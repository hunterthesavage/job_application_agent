from types import SimpleNamespace


def test_discover_job_links_passes_ai_title_expansion_flag(monkeypatch):
    import services.pipeline_runtime as runtime

    captured = {}
    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "legacy")

    monkeypatch.setattr(runtime, "load_settings", lambda: {"target_titles": "VP Technology"})

    def fake_discover_urls(settings, use_ai_expansion=True):
        captured["discover_urls_flag"] = use_ai_expansion
        return {
            "all_urls": ["https://example.com/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://example.com/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        }

    def fake_build_queries(settings, use_ai_expansion=False, log_lines=None):
        captured["build_queries_flag"] = use_ai_expansion
        return ["query 1"]

    monkeypatch.setattr(runtime.discover_module, "discover_urls", fake_discover_urls)
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(runtime.discover_module, "build_google_discovery_queries", fake_build_queries)
    monkeypatch.setattr(runtime.discover_module, "build_search_plan", lambda settings: ["Base titles: VP Technology"])

    result = runtime.discover_job_links(use_ai_title_expansion=False)

    assert captured["discover_urls_flag"] is False
    assert captured["build_queries_flag"] is False
    assert result["url_count"] == 1


def test_create_job_record_with_retry_retries_timeout_once(monkeypatch):
    import services.pipeline_runtime as runtime

    calls = {"count": 0}

    def fake_create_job_record(job_url):
        calls["count"] += 1
        if calls["count"] == 1:
            raise runtime.requests.exceptions.ReadTimeout("timed out")
        return SimpleNamespace(job_posting_url=job_url)

    monkeypatch.setattr(runtime, "create_job_record", fake_create_job_record)
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: None)

    job = runtime._create_job_record_with_retry("https://jobs.lever.co/example/1")

    assert calls["count"] == 2
    assert job.job_posting_url == "https://jobs.lever.co/example/1"


def test_normalize_job_posting_url_strips_lever_apply_suffix():
    import services.pipeline_runtime as runtime

    assert runtime._normalize_job_posting_url(
        "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf/apply"
    ) == "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf"


def test_normalize_job_posting_url_strips_ashby_application_suffix():
    import services.pipeline_runtime as runtime

    assert runtime._normalize_job_posting_url(
        "https://jobs.ashbyhq.com/mariner-careers/2a0b64d2-8483-461a-b08c-aad3b9ab6ddb/application"
    ) == "https://jobs.ashbyhq.com/mariner-careers/2a0b64d2-8483-461a-b08c-aad3b9ab6ddb"


def test_normalize_job_posting_urls_dedupes_wrapper_and_detail_variants():
    import services.pipeline_runtime as runtime

    assert runtime._normalize_job_posting_urls(
        [
            "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf/apply",
            "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf",
            "https://jobs.ashbyhq.com/mariner-careers/2a0b64d2-8483-461a-b08c-aad3b9ab6ddb/application",
            "https://jobs.ashbyhq.com/mariner-careers/2a0b64d2-8483-461a-b08c-aad3b9ab6ddb",
        ]
    ) == [
        "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf",
        "https://jobs.ashbyhq.com/mariner-careers/2a0b64d2-8483-461a-b08c-aad3b9ab6ddb",
    ]


def test_is_probable_job_url_allows_workday_detail_with_careers_segment():
    import services.pipeline_runtime as runtime

    is_job, reason = runtime.is_probable_job_url(
        "https://regeneron.wd1.myworkdayjobs.com/it-IT/Careers/job/Vice-President--Information-Technology_R42096"
    )

    assert is_job is True
    assert reason == "workday_detail"


def test_create_job_record_with_retry_does_not_retry_non_transient_error(monkeypatch):
    import services.pipeline_runtime as runtime

    calls = {"count": 0}

    def fake_create_job_record(job_url):
        calls["count"] += 1
        raise ValueError("bad parse")

    monkeypatch.setattr(runtime, "create_job_record", fake_create_job_record)
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: None)

    try:
        runtime._create_job_record_with_retry("https://example.com/jobs/1")
    except ValueError as exc:
        assert str(exc) == "bad parse"
    else:
        raise AssertionError("Expected ValueError to be raised")

    assert calls["count"] == 1


def test_build_jobs_from_urls_treats_ats_404_as_skip(monkeypatch):
    import services.pipeline_runtime as runtime

    response = runtime.requests.Response()
    response.status_code = 404
    http_error = runtime.requests.exceptions.HTTPError("404 not found")
    http_error.response = response

    monkeypatch.setattr(runtime, "load_settings", lambda: {})
    monkeypatch.setattr(runtime, "is_probable_job_url", lambda job_url: (True, "lever_detail"))
    monkeypatch.setattr(runtime, "_cheap_url_title_prefilter", lambda job_url, settings: (True, "ok"))
    monkeypatch.setattr(runtime, "create_job_record", lambda job_url: (_ for _ in ()).throw(http_error))
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        runtime,
        "ingest_job_records",
        lambda **kwargs: {
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_removed_count": 0,
            "net_new_count": 0,
            "rediscovered_count": 0,
            "duplicate_in_run_count": 0,
        },
    )

    result = runtime._build_jobs_from_urls(
        ["https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf"],
        source_name="Local Pipeline",
        source_detail="test",
        use_ai_scoring=False,
    )

    assert result["error_count"] == 0
    assert result["skipped_count"] == 1
    assert "Skipped unavailable ATS posting" in result["output"]


def test_build_jobs_from_urls_canonicalizes_wrapper_urls_before_validation(monkeypatch):
    import services.pipeline_runtime as runtime

    seen = {"gate": [], "created": []}

    monkeypatch.setattr(runtime, "load_settings", lambda: {})

    def fake_is_probable_job_url(job_url):
        seen["gate"].append(job_url)
        return True, "lever_detail"

    def fake_create_job_record(job_url):
        seen["created"].append(job_url)
        return SimpleNamespace(
            title="Vice President of Engineering",
            company="Example",
            location="Dallas, TX",
            description="",
            job_posting_url=job_url,
        )

    monkeypatch.setattr(runtime, "is_probable_job_url", fake_is_probable_job_url)
    monkeypatch.setattr(runtime, "_cheap_url_title_prefilter", lambda job_url, settings: (True, "ok"))
    monkeypatch.setattr(runtime, "create_job_record", fake_create_job_record)
    monkeypatch.setattr(runtime, "score_job_match", lambda job, settings: {"should_accept": True, "score": 80, "reason_text": "ok"})
    monkeypatch.setattr(runtime, "enrich_job_payload", lambda job, source_hint, source_detail_hint: {
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "job_posting_url": job.job_posting_url,
        "source_trust": "ATS Confirmed",
    })
    monkeypatch.setattr(
        runtime,
        "ingest_job_records",
        lambda **kwargs: {
            "inserted_count": 1,
            "updated_count": 0,
            "skipped_removed_count": 0,
            "net_new_count": 1,
            "rediscovered_count": 0,
            "duplicate_in_run_count": 0,
        },
    )

    result = runtime._build_jobs_from_urls(
        [
            "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf/apply",
            "https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf",
        ],
        source_name="Local Pipeline",
        source_detail="test",
        use_ai_scoring=False,
    )

    assert seen["gate"] == ["https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf"]
    assert seen["created"] == ["https://jobs.lever.co/aledade/4275e2d5-b433-4447-bfee-2b409deec4bf"]
    assert result["seen_urls"] == 1


