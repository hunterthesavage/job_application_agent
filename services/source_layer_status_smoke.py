from __future__ import annotations

import re

from services.db import db_connection


def _extract_note_int(notes: str, label: str) -> int:
    match = re.search(rf"{re.escape(label)}:\s*(\d+)", str(notes or ""))
    if not match:
        return 0
    return int(match.group(1))


def _extract_note_int_any(notes: str, *labels: str) -> int:
    for label in labels:
        value = _extract_note_int(notes, label)
        if value:
            return value
    return 0


def _extract_note_text(notes: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*(.*?)(?:\.|$)", str(notes or ""))
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _extract_note_text_any(notes: str, *labels: str) -> str:
    for label in labels:
        value = _extract_note_text(notes, label)
        if value:
            return value
    return ""


def build_source_layer_status_summary() -> dict:
    with db_connection() as conn:
        company_count = int(conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0])
        endpoint_count = int(conn.execute("SELECT COUNT(*) FROM hiring_endpoints").fetchone()[0])
        active_endpoint_count = int(
            conn.execute("SELECT COUNT(*) FROM hiring_endpoints WHERE active = 1").fetchone()[0]
        )
        approved_endpoint_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM hiring_endpoints WHERE active = 1 AND lower(review_status) = 'approved'"
            ).fetchone()[0]
        )
        latest_run = conn.execute(
            """
            SELECT
                mode,
                import_file_path,
                imported_records,
                selected_endpoints,
                discovered_urls,
                accepted_jobs,
                errors,
                notes,
                started_at,
                finished_at
            FROM source_layer_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    latest_run_summary = None
    if latest_run is not None:
        latest_run_notes = str(latest_run["notes"] or "")
        latest_run_summary = {
            "mode": str(latest_run["mode"] or ""),
            "import_file_path": str(latest_run["import_file_path"] or ""),
            "imported_records": int(latest_run["imported_records"] or 0),
            "selected_endpoints": int(latest_run["selected_endpoints"] or 0),
            "discovered_urls": int(latest_run["discovered_urls"] or 0),
            "accepted_jobs": int(latest_run["accepted_jobs"] or 0),
            "errors": int(latest_run["errors"] or 0),
            "notes": latest_run_notes,
            "next_gen_supported_seeds_scanned": _extract_note_int_any(
                latest_run_notes,
                "Direct-source seeds scanned",
                "Next-gen supported seeds scanned",
            ),
            "next_gen_unsupported_seeds_skipped": _extract_note_int_any(
                latest_run_notes,
                "Direct-source unsupported seeds skipped",
                "Next-gen unsupported seeds skipped",
            ),
            "next_gen_seeded_urls": _extract_note_int_any(
                latest_run_notes,
                "Direct-source seeded URLs",
                "Next-gen seeded URLs",
            ),
            "next_gen_seeded_accepted_jobs": _extract_note_int_any(
                latest_run_notes,
                "Direct-source seeded accepted jobs",
                "Next-gen seeded accepted jobs",
            ),
            "seeded_accepted_companies": _extract_note_text(
                latest_run_notes, "Seeded accepted companies"
            ),
            "next_gen_seed_failures": _extract_note_text_any(
                latest_run_notes,
                "Direct-source seed failures",
                "Next-gen seed failures",
            ),
            "first_pipeline_error": _extract_note_text(
                latest_run_notes, "First pipeline error"
            ),
            "started_at": str(latest_run["started_at"] or ""),
            "finished_at": str(latest_run["finished_at"] or ""),
        }

    return {
        "legacy": {
            "status": "current_source_of_truth",
        },
        "shadow": {
            "company_count": company_count,
            "endpoint_count": endpoint_count,
            "active_endpoint_count": active_endpoint_count,
            "approved_endpoint_count": approved_endpoint_count,
        },
        "next_gen": {
            "status": "direct_source_seed_experiment",
            "note": "Legacy discovery stays primary, and supported direct-source seed URLs are added when available.",
        },
        "latest_run": latest_run_summary,
    }


def format_source_layer_status_summary(summary: dict) -> str:
    lines = [
        "Source layer status smoke test: PASS",
        f"legacy.status: {summary['legacy']['status']}",
        f"shadow.company_count: {summary['shadow']['company_count']}",
        f"shadow.endpoint_count: {summary['shadow']['endpoint_count']}",
        f"shadow.active_endpoint_count: {summary['shadow']['active_endpoint_count']}",
        f"shadow.approved_endpoint_count: {summary['shadow']['approved_endpoint_count']}",
        f"next_gen.status: {summary['next_gen']['status']}",
        f"next_gen.note: {summary['next_gen']['note']}",
    ]

    latest_run = summary.get("latest_run")
    if latest_run:
        lines.extend(
            [
                f"latest_run.mode: {latest_run['mode']}",
                f"latest_run.imported_records: {latest_run['imported_records']}",
                f"latest_run.errors: {latest_run['errors']}",
                f"latest_run.next_gen_supported_seeds_scanned: {latest_run['next_gen_supported_seeds_scanned']}",
                f"latest_run.next_gen_unsupported_seeds_skipped: {latest_run['next_gen_unsupported_seeds_skipped']}",
                f"latest_run.next_gen_seeded_urls: {latest_run['next_gen_seeded_urls']}",
                f"latest_run.next_gen_seeded_accepted_jobs: {latest_run['next_gen_seeded_accepted_jobs']}",
                f"latest_run.seeded_accepted_companies: {latest_run['seeded_accepted_companies']}",
                f"latest_run.notes: {latest_run['notes']}",
            ]
        )
    else:
        lines.append("latest_run: none")

    return "\n".join(lines)


def main() -> int:
    summary = build_source_layer_status_summary()
    print(format_source_layer_status_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
