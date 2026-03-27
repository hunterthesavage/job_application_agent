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
        lambda settings: {"output": "Next-gen source layer shadow summary:\n- Active imported endpoints: 12"},
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["source_layer_mode"] == "shadow"
    assert "Next-gen source layer shadow summary" in result["output"]


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
    assert "Discovery output" in result["output"]
    assert "Ingest output" in result["output"]
    assert "Source Layer Run Snapshot:" in result["output"]
    assert "- Mode: legacy" in result["output"]
    assert "- Shadow active endpoints: 473" in result["output"]
    assert "- Shadow selected endpoints: 20" in result["output"]
    assert "- Next-gen seeded accepted jobs: 0" in result["output"]
    assert captured["source_layer_run"]["mode"] == "legacy"
    assert captured["source_layer_run"]["discovered_urls"] == 1
    assert captured["source_layer_run"]["accepted_jobs"] == 0
    assert captured["source_layer_run"]["selected_endpoints"] == 0


def test_discover_and_ingest_reports_next_gen_mode_but_falls_back_safely(monkeypatch):
    import services.pipeline_runtime as runtime

    monkeypatch.setattr(runtime, "get_source_layer_mode", lambda: "next_gen")
    captured = {}
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
            "output": "Discovery output\n\nNext-gen source layer mode requested. Legacy discovery remains primary for this run, and supported source-layer seed URLs will be added when available.",
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
    assert "Legacy discovery remains primary for this run" in result["output"]
    assert "Source Layer Run Snapshot:" in result["output"]
    assert "- Mode: next_gen" in result["output"]
    assert "- Next-gen supported seeds scanned: 0" in result["output"]
    assert "- Next-gen unsupported seeds skipped: 0" in result["output"]
    assert "- Next-gen seeded URLs: 2" in result["output"]
    assert "- Next-gen seeded accepted jobs: 0" in result["output"]
    assert captured["source_layer_run"]["mode"] == "next_gen"
    assert captured["source_layer_run"]["discovered_urls"] == 0
    assert captured["source_layer_run"]["accepted_jobs"] == 0
    assert captured["source_layer_run"]["selected_endpoints"] == 20
    assert "Next-gen seeded URLs: 2." in captured["source_layer_run"]["notes"]


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
            "output": "Next-gen source layer shadow summary:\n- Selected shadow candidates: 2",
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
    assert "Next-gen seed discovery summary:" in result["output"]
    assert "Next-gen seeds added 2 URL(s) ahead of legacy results for this run." in result["output"]


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
            "output": "Next-gen source layer shadow summary:\n- Selected shadow candidates: 1",
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
    assert "Checking next-gen Workday seed: Centene" in result["output"]
    assert "Next-gen Workday URLs found: 1" in result["output"]


def test_discover_job_links_next_gen_supports_successfactors_seeds(monkeypatch):
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
            "output": "Next-gen source layer shadow summary:\n- Selected shadow candidates: 1",
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
        lambda endpoint_url, settings: ["https://careers.paramount.com/job/Remote/Business-Analyst/123/"],
    )

    result = runtime.discover_job_links(use_ai_title_expansion=True)

    assert result["next_gen_seed_urls"] == [
        "https://careers.paramount.com/job/Remote/Business-Analyst/123/"
    ]
    assert result["next_gen_supported_seeds_scanned"] == 1
    assert result["next_gen_unsupported_seeds_skipped"] == 0
    assert "Checking next-gen SuccessFactors seed: Paramount" in result["output"]
    assert "Next-gen SuccessFactors URLs found: 1" in result["output"]


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


def test_build_successfactors_search_url_uses_branded_search_path():
    import services.pipeline_runtime as runtime

    url = runtime._build_successfactors_search_url(
        "https://careers.paramount.com/viewalljobs/",
        {"target_titles": "Business Analyst, Data Analyst", "preferred_locations": "Seattle"},
    )

    assert url == "https://careers.paramount.com/search/?q=Business+Analyst&locationsearch=Seattle"


def test_build_successfactors_search_url_rejects_generic_successfactors_host():
    import services.pipeline_runtime as runtime

    url = runtime._build_successfactors_search_url(
        "https://career4.successfactors.com/career",
        {"target_titles": "Business Analyst"},
    )

    assert url == ""


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
    assert "Next-gen contribution summary:" in result["output"]
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