def test_discover_job_links_includes_shadow_summary_when_enabled(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "shadow")
    monkeypatch.setattr(runtime, "load_settings", lambda: {"target_titles": "VP Technology"})
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": ["https://example.com/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://example.com/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(runtime.discover_module, "build_google_discovery_queries", lambda settings, use_ai_expansion=False: [])
    monkeypatch.setattr(runtime.discover_module, "build_search_plan", lambda settings: ["Base titles: VP Technology"])
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings: {"output": "Direct-source seed shadow summary:\n- Active imported endpoints: 12"},
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["source_layer_mode"] == "shadow"
    assert "Direct-source seed shadow summary" in result["output"]


def test_ingest_pasted_urls_passes_ai_scoring_flag(tmp_path, monkeypatch):
    import services.pipeline_runtime as runtime

    captured = {}
    manual_file = tmp_path / "manual_urls.txt"

    monkeypatch.setattr(runtime, "MANUAL_URLS_FILE", manual_file, raising=False)

    def fake_build_jobs(urls, source_name, source_detail, *, use_ai_scoring=True):
        captured["urls"] = urls
        captured["source_name"] = source_name
        captured["source_detail"] = source_detail
        captured["use_ai_scoring"] = use_ai_scoring
        return {"status": "completed", "output": "ok"}

    monkeypatch.setattr(runtime, "_build_jobs_from_urls", fake_build_jobs)

    result = runtime.ingest_pasted_urls("https://example.com/jobs/1", use_ai_scoring=False)

    assert result["status"] == "completed"
    assert captured["urls"] == ["https://example.com/jobs/1"]
    assert captured["source_name"] == "Local Pipeline"
    assert captured["use_ai_scoring"] is False
    assert manual_file.exists()


def test_discover_and_ingest_passes_ai_flags(monkeypatch):
    import services.pipeline_runtime as runtime

    captured = {}
    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "legacy")
    monkeypatch.setattr(
        runtime,
        "build_source_layer_status_summary",
        lambda: {
            "shadow": {
                "company_count": 473,
                "active_endpoint_count": 473,
                "approved_endpoint_count": 3,
            }
        },
    )
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "ats_counts": {"unknown": 313, "workday": 76},
            "selected_ats_counts": {"workday": 12, "lever": 8},
            "selected_company_names": ["Rover", "Checkr"],
            "selected_endpoint_count": 20,
        },
    )
    monkeypatch.setattr(
        runtime,
        "record_source_layer_run",
        lambda **kwargs: captured.setdefault("source_layer_run", kwargs),
    )
    monkeypatch.setattr(
        runtime,
        "update_ingestion_run_details",
        lambda run_id, extra_details: captured.setdefault("updated_run_details", []).append((run_id, extra_details)),
    )

    def fake_discover_job_links(*, use_ai_title_expansion=True):
        captured["discover_flag"] = use_ai_title_expansion
        return {
            "status": "completed",
            "output": "Discovery output",
            "urls": ["https://example.com/jobs/1"],
            "providers": {"greenhouse": 0, "lever": 0, "search": 1},
            "drop_summary": {},
        }

    def fake_build_jobs(urls, source_name, source_detail, *, use_ai_scoring=True, seeded_job_urls=None):
        captured["use_ai_scoring"] = use_ai_scoring
        captured["seeded_job_urls"] = seeded_job_urls
        return {
            "status": "completed",
            "output": "Ingest output",
            "summary": {
                "run_id": 42,
                "inserted_count": 0,
                "updated_count": 0,
                "skipped_removed_count": 0,
            },
            "accepted_jobs": 0,
            "seen_urls": 1,
            "skipped_count": 0,
            "skipped_duplicate_batch_count": 0,
            "error_count": 0,
            "build_seconds": 0.0,
            "ingest_seconds": 0.0,
            "skip_summary": {},
            "seeded_accepted_jobs": 0,
            "seeded_accepted_companies": [],
        }

    monkeypatch.setattr(runtime, "discover_job_links", fake_discover_job_links)
    monkeypatch.setattr(runtime, "_build_jobs_from_urls", fake_build_jobs)

    result = runtime.discover_and_ingest(
        use_ai_title_expansion=False,
        use_ai_scoring=False,
    )

    assert captured["discover_flag"] is False
    assert captured["use_ai_scoring"] is False
    assert captured["seeded_job_urls"] == []
    assert captured["updated_run_details"][0][0] == 42
    assert "pipeline_total_seconds" in captured["updated_run_details"][0][1]
    assert "Discovery output" in result["output"]
    assert "Ingest output" in result["output"]
    assert "Source Layer Run Snapshot:" in result["output"]
    assert "- Mode: legacy" in result["output"]
    assert "- Shadow active endpoints: 473" in result["output"]
    assert "- Shadow selected endpoints: 20" in result["output"]
    assert "- Direct-source seeded accepted jobs: 0" in result["output"]
    assert captured["source_layer_run"]["mode"] == "legacy"
    assert captured["source_layer_run"]["discovered_urls"] == 1
    assert captured["source_layer_run"]["accepted_jobs"] == 0
    assert captured["source_layer_run"]["selected_endpoints"] == 0


