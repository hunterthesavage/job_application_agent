import sqlite3


def test_build_source_layer_status_summary(temp_db_path):
    import services.source_layer_status_smoke as smoke

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, active)
            VALUES ('Walmart', 'walmart.com', 1)
            """
        )
        company_id = conn.execute("SELECT id FROM companies LIMIT 1").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id,
                endpoint_url,
                endpoint_type,
                ats_vendor,
                extraction_method,
                discovery_source,
                confidence_score,
                health_score,
                review_status,
                careers_url_status,
                is_primary,
                last_validated_at,
                active,
                notes
            )
            VALUES (?, 'https://careers.walmart.com', 'careers_page', 'custom', 'careers_page',
                    'legacy_import', 0.8, 0.8, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1, 'ok')
            """,
            (company_id,),
        )
        conn.execute(
            """
            INSERT INTO source_layer_runs (
                mode,
                import_file_path,
                imported_records,
                errors,
                notes
            )
            VALUES ('import', '/tmp/file.json', 1, 0, 'Imported 1 endpoint.')
            """
        )
        conn.commit()
    finally:
        conn.close()

    summary = smoke.build_source_layer_status_summary()

    assert summary["legacy"]["status"] == "current_source_of_truth"
    assert summary["shadow"]["company_count"] == 1
    assert summary["shadow"]["active_endpoint_count"] == 1
    assert summary["shadow"]["approved_endpoint_count"] == 1
    assert summary["next_gen"]["status"] == "seed_experiment"
    assert "seed URLs" in summary["next_gen"]["note"]
    assert summary["latest_run"]["mode"] == "import"


def test_format_source_layer_status_summary():
    import services.source_layer_status_smoke as smoke

    output = smoke.format_source_layer_status_summary(
        {
            "legacy": {"status": "current_source_of_truth"},
            "shadow": {
                "company_count": 1,
                "endpoint_count": 2,
                "active_endpoint_count": 2,
                "approved_endpoint_count": 1,
            },
            "next_gen": {
                "status": "seed_experiment",
                "note": "Legacy discovery stays primary, and supported source-layer seed URLs are added when available.",
            },
            "latest_run": {
                "mode": "import",
                "imported_records": 2,
                "errors": 0,
                "notes": "Imported 2 endpoint records.",
            },
        }
    )

    assert "legacy.status: current_source_of_truth" in output
    assert "shadow.endpoint_count: 2" in output
    assert "next_gen.status: seed_experiment" in output
    assert "next_gen.note: Legacy discovery stays primary" in output
    assert "latest_run.mode: import" in output
