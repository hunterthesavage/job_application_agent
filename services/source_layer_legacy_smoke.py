from __future__ import annotations

import json
from pathlib import Path


LEGACY_SOURCE_EXPORT_PATH = Path(
    "/Users/hunter/Documents/New project/data/output/validated_employer_endpoints.json"
)

REQUIRED_TOP_LEVEL_FIELDS = (
    "schema_version",
    "generated_at",
    "source_repo",
    "records",
)

REQUIRED_RECORD_FIELDS = (
    "company_name",
    "canonical_company_domain",
    "careers_url",
    "careers_url_status",
    "review_status",
    "ats_provider",
    "confidence_score",
    "last_validated_at",
)


def load_legacy_source_export(file_path: str | Path = LEGACY_SOURCE_EXPORT_PATH) -> dict:
    path = Path(file_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            raise ValueError(f"Legacy source export missing top-level field: {field}")

    records = payload["records"]
    if not isinstance(records, list):
        raise ValueError("Legacy source export 'records' must be a list.")
    if not records:
        raise ValueError("Legacy source export must contain at least one record.")

    for field in REQUIRED_RECORD_FIELDS:
        if field not in records[0]:
            raise ValueError(f"Legacy source export first record missing required field: {field}")

    return payload


def build_legacy_source_summary(file_path: str | Path = LEGACY_SOURCE_EXPORT_PATH) -> dict:
    payload = load_legacy_source_export(file_path)
    records = payload["records"]

    first_company_names = [
        str(record.get("company_name", "") or "").strip()
        for record in records[:5]
        if str(record.get("company_name", "") or "").strip()
    ]

    return {
        "schema_version": str(payload["schema_version"]),
        "record_count": len(records),
        "first_company_names": first_company_names,
    }


def format_legacy_source_summary(summary: dict) -> str:
    company_names = ", ".join(summary["first_company_names"]) or "(none)"
    return "\n".join(
        [
            "Legacy source export smoke test: PASS",
            f"schema_version: {summary['schema_version']}",
            f"record_count: {summary['record_count']}",
            f"first_company_names: {company_names}",
        ]
    )


def main() -> int:
    summary = build_legacy_source_summary()
    print(format_legacy_source_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
