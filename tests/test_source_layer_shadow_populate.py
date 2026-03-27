import services.source_layer_shadow_populate as populate


def test_populate_shadow_from_legacy_export(monkeypatch):
    monkeypatch.setattr(
        populate,
        "import_employer_endpoints",
        lambda path: {
            "status": "completed",
            "total_records": 473,
            "endpoint_inserted": 300,
            "endpoint_updated": 12,
            "skipped": 150,
            "invalid": 11,
        },
    )
    monkeypatch.setattr(
        populate,
        "build_source_layer_comparison_summary",
        lambda: {
            "legacy": {"schema_version": "1.0", "record_count": 473, "first_company_names": ["Walmart"]},
            "shadow": {
                "active_endpoint_count": 312,
                "approved_endpoint_count": 200,
                "candidate_endpoint_count": 50,
            },
            "delta": {"missing_from_shadow_count": 161},
            "next_gen": {"status": "not_enabled", "note": "next_gen remains gated; live discovery still falls back to legacy."},
        },
    )

    summary = populate.populate_shadow_from_legacy_export()

    assert summary["legacy_import"]["endpoint_inserted"] == 300
    assert summary["comparison"]["shadow"]["active_endpoint_count"] == 312


def test_format_shadow_population_summary():
    summary = {
        "legacy_import": {
            "status": "completed",
            "total_records": 473,
            "endpoint_inserted": 300,
            "endpoint_updated": 12,
            "skipped": 150,
            "invalid": 11,
        },
        "comparison": {
            "legacy": {"schema_version": "1.0", "record_count": 473, "first_company_names": ["Walmart"]},
            "shadow": {
                "active_endpoint_count": 312,
                "approved_endpoint_count": 200,
                "candidate_endpoint_count": 50,
            },
            "delta": {"missing_from_shadow_count": 161},
            "next_gen": {"status": "not_enabled", "note": "next_gen remains gated; live discovery still falls back to legacy."},
        },
    }

    output = populate.format_shadow_population_summary(summary)

    assert "Shadow population from legacy export: PASS" in output
    assert "legacy_import.endpoint_inserted: 300" in output
    assert "shadow.active_endpoint_count: 312" in output
    assert "next_gen.status: not_enabled" in output
