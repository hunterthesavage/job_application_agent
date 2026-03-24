def test_rescore_existing_jobs_refreshes_stale_scores(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.pipeline_runtime as runtime

    stale_payload = dict(sample_job_payload)
    stale_payload["title"] = "Compensation Analyst"
    stale_payload["normalized_title"] = "Compensation Analyst"
    stale_payload["fit_score"] = 91
    stale_payload["fit_tier"] = "Strong"
    stale_payload["ai_priority"] = "Apply"
    stale_payload["match_rationale"] = "Old stale rationale"
    stale_payload["duplicate_key"] = "testco|compensationanalyst|remote|1"
    stale_payload["job_posting_url"] = "https://example.com/jobs/analyst"

    insert_result = job_store.upsert_job(stale_payload)
    assert insert_result["status"] == "inserted"

    monkeypatch.setattr(
        runtime,
        "load_scoring_profile_text",
        lambda: ("Executive Summary:\nExecutive technology leader", "Settings -> Profile Context"),
    )
    monkeypatch.setattr(
        runtime,
        "score_accepted_job",
        lambda payload, resume_profile_text: {
            "status": "scored",
            "fit_score": 18,
            "confidence": "High",
            "match_summary": "Role is not aligned to the executive technology target.",
            "match_reasons": ["Technology leadership evidence does not match analyst scope."],
            "gaps_or_risks": ["Title appears far below selected executive levels"],
        },
    )
    monkeypatch.setattr(
        runtime,
        "scrub_accepted_job",
        lambda payload, resume_profile_text: {
            "scrub_status": "reject",
            "scrub_flags": ["Clear level mismatch"],
        },
    )

    result = runtime.rescore_existing_jobs()

    assert result["rescored_count"] == 1
    assert result["changed_count"] == 1

    existing = job_store.get_existing_job_by_duplicate_key(stale_payload["duplicate_key"])
    assert existing["fit_score"] == 18
    assert existing["ai_priority"] == "Skip"
    assert "Clear level mismatch" in existing["risk_flags"]


def test_rescore_existing_jobs_respects_limit(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.pipeline_runtime as runtime

    first_payload = dict(sample_job_payload)
    first_payload["title"] = "Compensation Analyst"
    first_payload["normalized_title"] = "Compensation Analyst"
    first_payload["fit_score"] = 91
    first_payload["duplicate_key"] = "testco|compensationanalyst|remote|1"
    first_payload["job_posting_url"] = "https://example.com/jobs/analyst"
    job_store.upsert_job(first_payload)

    second_payload = dict(sample_job_payload)
    second_payload["title"] = "Senior Director Technology"
    second_payload["normalized_title"] = "Senior Director Technology"
    second_payload["fit_score"] = 88
    second_payload["duplicate_key"] = "testco|seniordirectortechnology|remote|2"
    second_payload["job_posting_url"] = "https://example.com/jobs/director"
    job_store.upsert_job(second_payload)

    monkeypatch.setattr(
        runtime,
        "load_scoring_profile_text",
        lambda: ("Executive Summary:\nExecutive technology leader", "Settings -> Profile Context"),
    )
    monkeypatch.setattr(
        runtime,
        "score_accepted_job",
        lambda payload, resume_profile_text: {
            "status": "scored",
            "fit_score": 22,
            "confidence": "High",
            "match_summary": f"Rescored {payload.get('title')}",
            "match_reasons": ["Rescored"],
            "gaps_or_risks": ["Updated during test"],
        },
    )
    monkeypatch.setattr(
        runtime,
        "scrub_accepted_job",
        lambda payload, resume_profile_text: {
            "scrub_status": "review",
            "scrub_flags": ["Limited rescore test"],
        },
    )

    result = runtime.rescore_existing_jobs(limit=1)

    assert result["total_considered"] == 1
    assert result["rescored_count"] == 1

    first_existing = job_store.get_existing_job_by_duplicate_key(first_payload["duplicate_key"])
    second_existing = job_store.get_existing_job_by_duplicate_key(second_payload["duplicate_key"])

    rescored_scores = {first_existing["fit_score"], second_existing["fit_score"]}
    assert 22 in rescored_scores
    assert 88 in rescored_scores or 91 in rescored_scores
