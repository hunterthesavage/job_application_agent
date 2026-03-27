from services.source_layer_legacy_smoke import (
    LEGACY_SOURCE_EXPORT_PATH,
    REQUIRED_RECORD_FIELDS,
    REQUIRED_TOP_LEVEL_FIELDS,
    build_legacy_source_summary,
    load_legacy_source_export,
)


def test_legacy_source_export_smoke_contract_shape():
    payload = load_legacy_source_export(LEGACY_SOURCE_EXPORT_PATH)

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        assert field in payload

    records = payload["records"]
    assert isinstance(records, list)
    assert len(records) > 0

    first_record = records[0]
    for field in REQUIRED_RECORD_FIELDS:
        assert field in first_record


def test_legacy_source_export_smoke_summary():
    summary = build_legacy_source_summary(LEGACY_SOURCE_EXPORT_PATH)

    assert summary["schema_version"] == "1.0"
    assert summary["record_count"] > 0
    assert len(summary["first_company_names"]) > 0