def test_discover_and_ingest_runs_existing_job_maintenance(monkeypatch):
    import services.pipeline_runtime as runtime

    captured = {}
    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "legacy")
    monkeypatch.setattr(
        runtime,
        "discover_job_links",
        lambda use_ai_title_expansion=True: {
            "status": "completed",
            "output": "Discovery output",
            "urls": ["https://example.com/jobs/1"],
            "providers": {"greenhouse": 0, "lever": 0, "search": 1},
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(
        runtime,
        "_build_jobs_from_urls",
        lambda *args, **kwargs: {
            "status": "completed",
            "output": "Ingest output",
            "summary": {
                "run_id": 42,
                "inserted_count": 1,
                "updated_count": 0,
                "skipped_removed_count": 0,
            },
            "accepted_jobs": 1,
            "seen_urls": 1,
            "skipped_count": 0,
            "skipped_duplicate_batch_count": 0,
            "error_count": 0,
            "build_seconds": 0.0,
            "ingest_seconds": 0.0,
            "skip_summary": {},
        },
    )
    monkeypatch.setattr(runtime, "_record_pipeline_source_layer_run", lambda **kwargs: None)
    monkeypatch.setattr(runtime, "_format_source_layer_run_snapshot", lambda **kwargs: "Snapshot")

    def fake_refresh_existing_jobs_if_needed(**kwargs):
        captured["maintenance_kwargs"] = kwargs
        return {
            "status": "completed",
            "output": "Existing-job maintenance summary:\n- Existing jobs refreshed: 3",
            "refreshed_count": 3,
            "rescored_count": 2,
            "changed_count": 2,
        }

    monkeypatch.setattr(runtime, "refresh_existing_jobs_if_needed", fake_refresh_existing_jobs_if_needed)
    monkeypatch.setattr(
        runtime,
        "update_ingestion_run_details",
        lambda run_id, extra_details: captured.setdefault("updated_run_details", []).append((run_id, extra_details)),
    )

    result = runtime.discover_and_ingest(use_ai_scoring=True)

    assert result["maintenance"]["refreshed_count"] == 3
    assert captured["maintenance_kwargs"]["exclude_run_id"] == 42
    assert captured["maintenance_kwargs"]["use_ai_scoring"] is True
    assert captured["updated_run_details"][0][1]["maintenance_refreshed_count"] == 3


def test_discover_and_ingest_reports_next_gen_mode_but_falls_back_safely(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    captured = {}
    monkeypatch.setattr(
        runtime,
        "refresh_existing_jobs_if_needed",
        lambda **kwargs: {
            "output": "Existing-job maintenance summary:\n- Existing jobs selected: 0",
            "refreshed_count": 0,
            "rescored_count": 0,
            "changed_count": 0,
        },
    )
    monkeypatch.setattr(
        runtime,
        "build_source_layer_status_summary",
        lambda: {
            "shadow": {
                "company_count": 473,
                "active_endpoint_count": 473,
                "approved_endpoint_count": 3,
            }
        },
    )
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "ats_counts": {"unknown": 313, "workday": 76},
            "selected_ats_counts": {"workday": 12, "lever": 8},
            "selected_company_names": ["Rover", "Checkr"],
            "selected_endpoint_count": 20,
        },
    )
    monkeypatch.setattr(
        runtime,
        "record_source_layer_run",
        lambda **kwargs: captured.setdefault("source_layer_run", kwargs),
    )
    monkeypatch.setattr(
        runtime,
        "discover_job_links",
        lambda **kwargs: {
            "status": "completed",
            "output": "Discovery output\n\nDirect-source seeding mode requested. Legacy discovery remains primary for this run, and supported direct-source seed URLs will be added when available.",
            "urls": [],
            "providers": {"greenhouse": 0, "lever": 0, "search": 0},
            "drop_summary": {},
            "shadow_result": {
                "selected_ats_counts": {"workday": 12, "lever": 8},
                "selected_company_names": ["Rover", "Checkr"],
                "selected_endpoint_count": 20,
            },
            "next_gen_seed_urls": ["https://jobs.lever.co/rover/1", "https://jobs.lever.co/rover/2"],
        },
    )

    result = runtime.discover_and_ingest()

    assert "Source layer mode: next_gen" in result["output"]
    assert "Direct-source seeding mode requested" in result["output"]
    assert "Source Layer Run Snapshot:" in result["output"]
    assert "- Mode: next_gen" in result["output"]
    assert "- Direct-source seeds scanned: 0" in result["output"]
    assert "- Direct-source unsupported seeds skipped: 0" in result["output"]
    assert "- Direct-source seeded URLs: 2" in result["output"]
    assert "- Direct-source seeded accepted jobs: 0" in result["output"]
    assert captured["source_layer_run"]["mode"] == "next_gen"
    assert captured["source_layer_run"]["discovered_urls"] == 0
    assert captured["source_layer_run"]["accepted_jobs"] == 0
    assert captured["source_layer_run"]["selected_endpoints"] == 20
    assert "Direct-source seeded URLs: 2." in captured["source_layer_run"]["notes"]


def test_discover_job_links_next_gen_merges_supported_seed_urls(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    monkeypatch.setattr(runtime, "load_settings", lambda: {"target_titles": "Business Analyst"})
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": ["https://legacy.example/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://legacy.example/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(runtime.discover_module, "build_google_discovery_queries", lambda settings, use_ai_expansion=False: [])
    monkeypatch.setattr(runtime.discover_module, "build_search_plan", lambda settings: ["Base titles: Business Analyst"])
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 2",
            "selected_endpoint_count": 2,
            "selected_company_names": ["Rover", "Checkr"],
            "selected_ats_counts": {"lever": 1, "greenhouse": 1},
            "selected_candidates": [
                {
                    "company_name": "Rover",
                    "endpoint_url": "https://jobs.lever.co/rover",
                    "ats_vendor": "lever",
                },
                {
                    "company_name": "Checkr",
                    "endpoint_url": "https://job-boards.greenhouse.io/checkr",
                    "ats_vendor": "greenhouse",
                },
            ],
        },
    )
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_lever_jobs",
        lambda endpoint_url, settings: ["https://jobs.lever.co/rover/seeded-job"],
    )
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_greenhouse_jobs",
        lambda endpoint_url, settings: ["https://job-boards.greenhouse.io/checkr/jobs/seeded-job"],
    )
    monkeypatch.setattr(
        runtime,
        "_discover_workday_jobs",
        lambda endpoint_url, settings: ["https://company.wd5.myworkdayjobs.com/job/seeded-workday"],
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["source_layer_mode"] == "next_gen"
    assert result["next_gen_seed_urls"] == [
        "https://jobs.lever.co/rover/seeded-job",
        "https://job-boards.greenhouse.io/checkr/jobs/seeded-job",
    ]
    assert result["next_gen_supported_seeds_scanned"] == 2
    assert result["next_gen_unsupported_seeds_skipped"] == 0
    assert result["urls"][:2] == result["next_gen_seed_urls"]
    assert "Direct-source seed discovery summary:" in result["output"]
    assert "Direct-source seeds added 2 URL(s) ahead of legacy results for this run." in result["output"]


def test_discover_job_links_next_gen_supports_workday_seeds(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    monkeypatch.setattr(runtime, "load_settings", lambda: {"target_titles": "Business Analyst"})
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": ["https://legacy.example/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://legacy.example/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 1",
            "selected_endpoint_count": 1,
            "selected_company_names": ["Centene"],
            "selected_ats_counts": {"workday": 1},
            "selected_candidates": [
                {
                    "company_name": "Centene",
                    "endpoint_url": "https://centene.wd5.myworkdayjobs.com/Centene_External",
                    "ats_vendor": "workday",
                }
            ],
        },
    )
    monkeypatch.setattr(
        runtime,
        "_discover_workday_jobs",
        lambda endpoint_url, settings: ["https://centene.wd5.myworkdayjobs.com/job/Remote-OK/Business-Analyst_123"],
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["next_gen_seed_urls"] == [
        "https://centene.wd5.myworkdayjobs.com/job/Remote-OK/Business-Analyst_123"
    ]
    assert result["next_gen_supported_seeds_scanned"] == 1
    assert result["next_gen_unsupported_seeds_skipped"] == 0
    assert "Checking direct-source Workday seed: Centene" in result["output"]
    assert "Direct-source Workday URLs found: 1" in result["output"]


def test_discover_job_links_next_gen_supports_successfactors_seeds(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    monkeypatch.setattr(
        runtime,
        "load_settings",
        lambda: {
            "target_titles": "Business Analyst",
            "preferred_locations": "Dallas",
            "remote_only": "false",
        },
    )
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": ["https://legacy.example/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://legacy.example/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 1",
            "selected_endpoint_count": 1,
            "selected_company_names": ["Paramount"],
            "selected_ats_counts": {"sap successfactors": 1},
            "selected_candidates": [
                {
                    "company_name": "Paramount",
                    "endpoint_url": "https://careers.paramount.com/viewalljobs/",
                    "ats_vendor": "sap successfactors",
                }
            ],
        },
    )
    monkeypatch.setattr(
        runtime,
        "_discover_successfactors_jobs",
        lambda endpoint_url, settings: [
            "https://careers.paramount.com/job/Remote/Business-Analyst/123/",
            "https://careers.paramount.com/job/Dallas/Business-Analyst/124/",
            "https://careers.paramount.com/job/Dallas/Business-Analyst/125/",
            "https://careers.paramount.com/job/Dallas/Business-Analyst/126/",
            "https://careers.paramount.com/job/Austin/Senior-Sales-Manager/127/",
        ],
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["next_gen_seed_urls"] == [
        "https://careers.paramount.com/job/Remote/Business-Analyst/123/",
        "https://careers.paramount.com/job/Dallas/Business-Analyst/124/",
    ]
    assert result["next_gen_supported_seeds_scanned"] == 1
    assert result["next_gen_unsupported_seeds_skipped"] == 0
    assert "Checking direct-source SuccessFactors seed: Paramount" in result["output"]
    assert "Direct-source SuccessFactors URLs found: 5 | kept: 2" in result["output"]


def test_discover_job_links_next_gen_supports_icims_seeds(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    monkeypatch.setattr(
        runtime,
        "load_settings",
        lambda: {
            "target_titles": "Business Analyst",
            "preferred_locations": "Dallas",
            "remote_only": "false",
        },
    )
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": ["https://legacy.example/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://legacy.example/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 1",
            "selected_endpoint_count": 1,
            "selected_company_names": ["Schwab"],
            "selected_ats_counts": {"icims": 1},
            "selected_candidates": [
                {
                    "company_name": "Schwab",
                    "endpoint_url": "https://career-schwab.icims.com/jobs",
                    "ats_vendor": "icims",
                }
            ],
        },
    )
    monkeypatch.setattr(
        runtime,
        "_discover_icims_jobs",
        lambda endpoint_url, settings: [
            "https://career-schwab.icims.com/jobs/120193/business-analyst-platform/job",
            "https://career-schwab.icims.com/jobs/120301/senior-it-project-manager/job",
            "https://career-schwab.icims.com/jobs/120302/business-analyst-dallas/job",
            "https://career-schwab.icims.com/jobs/120303/business-analyst-remote/job",
        ],
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["next_gen_seed_urls"] == [
        "https://career-schwab.icims.com/jobs/120302/business-analyst-dallas/job",
        "https://career-schwab.icims.com/jobs/120303/business-analyst-remote/job",
    ]
    assert result["next_gen_supported_seeds_scanned"] == 1
    assert result["next_gen_unsupported_seeds_skipped"] == 0
    assert "Checking direct-source iCIMS seed: Schwab" in result["output"]
    assert "Direct-source iCIMS URLs found: 4 | kept: 2" in result["output"]


def test_discover_job_links_next_gen_supports_taleo_oracle_seeds(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    monkeypatch.setattr(
        runtime,
        "load_settings",
        lambda: {
            "target_titles": "Vice President of IT",
            "preferred_locations": "Dallas",
            "remote_only": "false",
        },
    )
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": ["https://legacy.example/jobs/1"],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": ["https://legacy.example/jobs/1"],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(
        runtime,
        "run_shadow_endpoint_selection",
        lambda settings=None: {
            "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 1",
            "selected_endpoint_count": 1,
            "selected_company_names": ["Weyerhaeuser"],
            "selected_ats_counts": {"taleo / oracle recruiting": 1},
            "selected_candidates": [
                {
                    "company_name": "Weyerhaeuser",
                    "endpoint_url": "https://weyerhaeuser.taleo.net/careersection/10000/jobsearch.ftl",
                    "ats_vendor": "taleo / oracle recruiting",
                }
            ],
        },
    )
    monkeypatch.setattr(
        runtime,
        "_discover_taleo_jobs",
        lambda endpoint_url, settings: [
            "https://weyerhaeuser.taleo.net/careersection/10000/jobdetail.ftl?job=459712",
            "https://weyerhaeuser.taleo.net/careersection/10000/jobdetail.ftl?job=459713",
        ],
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["next_gen_seed_urls"] == [
        "https://weyerhaeuser.taleo.net/careersection/10000/jobdetail.ftl?job=459712",
        "https://weyerhaeuser.taleo.net/careersection/10000/jobdetail.ftl?job=459713",
    ]
    assert result["next_gen_supported_seeds_scanned"] == 1
    assert result["next_gen_unsupported_seeds_skipped"] == 0
    assert "Checking direct-source Taleo seed: Weyerhaeuser" in result["output"]
    assert "Direct-source Taleo URLs found: 2 | kept: 2" in result["output"]


def test_discover_job_links_next_gen_fallback_scans_second_shadow_batch(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    monkeypatch.setattr(
        runtime,
        "load_settings",
        lambda: {
            "target_titles": "VP of IT",
            "remote_only": "true",
        },
    )
    monkeypatch.setattr(
        runtime.discover_module,
        "discover_urls",
        lambda settings, use_ai_expansion=True: {
            "all_urls": [],
            "greenhouse_urls": [],
            "lever_urls": [],
            "search_urls": [],
            "output": "Discovery output",
            "drop_summary": {},
        },
    )
    monkeypatch.setattr(runtime.discover_module, "save_output_urls", lambda file_path, urls: None)
    monkeypatch.setattr(runtime.discover_module, "build_google_discovery_queries", lambda settings, use_ai_expansion=False: [])
    monkeypatch.setattr(runtime.discover_module, "build_search_plan", lambda settings: ["Base titles: VP of IT"])

    calls = {"shadow_offsets": [], "shadow_excludes": [], "seed_batches": []}

    def fake_run_shadow(settings=None):
        settings = settings or {}
        offset = int(settings.get("_shadow_selection_offset", 0) or 0)
        calls["shadow_offsets"].append(offset)
        calls["shadow_excludes"].append(str(settings.get("_shadow_exclude_endpoint_urls", "") or ""))
        if offset == 0:
            if calls["shadow_excludes"][-1]:
                return {
                    "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 25",
                    "active_endpoint_count": 50,
                    "selected_endpoint_count": 25,
                    "selected_candidates": [
                        {"company_name": "Second Batch", "endpoint_url": "https://second.example", "ats_vendor": "icims"}
                    ],
                }
            return {
                "output": "Direct-source seed shadow summary:\n- Selected shadow candidates: 25",
                "active_endpoint_count": 50,
                "selected_endpoint_count": 25,
                "selected_candidates": [
                    {"company_name": "First Batch", "endpoint_url": "https://first.example", "ats_vendor": "icims"}
                ],
            }
        raise AssertionError("Fallback should exclude first-batch endpoints instead of paging by offset")

    def fake_discover_from_seeds(*, settings, shadow_result):
        company_name = shadow_result["selected_candidates"][0]["company_name"]
        calls["seed_batches"].append(company_name)
        if company_name == "First Batch":
            return [], ["First batch log"], 25, 0, []
        return ["https://jobs.example/seeded-second-batch"], ["Second batch log"], 25, 0, []

    monkeypatch.setattr(runtime, "run_shadow_endpoint_selection", fake_run_shadow)
    monkeypatch.setattr(runtime, "_discover_urls_from_next_gen_seeds", fake_discover_from_seeds)

    result = runtime.discover_job_links(use_ai_title_expansion=False)

    assert calls["shadow_offsets"] == [0, 0]
    assert calls["shadow_excludes"] == ["", "https://first.example"]
    assert calls["seed_batches"] == ["First Batch", "Second Batch"]
    assert result["next_gen_seed_urls"] == ["https://jobs.example/seeded-second-batch"]
    assert result["next_gen_supported_seeds_scanned"] == 50
    assert "Direct-source seed fallback triggered." in result["output"]


def test_filter_next_gen_seed_urls_prefers_relevant_matches():
    import services.pipeline_runtime as runtime

    kept, title_skips, location_skips = runtime._filter_next_gen_seed_urls(
        [
            "https://careers.example.com/job/Remote/Vice-President-of-IT/1/",
            "https://careers.example.com/job/Dallas/Vice-President-of-IT/2/",
            "https://careers.example.com/job/Houston/Vice-President-of-IT/4/",
            "https://careers.example.com/job/Dallas/Sr-Sales-Manager/5/",
            "https://careers.example.com/job/Dallas/Vice-President-of-IT/3/",
        ],
        {
            "target_titles": "Vice President of IT",
            "preferred_locations": "Dallas",
            "remote_only": "false",
        },
        apply_location_filter=True,
    )

    assert kept == [
        "https://careers.example.com/job/Remote/Vice-President-of-IT/1/",
        "https://careers.example.com/job/Dallas/Vice-President-of-IT/2/",
    ]
    assert title_skips == 0
    assert location_skips == 0


def test_cheap_seed_location_prefilter_rejects_explicit_foreign_remote_hint():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_seed_location_prefilter_from_hint(
        "Mexico Remote",
        {
            "preferred_locations": "Remote",
            "remote_only": "true",
        },
    )

    assert passed is False
    assert "foreign remote mismatch" in reason


def test_cheap_seed_location_prefilter_allows_us_remote_hint():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_seed_location_prefilter_from_hint(
        "United States Remote",
        {
            "preferred_locations": "Remote",
            "remote_only": "true",
        },
    )

    assert passed is True
    assert "matched remote" in reason


def test_cheap_url_title_prefilter_rejects_wrong_executive_lane_without_hardcoded_title():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_url_title_prefilter(
        "https://careers.example.com/job/Dallas/Vice-President-of-Manufacturing/1/",
        {"target_titles": "Vice President of IT"},
    )

    assert passed is False
    assert "signature mismatch" in reason


def test_cheap_url_title_prefilter_allows_adjacent_technology_leadership_lane():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_url_title_prefilter(
        "https://careers.example.com/job/Dallas/Vice-President-of-Engineering/1/",
        {"target_titles": "Vice President of IT"},
    )

    assert passed is True
    assert "token overlap" in reason


def test_cheap_url_title_prefilter_rejects_real_mohawk_manufacturing_slug():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_url_title_prefilter(
        "https://careers.mohawkind.com/DalTile/job/Dallas-VP-OF-MANUFACTURING-%28MULTI-SITE%29-Texa-75217/1365283300/",
        {"target_titles": "Vice President of IT"},
    )

    assert passed is False
    assert "signature mismatch" in reason


def test_cheap_url_title_prefilter_rejects_real_hfs_manager_slug():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_url_title_prefilter(
        "https://careers.hfsinclair.com/job/Dallas-Natural-Gas-Supply-Manager-TX-75219/1368517600/",
        {"target_titles": "Vice President of IT"},
    )

    assert passed is False
    assert "prefilter mismatch" in reason or "signature mismatch" in reason


def test_cheap_seed_title_prefilter_allows_adjacent_technology_vp_slug():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_seed_title_prefilter(
        "https://example.com/job/remote/Vice-President-IT-Infrastructure/123/",
        {"target_titles": "VP of IT"},
    )

    assert passed is True
    assert "seed title" in reason or "lane matched" in reason


def test_cheap_seed_title_prefilter_rejects_operations_vp_slug():
    import services.pipeline_runtime as runtime

    passed, reason = runtime._cheap_seed_title_prefilter(
        "https://example.com/job/remote/VP-OF-MANUFACTURING/123/",
        {"target_titles": "VP of IT"},
    )

    assert passed is False
    assert "seed title" in reason or "signature mismatch" in reason


def test_build_icims_search_url_uses_form_action_and_location_value(monkeypatch):
    import services.pipeline_runtime as runtime

    html = """
    <form action="https://career-schwab.icims.com/jobs/search?in_iframe=1&amp;hashed=-626009902">
      <select name="searchLocation">
        <option value="">(All)</option>
        <option value="-12787-Dallas">TX,Dallas</option>
      </select>
    </form>
    """

    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            return None

    monkeypatch.setattr(runtime.requests, "get", lambda *args, **kwargs: Response(html))

    url = runtime._build_icims_search_url(
        "https://career-schwab.icims.com/jobs",
        {
            "target_titles": "Vice President of IT",
            "preferred_locations": "Dallas",
            "remote_only": "false",
        },
    )

    assert "career-schwab.icims.com/jobs/search" in url
    assert "searchKeyword=Vice+President+of+information+technology" in url
    assert "searchLocation=-12787-Dallas" in url


def test_build_icims_search_url_without_title_keeps_search_shell(monkeypatch):
    import services.pipeline_runtime as runtime

    html = """
    <form action="https://career-schwab.icims.com/jobs/search?in_iframe=1&amp;hashed=-626009902">
      <select name="searchLocation">
        <option value="">(All)</option>
      </select>
    </form>
    """

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    monkeypatch.setattr(runtime.requests, "get", lambda *args, **kwargs: Response(html))

    url = runtime._build_icims_search_url(
        "https://career-schwab.icims.com/jobs",
        {
            "target_titles": "",
            "preferred_locations": "",
            "remote_only": "false",
        },
    )

    assert url == "https://career-schwab.icims.com/jobs/search?in_iframe=1&hashed=-626009902"


def test_discover_icims_jobs_without_titles_uses_listing_page_links(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    html = """
    <a href="/jobs/120302/business-analyst-dallas/job?mode=job">Business Analyst</a>
    <a href="/jobs/120303/business-analyst-remote/job">Business Analyst Remote</a>
    """

    monkeypatch.setattr(runtime.requests, "get", lambda *args, **kwargs: Response(html))

    urls = runtime._discover_icims_jobs(
        "https://career-schwab.icims.com/jobs",
        {
            "target_titles": "",
            "preferred_locations": "",
            "remote_only": "false",
        },
    )

    assert urls == [
        "https://career-schwab.icims.com/jobs/120302/business-analyst-dallas/job?mode=job",
        "https://career-schwab.icims.com/jobs/120303/business-analyst-remote/job",
    ]


def test_discover_icims_jobs_without_titles_falls_back_to_talentbrew_search_jobs(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *args, **kwargs):
        if url == "https://career-schwab.icims.com/jobs":
            return Response(
                """
                <html>
                  <head><base href="https://www.schwabjobs.com/" /></head>
                  <body><a href="/search-jobs">Search Jobs</a></body>
                </html>
                """
            )
        if url == "https://www.schwabjobs.com/search-jobs":
            return Response(
                """
                <a href="/job/westlake/director-platform-engineering/33727/92849236608">
                  Director Platform Engineering
                </a>
                """
            )
        raise AssertionError(url)

    monkeypatch.setattr(runtime.requests, "get", fake_get)

    urls = runtime._discover_icims_jobs(
        "https://career-schwab.icims.com/jobs",
        {
            "target_titles": "",
            "preferred_locations": "",
            "remote_only": "false",
        },
    )

    assert urls == [
        "https://www.schwabjobs.com/job/westlake/director-platform-engineering/33727/92849236608"
    ]


def test_build_icims_search_url_ignores_failing_jobs_root_fallback(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text, should_raise=False):
            self.text = text
            self.should_raise = should_raise

        def raise_for_status(self):
            if self.should_raise:
                raise runtime.requests.HTTPError("404")
            return None

    def fake_get(url, *args, **kwargs):
        if url == "https://careers.questdiagnostics.com/job-seeker-resources":
            return Response("<html><body>No search form here.</body></html>")
        if url == "https://careers.questdiagnostics.com/jobs":
            return Response("", should_raise=True)
        raise AssertionError(url)

    monkeypatch.setattr(runtime.requests, "get", fake_get)

    url = runtime._build_icims_search_url(
        "https://careers.questdiagnostics.com/job-seeker-resources",
        {
            "target_titles": "Vice President of IT",
            "preferred_locations": "",
            "remote_only": "false",
        },
    )

    assert url == ""


def test_build_successfactors_search_url_without_title_uses_browse_page():
    import services.pipeline_runtime as runtime

    url = runtime._build_successfactors_search_url(
        "https://jobs.brighthousefinancial.com/content/Reasonable-Accommodations/",
        {"target_titles": "", "preferred_locations": "", "remote_only": "false"},
    )

    assert url == "https://jobs.brighthousefinancial.com/search/"


def test_build_workday_detail_url_preserves_board_prefix():
    import services.pipeline_runtime as runtime

    url = runtime._build_workday_detail_url(
        "https://allstate.wd5.myworkdayjobs.com/allstate_careers",
        "/job/USA---WI-Remote/Project---Program-Management-Lead-Consultant_R26558-1",
    )

    assert (
        url
        == "https://allstate.wd5.myworkdayjobs.com/allstate_careers/job/USA---WI-Remote/Project---Program-Management-Lead-Consultant_R26558-1"
    )


def test_discover_workday_jobs_pages_through_results_without_internal_filtering(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text="", json_data=None):
            self.text = text
            self._json_data = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json_data

    page_html = """
    <script>
      tenant: "centene",
      siteId: "Centene_External",
      locale: "",
      requestLocale: "en-US",
    </script>
    """

    posts = [
        {
            "total": 25,
            "jobPostings": [
                {"externalPath": "/job/Remote-MO/General-Role-1_1001"},
                {"externalPath": "/job/Remote-MO/General-Role-2_1002"},
            ],
        },
        {
            "total": 25,
            "jobPostings": [
                {"externalPath": "/job/Remote-MO/VP-of-IT_2001"},
                {"externalPath": "/job/Remote-MO/Head-of-Technology_2002"},
            ],
        },
        {
            "total": 25,
            "jobPostings": [],
        },
    ]
    seen_payloads = []

    def fake_get(url, *args, **kwargs):
        assert url == "https://centene.wd5.myworkdayjobs.com/Centene_External"
        return Response(text=page_html)

    def fake_post(url, json=None, *args, **kwargs):
        assert url == "https://centene.wd5.myworkdayjobs.com/wday/cxs/centene/Centene_External/jobs"
        seen_payloads.append(dict(json or {}))
        return Response(json_data=posts[len(seen_payloads) - 1])

    monkeypatch.setattr(runtime.requests, "get", fake_get)
    monkeypatch.setattr(runtime.requests, "post", fake_post)

    urls = runtime._discover_workday_jobs(
        "https://centene.wd5.myworkdayjobs.com/Centene_External",
        {
            "target_titles": "",
            "preferred_locations": "Remote",
            "remote_only": "false",
        },
    )

    assert urls == [
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-MO/General-Role-1_1001",
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-MO/General-Role-2_1002",
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-MO/VP-of-IT_2001",
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-MO/Head-of-Technology_2002",
    ]
    assert seen_payloads == [
        {"limit": runtime.WORKDAY_SEED_PAGE_SIZE, "offset": 0},
        {"limit": runtime.WORKDAY_SEED_PAGE_SIZE, "offset": runtime.WORKDAY_SEED_PAGE_SIZE},
        {"limit": runtime.WORKDAY_SEED_PAGE_SIZE, "offset": runtime.WORKDAY_SEED_PAGE_SIZE * 2},
    ]


def test_discover_workday_jobs_uses_search_safe_title_before_broad_fallback(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text="", json_data=None):
            self.text = text
            self._json_data = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json_data

    page_html = """
    <script>
      tenant: "centene",
      siteId: "Centene_External",
      locale: "",
      requestLocale: "en-US",
    </script>
    """

    seen_payloads = []

    def fake_get(url, *args, **kwargs):
        assert url == "https://centene.wd5.myworkdayjobs.com/Centene_External"
        return Response(text=page_html)

    def fake_post(url, json=None, *args, **kwargs):
        assert url == "https://centene.wd5.myworkdayjobs.com/wday/cxs/centene/Centene_External/jobs"
        payload = dict(json or {})
        seen_payloads.append(payload)
        if payload.get("searchText") == "vice president of information technology":
            return Response(json_data={"total": 0, "jobPostings": []})
        return Response(
            json_data={
                "total": 1,
                "jobPostings": [{"externalPath": "/job/Remote-MO/VP-of-IT_2001"}],
            }
        )

    monkeypatch.setattr(runtime.requests, "get", fake_get)
    monkeypatch.setattr(runtime.requests, "post", fake_post)

    urls = runtime._discover_workday_jobs(
        "https://centene.wd5.myworkdayjobs.com/Centene_External",
        {
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "false",
        },
    )

    assert urls == [
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-MO/VP-of-IT_2001",
    ]
    assert seen_payloads == [
        {
                "limit": runtime.WORKDAY_SEED_PAGE_SIZE,
                "offset": 0,
                "searchText": "vice president of information technology",
            },
        {
            "limit": runtime.WORKDAY_SEED_PAGE_SIZE,
            "offset": 0,
        },
    ]


def test_discover_workday_jobs_stops_after_search_results(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text="", json_data=None):
            self.text = text
            self._json_data = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json_data

    page_html = """
    <script>
      tenant: "centene",
      siteId: "Centene_External",
      locale: "",
      requestLocale: "en-US",
    </script>
    """

    seen_payloads = []

    def fake_get(url, *args, **kwargs):
        return Response(text=page_html)

    def fake_post(url, json=None, *args, **kwargs):
        payload = dict(json or {})
        seen_payloads.append(payload)
        return Response(
            json_data={
                "total": 1,
                "jobPostings": [{"externalPath": "/job/Remote-MO/VP-of-IT_2001"}],
            }
        )

    monkeypatch.setattr(runtime.requests, "get", fake_get)
    monkeypatch.setattr(runtime.requests, "post", fake_post)

    urls = runtime._discover_workday_jobs(
        "https://centene.wd5.myworkdayjobs.com/Centene_External",
        {
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "false",
        },
    )

    assert urls == [
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-MO/VP-of-IT_2001",
    ]
    assert seen_payloads == [
        {
            "limit": runtime.WORKDAY_SEED_PAGE_SIZE,
            "offset": 0,
            "searchText": "vice president of information technology",
        }
    ]


def test_discover_workday_jobs_prefilters_using_structured_posting_title_and_location(monkeypatch):
    import services.pipeline_runtime as runtime

    class Response:
        def __init__(self, text="", json_data=None):
            self.text = text
            self._json_data = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json_data

    page_html = """
    <script>
      tenant: "centene",
      siteId: "Centene_External",
      locale: "",
      requestLocale: "en-US",
    </script>
    """

    def fake_get(url, *args, **kwargs):
        return Response(text=page_html)

    def fake_post(url, json=None, *args, **kwargs):
        return Response(
            json_data={
                "total": 4,
                "jobPostings": [
                    {
                        "title": "Vice President, Information Technology",
                        "locationsText": "United States Remote",
                        "externalPath": "/job/Remote-USA/VP-Information-Technology_2001",
                    },
                    {
                        "title": "Intern, Biostatistics",
                        "locationsText": "Remote, USA",
                        "externalPath": "/job/Remote-USA/Intern-Biostatistics_1001",
                    },
                    {
                        "title": "Vice President, Sales",
                        "locationsText": "United States Remote",
                        "externalPath": "/job/Remote-USA/VP-Sales_1002",
                    },
                    {
                        "title": "Vice President, Information Technology",
                        "locationsText": "Mexico Remote",
                        "externalPath": "/job/Mexico-Remote/VP-Information-Technology_1003",
                    },
                ],
            }
        )

    monkeypatch.setattr(runtime.requests, "get", fake_get)
    monkeypatch.setattr(runtime.requests, "post", fake_post)

    urls = runtime._discover_workday_jobs(
        "https://centene.wd5.myworkdayjobs.com/Centene_External",
        {
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        },
    )

    assert urls == [
        "https://centene.wd5.myworkdayjobs.com/Centene_External/job/Remote-USA/VP-Information-Technology_2001",
    ]


def test_build_successfactors_search_url_uses_branded_search_path():
    import services.pipeline_runtime as runtime

    url = runtime._build_successfactors_search_url(
        "https://careers.paramount.com/viewalljobs/",
        {"target_titles": "Business Analyst, Data Analyst", "preferred_locations": "Seattle"},
    )

    assert url == "https://careers.paramount.com/search/?q=Business+Analyst&locationsearch=Seattle"


def test_build_successfactors_search_url_uses_search_safe_title_variant():
    import services.pipeline_runtime as runtime

    url = runtime._build_successfactors_search_url(
        "https://careers.paramount.com/viewalljobs/",
        {"target_titles": "VP of IT", "preferred_locations": "Remote", "remote_only": "true"},
    )

    assert (
        url
        == "https://careers.paramount.com/search/?q=vice+president+of+information+technology"
    )


def test_build_successfactors_search_url_rejects_generic_successfactors_host():
    import services.pipeline_runtime as runtime

    url = runtime._build_successfactors_search_url(
        "https://career4.successfactors.com/career",
        {"target_titles": "Business Analyst"},
    )

    assert url == ""


def test_build_taleo_search_url_supports_classic_public_search_page():
    import services.pipeline_runtime as runtime

    url = runtime._build_taleo_search_url(
        "https://weyerhaeuser.taleo.net/careersection/10000/jobsearch.ftl",
        {"target_titles": "Vice President of IT"},
    )

    assert (
        url
        == "https://weyerhaeuser.taleo.net/careersection/10000/jobsearch.ftl?keyword=Vice+President+of+information+technology"
    )


def test_build_taleo_search_url_uses_search_safe_title_variant():
    import services.pipeline_runtime as runtime

    url = runtime._build_taleo_search_url(
        "https://weyerhaeuser.taleo.net/careersection/10000/jobsearch.ftl",
        {"target_titles": "VP of IT"},
    )

    assert (
        url
        == "https://weyerhaeuser.taleo.net/careersection/10000/jobsearch.ftl?keyword=vice+president+of+information+technology"
    )


def test_build_icims_search_url_uses_search_safe_title_variant(monkeypatch):
    import services.pipeline_runtime as runtime

    html = """
    <form action="https://career-schwab.icims.com/jobs/search?in_iframe=1&amp;hashed=-626009902">
      <select name="searchLocation">
        <option value="">(All)</option>
        <option value="-12787-Remote">Remote</option>
      </select>
    </form>
    """

    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            return None

    monkeypatch.setattr(runtime.requests, "get", lambda *args, **kwargs: Response(html))

    url = runtime._build_icims_search_url(
        "https://career-schwab.icims.com/jobs",
        {
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        },
    )

    assert "searchKeyword=vice+president+of+information+technology" in url
    assert "searchLocation=" not in url


def test_build_jobs_from_urls_tracks_next_gen_seed_contribution(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "load_settings", lambda: {})
    monkeypatch.setattr(runtime, "is_probable_job_url", lambda url: (True, ""))
    monkeypatch.setattr(runtime, "_cheap_url_title_prefilter", lambda url, settings: (True, ""))
    monkeypatch.setattr(
        runtime,
        "create_job_record",
        lambda url: SimpleNamespace(
            company="SeedCo" if "seeded" in url else "LegacyCo",
            title="Business Analyst",
            location="Remote",
            normalized_title="Business Analyst",
            role_family="Business",
            remote_type="Remote",
            dallas_dfw_match="No",
            compensation_raw="",
            validation_status="Valid",
            validation_confidence="High",
            compensation_status="",
            job_posting_url=url,
        ),
    )
    monkeypatch.setattr(
        runtime,
        "score_job_match",
        lambda job, settings: {"should_accept": True, "score": 65, "reason_text": "match"},
    )
    monkeypatch.setattr(
        runtime,
        "enrich_job_payload",
        lambda job, source_hint, source_detail_hint: {
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "job_posting_url": job.job_posting_url,
            "source_trust": "ATS Confirmed",
            "ats_type": "Lever",
            "source_type": "ATS",
        },
    )
    monkeypatch.setattr(runtime, "load_scoring_profile_text", lambda: ("", ""))
    monkeypatch.setattr(
        runtime,
        "ingest_job_records",
        lambda job_records, source_name, source_detail, run_type="ingest_jobs": {
            "inserted_count": len(job_records),
            "updated_count": 0,
            "skipped_removed_count": 0,
            "source_yield_top": [],
            "source_dominance": {},
        },
    )

    result = runtime._build_jobs_from_urls(
        ["https://jobs.lever.co/seeded-job", "https://jobs.lever.co/legacy-job"],
        source_name="Local Pipeline",
        source_detail="in_memory_discovery_result",
        use_ai_scoring=False,
        seeded_job_urls=["https://jobs.lever.co/seeded-job"],
    )

    assert result["accepted_jobs"] == 2
    assert result["seeded_url_count"] == 1
    assert result["seeded_accepted_jobs"] == 1
    assert result["legacy_accepted_jobs"] == 1
    assert result["seeded_accepted_companies"] == ["SeedCo"]
    assert "Direct-source contribution summary:" in result["output"]
    assert "- Seeded URLs accepted: 1" in result["output"]


def test_build_jobs_from_urls_skips_ai_when_disabled(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "load_settings", lambda: {})
    monkeypatch.setattr(runtime, "is_probable_job_url", lambda url: (True, ""))
    monkeypatch.setattr(runtime, "_cheap_url_title_prefilter", lambda url, settings: (True, ""))
    monkeypatch.setattr(
        runtime,
        "create_job_record",
        lambda url: SimpleNamespace(title="VP Technology", location="Remote"),
    )
    monkeypatch.setattr(
        runtime,
        "score_job_match",
        lambda job, settings: {"should_accept": True, "score": 55, "reason_text": "Accepted"},
    )
    monkeypatch.setattr(
        runtime,
        "enrich_job_payload",
        lambda job, source_hint="", source_detail_hint="": {
            "company": "TestCo",
            "title": "VP Technology",
            "location": "Remote",
            "source_trust": "ATS Confirmed",
            "job_posting_url": "https://example.com/jobs/1",
        },
    )
    monkeypatch.setattr(runtime, "_batch_dedupe_key", lambda payload: "")
    monkeypatch.setattr(
        runtime,
        "ingest_job_records",
        lambda **kwargs: {
            "inserted_count": 1,
            "updated_count": 0,
            "skipped_removed_count": 0,
            "source_yield_top": [],
            "source_dominance": {},
        },
    )
    monkeypatch.setattr(
        runtime,
        "score_accepted_job",
        lambda payload, resume_profile_text: (_ for _ in ()).throw(AssertionError("AI scoring should be disabled")),
    )

    result = runtime._build_jobs_from_urls(
        ["https://example.com/jobs/1"],
        source_name="Local Pipeline",
        source_detail="manual_test",
        use_ai_scoring=False,
    )

    assert result["accepted_jobs"] == 1
    assert "AI job scoring: disabled for this run" in result["output"]
