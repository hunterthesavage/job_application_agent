from __future__ import annotations

from services.source_layer_import import import_employer_endpoints
from services.source_layer_legacy_smoke import LEGACY_SOURCE_EXPORT_PATH
from services.source_layer_shadow_smoke import (
    build_source_layer_comparison_summary,
    format_source_layer_comparison_summary,
)


def populate_shadow_from_legacy_export() -> dict:
    import_summary = import_employer_endpoints(LEGACY_SOURCE_EXPORT_PATH)
    comparison_summary = build_source_layer_comparison_summary()
    return {
        "legacy_import": import_summary,
        "comparison": comparison_summary,
    }


def format_shadow_population_summary(summary: dict) -> str:
    import_summary = summary["legacy_import"]
    comparison_summary = summary["comparison"]

    return "\n\n".join(
        [
            "Shadow population from legacy export: PASS",
            "\n".join(
                [
                    f"legacy_import.status: {import_summary['status']}",
                    f"legacy_import.total_records: {import_summary['total_records']}",
                    f"legacy_import.endpoint_inserted: {import_summary['endpoint_inserted']}",
                    f"legacy_import.endpoint_updated: {import_summary['endpoint_updated']}",
                    f"legacy_import.skipped: {import_summary['skipped']}",
                    f"legacy_import.invalid: {import_summary['invalid']}",
                ]
            ),
            format_source_layer_comparison_summary(comparison_summary),
        ]
    )


def main() -> int:
    summary = populate_shadow_from_legacy_export()
    print(format_shadow_population_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
