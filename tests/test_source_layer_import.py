import json
import sqlite3


def _write_contract_file(path, records, *, schema_version="1.0"):
    payload = {
        "schema_version": schema_version,
        "generated_at": "2026-03-25T12:00:00Z",
        "source_repo": "fortune-500-career-pages",
        "records": records,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_initialize_database_creates_source_layer_tables(temp_db_path):
    conn = sqlite3.connect(temp_db_path)
    try:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "companies" in table_names
    assert "hiring_endpoints" in table_names
    assert "endpoint_validation_runs" in table_names
    assert "source_layer_runs" in table_names


def test_import_employer_endpoints_imports_valid_rows(temp_db_path, tmp_path):
    from services.source_layer_import import import_employer_endpoints

    import_file = tmp_path / "validated_employer_endpoints.json"
    _write_contract_file(
        import_file,
        [
            {
                "company_name": "Xapo Bank",
                "canonical_company_domain": "xapo.com",
                "careers_url": "https://job-boards.greenhouse.io/xapo61",
                "careers_url_status": "validated",
                "review_status": "approved",
                "ats_provider": "greenhouse",
                "confidence_score": 0.94,
                "last_validated_at": "2026-03-25T11:54:00Z",
                "confidence_reason": "Validated greenhouse endpoint",
            }
        ],
    )

    summary = import_employer_endpoints(import_file)

    assert summary["status"] == "completed"
    assert summary["company_inserted"] == 1
    assert summary["endpoint_inserted"] == 1
    assert summary["invalid"] == 0
    assert summary["skipped"] == 0

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        company = conn.execute("SELECT * FROM companies").fetchone()
        endpoint = conn.execute("SELECT * FROM hiring_endpoints").fetchone()
        run_row = conn.execute("SELECT * FROM source_layer_runs").fetchone()
    finally:
        conn.close()

    assert company["name"] == "Xapo Bank"
    assert company["canonical_domain"] == "xapo.com"
    assert endpoint["endpoint_url"] == "https://job-boards.greenhouse.io/xapo61"
    assert endpoint["ats_vendor"] == "greenhouse"
    assert endpoint["careers_url_status"] == "validated"
    assert run_row["mode"] == "import"


def test_import_employer_endpoints_skips_invalid_and_non_importable_rows(temp_db_path, tmp_path):
    from services.source_layer_import import import_employer_endpoints

    import_file = tmp_path / "validated_employer_endpoints.json"
    _write_contract_file(
        import_file,
        [
            {
                "company_name": "No Url Co",
                "canonical_company_domain": "nourl.com",
                "careers_url": "",
                "careers_url_status": "validated",
                "review_status": "approved",
                "ats_provider": "greenhouse",
                "confidence_score": 0.8,
                "last_validated_at": "2026-03-25T11:54:00Z",
            },
            {
                "company_name": "Blocked Co",
                "canonical_company_domain": "blocked.com",
                "careers_url": "https://blocked.com/careers",
                "careers_url_status": "blocked",
                "review_status": "approved",
                "ats_provider": "custom",
                "confidence_score": 0.4,
                "last_validated_at": "2026-03-25T11:54:00Z",
            },
            {
                "company_name": "Broken Score Co",
                "canonical_company_domain": "broken.com",
                "careers_url": "https://broken.com/careers",
                "careers_url_status": "validated",
                "review_status": "approved",
                "ats_provider": "custom",
                "confidence_score": "not-a-number",
                "last_validated_at": "2026-03-25T11:54:00Z",
            },
        ],
    )

    summary = import_employer_endpoints(import_file)

    assert summary["endpoint_inserted"] == 0
    assert summary["skipped"] == 1
    assert summary["invalid"] == 2

    conn = sqlite3.connect(temp_db_path)
    try:
        company_count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        endpoint_count = conn.execute("SELECT COUNT(*) FROM hiring_endpoints").fetchone()[0]
    finally:
        conn.close()

    assert company_count == 0
    assert endpoint_count == 0


def test_import_employer_endpoints_updates_existing_rows_without_duplicates(temp_db_path, tmp_path):
    from services.source_layer_import import import_employer_endpoints

    import_file = tmp_path / "validated_employer_endpoints.json"
    _write_contract_file(
        import_file,
        [
            {
                "company_name": "Xapo Bank",
                "canonical_company_domain": "xapo.com",
                "careers_url": "https://job-boards.greenhouse.io/xapo61",
                "careers_url_status": "validated",
                "review_status": "approved",
                "ats_provider": "greenhouse",
                "confidence_score": 0.9,
                "last_validated_at": "2026-03-25T11:54:00Z",
            }
        ],
    )

    first = import_employer_endpoints(import_file)
    assert first["company_inserted"] == 1
    assert first["endpoint_inserted"] == 1

    _write_contract_file(
        import_file,
        [
            {
                "company_name": "Xapo Bank",
                "canonical_company_domain": "xapo.com",
                "careers_url": "https://job-boards.greenhouse.io/xapo61",
                "careers_url_status": "candidate",
                "review_status": "needs_review",
                "ats_provider": "greenhouse",
                "confidence_score": 0.77,
                "last_validated_at": "2026-03-26T08:00:00Z",
                "notes": "Confidence dropped during revalidation",
            }
        ],
    )

    second = import_employer_endpoints(import_file)
    assert second["company_updated"] == 1
    assert second["endpoint_updated"] == 1

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        company_count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        endpoint_count = conn.execute("SELECT COUNT(*) FROM hiring_endpoints").fetchone()[0]
        endpoint = conn.execute("SELECT * FROM hiring_endpoints").fetchone()
    finally:
        conn.close()

    assert company_count == 1
    assert endpoint_count == 1
    assert endpoint["careers_url_status"] == "candidate"
    assert endpoint["review_status"] == "needs_review"
    assert endpoint["confidence_score"] == 0.77
