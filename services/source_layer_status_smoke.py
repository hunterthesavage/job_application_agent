from __future__ import annotations

from services.db import db_connection


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
        latest_run_summary = {
            "mode": str(latest_run["mode"] or ""),
            "import_file_path": str(latest_run["import_file_path"] or ""),
            "imported_records": int(latest_run["imported_records"] or 0),
            "selected_endpoints": int(latest_run["selected_endpoints"] or 0),
            "discovered_urls": int(latest_run["discovered_urls"] or 0),
            "accepted_jobs": int(latest_run["accepted_jobs"] or 0),
            "errors": int(latest_run["errors"] or 0),
            "notes": str(latest_run["notes"] or ""),
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
            "status": "seed_experiment",
            "note": "Legacy discovery stays primary, and supported source-layer seed URLs are added when available.",
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
