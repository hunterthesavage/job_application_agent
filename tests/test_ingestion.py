from dataclasses import dataclass


@dataclass
class DummyJob:
    date_found: str
    date_last_validated: str
    company: str
    title: str
    role_family: str
    normalized_title: str
    location: str
    remote_type: str
    dallas_dfw_match: str
    company_careers_url: str
    job_posting_url: str
    ats_type: str
    requisition_id: str
    source: str
    compensation_raw: str
    compensation_status: str
    validation_status: str
    validation_confidence: str
    fit_score: float
    fit_tier: str
    ai_priority: str
    match_rationale: str
    risk_flags: str
    application_angle: str
    cover_letter_starter: str
    status: str
    duplicate_key: str
    active_status: str


def build_dummy_job(suffix: str) -> DummyJob:
    return DummyJob(
        date_found="2026-03-20",
        date_last_validated="2026-03-20",
        company=f"TestCo{suffix}",
        title="VP Technology",
        role_family="Technology",
        normalized_title="VP Technology",
        location="Remote",
        remote_type="Remote",
        dallas_dfw_match="No",
        company_careers_url="https://example.com/careers",
        job_posting_url=f"https://example.com/jobs/{suffix}",
        ats_type="Greenhouse",
        requisition_id=f"REQ-{suffix}",
        source="Unit Test",
        compensation_raw="$250,000",
        compensation_status="Listed",
        validation_status="Valid",
        validation_confidence="High",
        fit_score=90.0,
        fit_tier="A",
        ai_priority="High",
        match_rationale="Strong match",
        risk_flags="",
        application_angle="Executive transformation",
        cover_letter_starter="I am excited",
        status="New",
        duplicate_key=f"testco|vptechnology|remote|{suffix}",
        active_status="Active",
    )


def test_ingestion_run_logging(temp_db_path, seeded_db):
    import services.ingestion as ingestion

    jobs = [build_dummy_job("1"), build_dummy_job("2")]
    summary = ingestion.ingest_job_records(
        job_records=jobs,
        source_name="unit_test",
        source_detail="pytest",
        run_type="ingest_jobs",
    )

    assert summary["total_seen"] == 2
    assert summary["inserted_count"] == 2
    assert summary["updated_count"] == 0
    assert summary["error_count"] == 0

    row = seeded_db.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()
    assert row[0] == 1

    row = seeded_db.execute("SELECT COUNT(*) FROM ingestion_run_items").fetchone()
    assert row[0] == 2
