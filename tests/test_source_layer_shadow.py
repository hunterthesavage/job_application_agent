import sqlite3


def test_run_shadow_endpoint_selection_returns_selected_candidates(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('Rover', 'rover.com', 'Seattle', 1),
                ('Checkr', 'checkr.com', 'Remote', 1)
            """
        )
        companies = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
        company_ids = {row["name"]: row["id"] for row in companies}

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
            VALUES (?, 'https://jobs.lever.co/rover', 'careers_page', 'lever', 'lever',
                    'legacy_import', 0.9, 0.9, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Business analyst and Seattle roles')
            """,
            (company_ids["Rover"],),
        )
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
            VALUES (?, 'https://job-boards.greenhouse.io/checkr', 'careers_page', 'greenhouse', 'greenhouse',
                    'legacy_import', 0.7, 0.7, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Remote friendly operations roles')
            """,
            (company_ids["Checkr"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "target_titles": "Business Analyst",
            "preferred_locations": "Seattle",
            "remote_only": "false",
        }
    )

    assert result["active_endpoint_count"] == 2
    assert result["selected_endpoint_count"] == 2
    assert result["approved_endpoint_count"] == 1
    assert "Rover" in result["selected_company_names"]
    assert "Selected shadow candidates: 2" in result["output"]

