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


def test_run_shadow_endpoint_selection_prefers_supported_seed_vendors_for_next_gen(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('Supported Lever', 'supportedlever.com', 'Seattle', 1),
                ('Supported Greenhouse', 'supportedgreenhouse.com', 'Remote', 1),
                ('Unsupported Taleo', 'unsupportedtaleo.com', 'Seattle', 1)
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
            VALUES (?, 'https://jobs.lever.co/supportedlever', 'careers_page', 'lever', 'lever',
                    'legacy_import', 0.7, 0.7, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Business analyst Seattle roles')
            """,
            (company_ids["Supported Lever"],),
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
            VALUES (?, 'https://job-boards.greenhouse.io/supportedgreenhouse', 'careers_page', 'greenhouse', 'greenhouse',
                    'legacy_import', 0.65, 0.65, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Remote business analyst roles')
            """,
            (company_ids["Supported Greenhouse"],),
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
            VALUES (?, 'https://careers.example.com/unsupportedtaleo', 'careers_page', 'taleo / oracle recruiting', 'taleo',
                    'legacy_import', 0.99, 0.99, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Very strong business analyst Seattle endpoint')
            """,
            (company_ids["Unsupported Taleo"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "target_titles": "Business Analyst",
            "preferred_locations": "Seattle",
            "remote_only": "false",
        }
    )

    selected_vendors = [candidate["ats_vendor"] for candidate in result["selected_candidates"]]
    assert selected_vendors[:2] == ["lever", "greenhouse"]
    assert "Direct-source seed-supporting candidates: 2" in result["output"]


def test_run_shadow_endpoint_selection_prefers_high_confidence_validated_seed_pool(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('High Confidence Seed', 'highseed.com', 'Remote', 1),
                ('Low Confidence Seed', 'lowseed.com', 'Remote', 1),
                ('Another High Confidence Seed', 'anotherhighseed.com', 'Remote', 1)
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
            VALUES (?, 'https://highseed.wd1.myworkdayjobs.com/External', 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.95, 0.95, 'unreviewed', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of IT remote role')
            """,
            (company_ids["High Confidence Seed"],),
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
            VALUES (?, 'https://job-boards.greenhouse.io/anotherhighseed', 'careers_page', 'greenhouse', 'greenhouse',
                    'legacy_import', 0.90, 0.90, 'unreviewed', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President technology remote role')
            """,
            (company_ids["Another High Confidence Seed"],),
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
            VALUES (?, 'https://jobs.lever.co/lowseed', 'careers_page', 'lever', 'lever',
                    'legacy_import', 0.55, 0.55, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of IT remote role')
            """,
            (company_ids["Low Confidence Seed"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "_shadow_selection_cap": "2",
            "target_titles": "VP of IT",
            "preferred_locations": "",
            "remote_only": "true",
        }
    )

    selected_companies = [candidate["company_name"] for candidate in result["selected_candidates"]]
    assert selected_companies == ["High Confidence Seed", "Another High Confidence Seed"]
    assert result["preferred_next_gen_seed_count"] == 2
    assert "Preferred direct-source seed pool: 2" in result["output"]


def test_run_shadow_endpoint_selection_prefers_seedable_taleo_endpoint_shapes(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('Supported Taleo', 'supportedtaleo.com', 'Dallas', 1),
                ('Unsupported Taleo', 'unsupportedtaleo.com', 'Dallas', 1)
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
            VALUES (?, 'https://weyerhaeuser.taleo.net/careersection/10000/jobsearch.ftl', 'careers_page', 'taleo / oracle recruiting', 'taleo',
                    'legacy_import', 0.70, 0.70, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of IT Dallas roles')
            """,
            (company_ids["Supported Taleo"],),
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
            VALUES (?, 'https://uhg.taleo.net/careersection/careersection/privacyagreement/statementBeforeAuthentification.jsf', 'careers_page', 'taleo / oracle recruiting', 'taleo',
                    'legacy_import', 0.99, 0.99, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Very strong but unseedable endpoint')
            """,
            (company_ids["Unsupported Taleo"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "target_titles": "Vice President of IT",
            "preferred_locations": "Dallas",
            "remote_only": "false",
        }
    )

    assert result["selected_candidates"][0]["company_name"] == "Supported Taleo"
    assert "Direct-source seed-supporting candidates: 1" in result["output"]


def test_run_shadow_endpoint_selection_biases_workday_and_icims_for_senior_tech_search(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('High Score SuccessFactors', 'sfexample.com', 'Remote', 1),
                ('Workday Example', 'wdexample.com', 'Remote', 1),
                ('iCIMS Example', 'icimsexample.com', 'Remote', 1)
            """
        )
        companies = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
        company_ids = {row["name"]: row["id"] for row in companies}

        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://careers.example-successfactors.com/search/', 'careers_page', 'sap successfactors', 'successfactors',
                    'legacy_import', 0.99, 0.99, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["High Score SuccessFactors"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://workday-example.wd5.myworkdayjobs.com/Careers', 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.60, 0.60, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Technology leadership roles')
            """,
            (company_ids["Workday Example"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://careers-icims-example.icims.com/jobs', 'careers_page', 'icims', 'icims',
                    'legacy_import', 0.60, 0.60, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Infrastructure and platform roles')
            """,
            (company_ids["iCIMS Example"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        }
    )

    selected_companies = [candidate["company_name"] for candidate in result["selected_candidates"][:3]]
    assert selected_companies[:2] == ["Workday Example", "iCIMS Example"]
    assert "Direct-source ranking bias: senior technology leadership" in result["output"]


def test_run_shadow_endpoint_selection_diversifies_senior_tech_mix_across_ats_families(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        company_rows = [
            ("Workday 1", "workday1.com", "Remote"),
            ("Workday 2", "workday2.com", "Remote"),
            ("Workday 3", "workday3.com", "Remote"),
            ("Workday 4", "workday4.com", "Remote"),
            ("Workday 5", "workday5.com", "Remote"),
            ("Workday 6", "workday6.com", "Remote"),
            ("iCIMS 1", "icims1.com", "Remote"),
            ("SuccessFactors 1", "successfactors1.com", "Remote"),
            ("Taleo 1", "taleo1.com", "Remote"),
        ]
        conn.executemany(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES (?, ?, ?, 1)
            """,
            company_rows,
        )
        companies = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
        company_ids = {row["name"]: row["id"] for row in companies}

        for index in range(1, 7):
            conn.execute(
                """
                INSERT INTO hiring_endpoints (
                    company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                    discovery_source, confidence_score, health_score, review_status,
                    careers_url_status, is_primary, last_validated_at, active, notes
                )
                VALUES (?, ?, 'careers_page', 'workday', 'workday',
                        'legacy_import', 0.95, 0.95, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                        'Vice President of Information Technology remote roles')
                """,
                (
                    company_ids[f"Workday {index}"],
                    f"https://workday-{index}.wd5.myworkdayjobs.com/Careers",
                ),
            )

        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://careers-icims-example.icims.com/jobs', 'careers_page', 'icims', 'icims',
                    'legacy_import', 0.70, 0.70, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Infrastructure and platform leadership roles')
            """,
            (company_ids["iCIMS 1"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://careers-successfactors-example.jobs.example/search/', 'careers_page', 'sap successfactors', 'successfactors',
                    'legacy_import', 0.70, 0.70, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["SuccessFactors 1"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://taleo-example.taleo.net/careersection/10000/jobsearch.ftl', 'careers_page', 'taleo / oracle recruiting', 'taleo',
                    'legacy_import', 0.70, 0.70, 'needs_review', 'candidate', 1, '2026-03-26T10:00:00Z', 1,
                    'Technology vice president roles')
            """,
            (company_ids["Taleo 1"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "_shadow_selection_cap": "6",
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        }
    )

    selected_vendors = [candidate["ats_vendor"] for candidate in result["selected_candidates"]]
    assert "workday" in selected_vendors
    assert "icims" in selected_vendors
    assert "sap successfactors" in selected_vendors
    assert "taleo / oracle recruiting" in selected_vendors
    assert "Direct-source ATS mix profile: diversified senior tech" in result["output"]


def test_run_shadow_endpoint_selection_prefers_higher_quality_seed_shapes(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('Strong Workday', 'strongwd.com', 'Remote', 1),
                ('Weak Workday', 'weakwd.com', 'Remote', 1),
                ('Strong iCIMS', 'strongicims.com', 'Remote', 1),
                ('Weak iCIMS', 'weakicims.com', 'Remote', 1)
            """
        )
        companies = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
        company_ids = {row["name"]: row["id"] for row in companies}

        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://strongwd.wd5.myworkdayjobs.com/Careers', 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.80, 0.80, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["Strong Workday"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://weakwd.wd1.myworkdayjobs.com/en-US/External/login', 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.99, 0.99, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["Weak Workday"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://strong-icims.icims.com/jobs', 'careers_page', 'icims', 'icims',
                    'legacy_import', 0.80, 0.80, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Technology leadership roles')
            """,
            (company_ids["Strong iCIMS"],),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://weak-icims.icims.com/job-scams', 'careers_page', 'icims', 'icims',
                    'legacy_import', 0.99, 0.99, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Technology leadership roles')
            """,
            (company_ids["Weak iCIMS"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "_shadow_selection_cap": "4",
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        }
    )

    selected_companies = [candidate["company_name"] for candidate in result["selected_candidates"]]
    assert selected_companies.index("Strong Workday") < selected_companies.index("Weak Workday")
    assert selected_companies.index("Strong iCIMS") < selected_companies.index("Weak iCIMS")


def test_run_shadow_endpoint_selection_avoids_duplicate_seed_endpoint_urls(temp_db_path):
    import services.source_layer_shadow as shadow

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO companies (name, canonical_domain, hq, active)
            VALUES
                ('Company A', 'companya.com', 'Remote', 1),
                ('Company B', 'companyb.com', 'Remote', 1),
                ('Company C', 'companyc.com', 'Remote', 1)
            """
        )
        companies = conn.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
        company_ids = {row["name"]: row["id"] for row in companies}

        shared_endpoint = "https://sharedtenant.wd5.myworkdayjobs.com/Careers"
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, ?, 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.95, 0.95, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["Company A"], shared_endpoint),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, ?, 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.95, 0.95, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["Company B"], shared_endpoint),
        )
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id, endpoint_url, endpoint_type, ats_vendor, extraction_method,
                discovery_source, confidence_score, health_score, review_status,
                careers_url_status, is_primary, last_validated_at, active, notes
            )
            VALUES (?, 'https://unique.wd5.myworkdayjobs.com/Careers', 'careers_page', 'workday', 'workday',
                    'legacy_import', 0.90, 0.90, 'approved', 'validated', 1, '2026-03-26T10:00:00Z', 1,
                    'Vice President of Information Technology remote roles')
            """,
            (company_ids["Company C"],),
        )
        conn.commit()
    finally:
        conn.close()

    result = shadow.run_shadow_endpoint_selection(
        {
            "_source_layer_mode": "next_gen",
            "_shadow_selection_cap": "3",
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "false",
        }
    )

    endpoints = [candidate["endpoint_url"] for candidate in result["selected_candidates"]]
    assert endpoints.count(shared_endpoint) == 1
