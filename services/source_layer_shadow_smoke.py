from __future__ import annotations

from services.source_layer_legacy_smoke import build_legacy_source_summary
from services.source_layer_shadow import run_shadow_endpoint_selection


def build_source_layer_comparison_summary() -> dict:
    legacy_summary = build_legacy_source_summary()
    shadow_summary = run_shadow_endpoint_selection()

    legacy_record_count = int(legacy_summary["record_count"])
    shadow_endpoint_count = int(shadow_summary["active_endpoint_count"])

    return {
        "legacy": legacy_summary,
        "shadow": shadow_summary,
        "next_gen": {
            "status": "not_enabled",
            "note": "next_gen remains gated; live discovery still falls back to legacy.",
        },
        "delta": {
            "legacy_record_count": legacy_record_count,
            "shadow_endpoint_count": shadow_endpoint_count,
            "missing_from_shadow_count": max(legacy_record_count - shadow_endpoint_count, 0),
        },
    }


def format_source_layer_comparison_summary(summary: dict) -> str:
    legacy = summary["legacy"]
    shadow = summary["shadow"]
    delta = summary["delta"]
    next_gen = summary["next_gen"]

    legacy_company_names = ", ".join(legacy["first_company_names"]) or "(none)"

    return "\n".join(
        [
            "Source layer comparison smoke test: PASS",
            f"legacy.schema_version: {legacy['schema_version']}",
            f"legacy.record_count: {legacy['record_count']}",
            f"legacy.first_company_names: {legacy_company_names}",
            f"shadow.active_endpoint_count: {shadow['active_endpoint_count']}",
            f"shadow.approved_endpoint_count: {shadow['approved_endpoint_count']}",
            f"shadow.candidate_endpoint_count: {shadow['candidate_endpoint_count']}",
            f"delta.missing_from_shadow_count: {delta['missing_from_shadow_count']}",
            f"next_gen.status: {next_gen['status']}",
            f"next_gen.note: {next_gen['note']}",
        ]
    )


def main() -> int:
    summary = build_source_layer_comparison_summary()
    print(format_source_layer_comparison_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
