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

    def fake_build_jobs(urls, source_name, source_detail, *, use_ai_scoring=True):
        captured["use_ai_scoring"] = use_ai_scoring
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
        }

    monkeypatch.setattr(runtime, "discover_job_links", fake_discover_job_links)
    monkeypatch.setattr(runtime, "_build_jobs_from_urls", fake_build_jobs)

    result = runtime.discover_and_ingest(
        use_ai_title_expansion=False,
        use_ai_scoring=False,
    )

    assert captured["discover_flag"] is False
    assert captured["use_ai_scoring"] is False
    assert "Discovery output" in result["output"]
    assert "Ingest output" in result["output"]
    assert "Source Layer Run Snapshot:" in result["output"]
    assert "- Mode: legacy" in result["output"]
    assert "- Shadow active endpoints: 473" in result["output"]
    assert "- Shadow selected endpoints: 20" in result["output"]
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
            "output": "Discovery output\n\nNext-gen source layer mode requested, but live next-gen discovery is not enabled yet. Falling back to legacy discovery for this run.",
            "urls": [],
            "providers": {"greenhouse": 0, "lever": 0, "search": 0},
            "drop_summary": {},
            "shadow_result": {
                "selected_ats_counts": {"workday": 12, "lever": 8},
                "selected_company_names": ["Rover", "Checkr"],
                "selected_endpoint_count": 20,
            },
        },
    )

    result = runtime.discover_and_ingest()

    assert "Source layer mode: next_gen" in result["output"]
    assert "Falling back to legacy discovery for this run." in result["output"]
    assert "Source Layer Run Snapshot:" in result["output"]
    assert "- Mode: next_gen" in result["output"]
    assert captured["source_layer_run"]["mode"] == "next_gen"
    assert captured["source_layer_run"]["discovered_urls"] == 0
    assert captured["source_layer_run"]["accepted_jobs"] == 0
    assert captured["source_layer_run"]["selected_endpoints"] == 20


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
