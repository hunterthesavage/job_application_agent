def test_upsert_job_inserts_new(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store

    result = job_store.upsert_job(sample_job_payload)

    assert result["status"] == "inserted"
    assert result["job_id"] is not None


def test_upsert_job_updates_existing(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store

    first = job_store.upsert_job(sample_job_payload)
    updated_payload = dict(sample_job_payload)
    updated_payload["fit_score"] = 77
    updated_payload["title"] = "VP Technology Updated"

    second = job_store.upsert_job(updated_payload)

    assert second["status"] == "updated"
    assert second["job_id"] == first["job_id"]

    existing = job_store.get_existing_job_by_duplicate_key(updated_payload["duplicate_key"])
    assert existing["title"] == "VP Technology Updated"


def test_upsert_job_skips_removed_duplicate(temp_db_path, seeded_db, sample_job_payload):
    import services.job_store as job_store

    seeded_db.execute(
        """
        INSERT INTO removed_jobs (
            removed_date,
            duplicate_key,
            company,
            title,
            location,
            job_posting_url,
            removal_reason,
            source_sheet
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-03-20",
            sample_job_payload["duplicate_key"],
            sample_job_payload["company"],
            sample_job_payload["title"],
            sample_job_payload["location"],
            sample_job_payload["job_posting_url"],
            "Removed in test",
            "Test",
        ),
    )
    seeded_db.commit()

    result = job_store.upsert_job(sample_job_payload)

    assert result["status"] == "skipped_removed"
    assert result["job_id"] is None


def test_update_job_scoring_fields_updates_only_scoring_columns(temp_db_path, sample_job_payload):
    import services.job_store as job_store

    inserted = job_store.upsert_job(sample_job_payload)
    job_id = inserted["job_id"]

    updated_payload = dict(sample_job_payload)
    updated_payload["fit_score"] = 42
    updated_payload["fit_tier"] = "Weak"
    updated_payload["ai_priority"] = "Hold"
    updated_payload["match_rationale"] = "Rescored rationale"
    updated_payload["risk_flags"] = "Level mismatch"
    updated_payload["application_angle"] = "Updated angle"

    job_store.update_job_scoring_fields(job_id, updated_payload)

    existing = job_store.get_existing_job_by_duplicate_key(sample_job_payload["duplicate_key"])
    assert existing["fit_score"] == 42
    assert existing["fit_tier"] == "Weak"
    assert existing["ai_priority"] == "Hold"
    assert existing["match_rationale"] == "Rescored rationale"
    assert existing["risk_flags"] == "Level mismatch"
    assert existing["application_angle"] == "Updated angle"
