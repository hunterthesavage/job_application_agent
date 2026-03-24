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


def test_rescore_existing_jobs_respects_stale_days(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.pipeline_runtime as runtime
    from services.db import db_connection

    stale_payload = dict(sample_job_payload)
    stale_payload["title"] = "Compensation Analyst"
    stale_payload["normalized_title"] = "Compensation Analyst"
    stale_payload["fit_score"] = 91
    stale_payload["duplicate_key"] = "testco|compensationanalyst|remote|1"
    stale_payload["job_posting_url"] = "https://example.com/jobs/analyst"
    job_store.upsert_job(stale_payload)

    fresh_payload = dict(sample_job_payload)
    fresh_payload["title"] = "VP Technology"
    fresh_payload["normalized_title"] = "VP Technology"
    fresh_payload["fit_score"] = 77
    fresh_payload["duplicate_key"] = "testco|vptechnology|remote|2"
    fresh_payload["job_posting_url"] = "https://example.com/jobs/vp-tech"
    job_store.upsert_job(fresh_payload)

    with db_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET updated_at = datetime('now', '-45 days')
            WHERE duplicate_key = ?
            """,
            (stale_payload["duplicate_key"],),
        )
        conn.execute(
            """
            UPDATE jobs
            SET updated_at = datetime('now', '-2 days')
            WHERE duplicate_key = ?
            """,
            (fresh_payload["duplicate_key"],),
        )

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
            "fit_score": 15 if payload.get("title") == "Compensation Analyst" else 70,
            "confidence": "High",
            "match_summary": f"Rescored {payload.get('title')}",
            "match_reasons": ["Rescored"],
            "gaps_or_risks": ["Updated during stale-days test"],
        },
    )
    monkeypatch.setattr(
        runtime,
        "scrub_accepted_job",
        lambda payload, resume_profile_text: {
            "scrub_status": "review",
            "scrub_flags": ["Stale filter test"],
        },
    )

    result = runtime.rescore_existing_jobs(stale_days=30)

    assert result["total_considered"] == 1
    assert result["rescored_count"] == 1
    assert "Rescore age filter: Older than 30 days" in result["output"]

    stale_existing = job_store.get_existing_job_by_duplicate_key(stale_payload["duplicate_key"])
    fresh_existing = job_store.get_existing_job_by_duplicate_key(fresh_payload["duplicate_key"])

    assert stale_existing["fit_score"] == 15
    assert fresh_existing["fit_score"] == 77


def test_rescore_existing_jobs_can_persist_scrub_field_corrections(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.pipeline_runtime as runtime

    stale_payload = dict(sample_job_payload)
    stale_payload["title"] = "VP Tech"
    stale_payload["company"] = "ExampleCo LLC"
    stale_payload["location"] = "Texas"
    stale_payload["compensation_raw"] = ""
    stale_payload["duplicate_key"] = "exampleco|vptech|remote|1"
    stale_payload["job_posting_url"] = "https://example.com/jobs/vp-tech"
    job_store.upsert_job(stale_payload)

    class _FakeJob:
        description_text = "Vice President of Technology at ExampleCo. Compensation: $220,000 - $260,000."
        job_posting_url = "https://example.com/jobs/vp-tech"
        company = "ExampleCo"
        title = "Vice President of Technology"
        normalized_title = "vice president of technology"
        role_family = "VP Technology"
        location = "Dallas, TX"
        compensation_raw = "$220,000 - $260,000"
        remote_type = ""
        dallas_dfw_match = "true"
        validation_status = "Validated"
        validation_confidence = "High"
        compensation_status = "Disclosed"

    monkeypatch.setattr(
        runtime,
        "load_scoring_profile_text",
        lambda: ("Executive Summary:\nExecutive technology leader", "Settings -> Profile Context"),
    )
    monkeypatch.setattr(runtime, "create_job_record", lambda job_url: _FakeJob())
    monkeypatch.setattr(
        runtime,
        "score_accepted_job",
        lambda payload, resume_profile_text: {
            "status": "scored",
            "fit_score": 84,
            "confidence": "High",
            "match_summary": "Strong executive technology fit.",
            "match_reasons": ["Rescored against refreshed page text."],
            "gaps_or_risks": [],
        },
    )
    monkeypatch.setattr(
        runtime,
        "scrub_accepted_job",
        lambda payload, resume_profile_text: {
            "scrub_status": "clean",
            "scrub_confidence": "High",
            "corrected_title": "Vice President of Technology",
            "corrected_company": "ExampleCo",
            "corrected_location": "Dallas, TX",
            "corrected_compensation_raw": "$220,000 - $260,000",
            "correction_confidence": "High",
            "correction_notes": ["Page header and compensation section were explicit."],
        },
    )

    result = runtime.rescore_existing_jobs()

    assert result["rescored_count"] == 1
    assert result["changed_count"] == 1
    assert "Live page refreshes succeeded: 1" in result["output"]

    existing = job_store.get_existing_job_by_duplicate_key(stale_payload["duplicate_key"])
    assert existing["title"] == "Vice President of Technology"
    assert existing["company"] == "ExampleCo"
    assert existing["location"] == "Dallas, TX"
    assert existing["compensation_raw"] == "$220,000 - $260,000"
    assert "Page header and compensation section were explicit." in existing["risk_flags"]


def test_rescore_existing_jobs_applies_parser_refresh_to_company_and_title(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.pipeline_runtime as runtime

    stale_payload = dict(sample_job_payload)
    stale_payload["title"] = "Myworkdayjobs - SVP Technology & Engineering"
    stale_payload["company"] = "Myworkdayjobs"
    stale_payload["location"] = "Remote"
    stale_payload["compensation_raw"] = ""
    stale_payload["duplicate_key"] = "myworkdayjobs|svptech|remote|1"
    stale_payload["job_posting_url"] = "https://example.com/jobs/workday"
    job_store.upsert_job(stale_payload)

    class _FakeJob:
        description_text = "SVP Technology & Engineering at Harris Computer."
        job_posting_url = "https://example.com/jobs/workday"
        company = "Harris Computer"
        title = "SVP Technology & Engineering"
        normalized_title = "svp technology engineering"
        role_family = "SVP Technology"
        location = "Remote - North Carolina, United States of America"
        compensation_raw = ""
        remote_type = "Fully Remote"
        dallas_dfw_match = "Yes"
        validation_status = "Validated"
        validation_confidence = "High"
        compensation_status = "Not Disclosed"

    monkeypatch.setattr(
        runtime,
        "load_scoring_profile_text",
        lambda: ("Executive Summary:\nExecutive technology leader", "Settings -> Profile Context"),
    )
    monkeypatch.setattr(runtime, "create_job_record", lambda job_url: _FakeJob())
    monkeypatch.setattr(
        runtime,
        "score_accepted_job",
        lambda payload, resume_profile_text: {
            "status": "scored",
            "fit_score": 70,
            "confidence": "High",
            "match_summary": "Strong enough fit after parser refresh.",
            "match_reasons": ["Refreshed against live page values."],
            "gaps_or_risks": [],
        },
    )
    monkeypatch.setattr(
        runtime,
        "scrub_accepted_job",
        lambda payload, resume_profile_text: {
            "scrub_status": "clean",
            "scrub_flags": [],
        },
    )

    result = runtime.rescore_existing_jobs()

    assert result["rescored_count"] == 1
    existing = job_store.get_existing_job_by_duplicate_key(stale_payload["duplicate_key"])
    assert existing["company"] == "Harris Computer"
    assert existing["title"] == "SVP Technology & Engineering"
    assert existing["location"] == "Remote - North Carolina, United States of America"
