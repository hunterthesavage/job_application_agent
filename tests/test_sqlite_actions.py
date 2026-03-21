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
