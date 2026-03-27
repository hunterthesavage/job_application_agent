import services.source_layer_shadow_smoke as smoke


def test_build_source_layer_comparison_summary(monkeypatch):
    monkeypatch.setattr(
        smoke,
        "build_legacy_source_summary",
        lambda: {
            "schema_version": "1.0",
            "record_count": 473,
            "first_company_names": ["Walmart", "Amazon.com"],
        },
    )
    monkeypatch.setattr(
        smoke,
        "run_shadow_endpoint_selection",
        lambda: {
            "active_endpoint_count": 12,
            "approved_endpoint_count": 7,
            "candidate_endpoint_count": 3,
            "primary_endpoint_count": 5,
            "ats_counts": {"greenhouse": 4},
            "output": "Next-gen source layer shadow summary",
        },
    )

    summary = smoke.build_source_layer_comparison_summary()

    assert summary["legacy"]["record_count"] == 473
    assert summary["shadow"]["active_endpoint_count"] == 12
    assert summary["delta"]["missing_from_shadow_count"] == 461
    assert summary["next_gen"]["status"] == "not_enabled"


def test_format_source_layer_comparison_summary_contains_modes():
    summary = {
        "legacy": {
            "schema_version": "1.0",
            "record_count": 473,
            "first_company_names": ["Walmart", "Amazon.com"],
        },
        "shadow": {
            "active_endpoint_count": 12,
            "approved_endpoint_count": 7,
            "candidate_endpoint_count": 3,
        },
        "delta": {
            "missing_from_shadow_count": 461,
        },
        "next_gen": {
            "status": "not_enabled",
            "note": "next_gen remains gated; live discovery still falls back to legacy.",
        },
    }

    output = smoke.format_source_layer_comparison_summary(summary)

    assert "legacy.schema_version: 1.0" in output
    assert "shadow.active_endpoint_count: 12" in output
    assert "next_gen.status: not_enabled" in output
