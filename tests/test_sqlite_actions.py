from datetime import datetime


def test_mark_job_as_applied(temp_db_path, sample_job_payload):
    import services.job_store as job_store
    import services.sqlite_actions as actions

    inserted = job_store.upsert_job(sample_job_payload)
    updated = actions.mark_job_as_applied(inserted["job_id"])

    assert updated["workflow_status"] == "Applied"
    assert updated["status"] == "Applied"
    assert updated["applied_date"] == datetime.now().strftime("%Y-%m-%d")


def test_remove_job_moves_to_removed(temp_db_path, seeded_db, sample_job_payload):
    import services.job_store as job_store
    import services.sqlite_actions as actions

    inserted = job_store.upsert_job(sample_job_payload)
    removed = actions.remove_job(inserted["job_id"])

    assert removed["duplicate_key"] == sample_job_payload["duplicate_key"]

    row = seeded_db.execute(
        "SELECT COUNT(*) FROM jobs WHERE duplicate_key = ?",
        (sample_job_payload["duplicate_key"],),
    ).fetchone()
    assert row[0] == 0

    row = seeded_db.execute(
        "SELECT COUNT(*) FROM removed_jobs WHERE duplicate_key = ?",
        (sample_job_payload["duplicate_key"],),
    ).fetchone()
    assert row[0] == 1


def test_record_cover_letter_artifact(temp_db_path, seeded_db, sample_job_payload):
    import services.job_store as job_store
    import services.sqlite_actions as actions

    inserted = job_store.upsert_job(sample_job_payload)
    output_path = "/tmp/TestCo_Cover_Letter.txt"
    updated = actions.record_cover_letter_artifact(inserted["job_id"], output_path)

    assert updated["cover_letter_path"] == output_path

    row = seeded_db.execute(
        "SELECT COUNT(*) FROM cover_letter_artifacts WHERE output_path = ?",
        (output_path,),
    ).fetchone()
    assert row[0] == 1


def test_rescore_job_updates_scoring_fields(temp_db_path, seeded_db, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.sqlite_actions as actions

    inserted = job_store.upsert_job(sample_job_payload)
    job_id = inserted["job_id"]

    monkeypatch.setattr(
        actions,
        "load_scoring_profile_text",
        lambda: ("Executive Summary: VP technology leader", "Settings -> Profile Context"),
    )
    monkeypatch.setattr(
        actions,
        "score_accepted_job",
        lambda payload, profile_text: {
            "status": "scored",
            "fit_score": 88,
            "confidence": "High",
            "match_summary": "Strong executive technology fit.",
            "match_reasons": ["Executive technology leadership", "Transformation delivery"],
            "gaps_or_risks": ["Industry depth not explicit"],
        },
    )
    monkeypatch.setattr(
        actions,
        "scrub_accepted_job",
        lambda payload, profile_text: {
            "status": "scrubbed",
            "scrub_status": "review",
            "scrub_summary": "Level looks right but the JD is a little thin.",
            "scrub_flags": ["Thin JD evidence"],
            "scrub_confidence": "Medium",
        },
    )

    updated = actions.rescore_job(job_id)

    assert updated["fit_score"] == 88
    assert updated["fit_tier"] == "Strong"
    assert updated["ai_priority"] == "Hold"
    assert updated["match_rationale"] == "Strong executive technology fit."
    assert "Industry depth not explicit" in updated["risk_flags"]
    assert "Thin JD evidence" in updated["risk_flags"]


def test_rescore_job_requires_profile_context(temp_db_path, sample_job_payload, monkeypatch):
    import services.job_store as job_store
    import services.sqlite_actions as actions

    inserted = job_store.upsert_job(sample_job_payload)

    monkeypatch.setattr(actions, "load_scoring_profile_text", lambda: ("", ""))

    try:
        actions.rescore_job(inserted["job_id"])
    except ValueError as exc:
        assert "Profile Context" in str(exc)
    else:
        raise AssertionError("Expected rescore_job to require profile context.")
