from services.backup import get_latest_backup
from services.db import db_connection
from services.openai_key import has_openai_api_key, load_saved_openai_api_key, mask_openai_api_key


def _safe_scalar(conn, query: str, default=0):
    try:
        row = conn.execute(query).fetchone()
        if row is None:
            return default
        return row[0]
    except Exception:
        return default


def _safe_row(conn, query: str):
    try:
        return conn.execute(query).fetchone()
    except Exception:
        return None


def get_system_status() -> dict[str, str]:
    with db_connection() as conn:
        jobs_total = _safe_scalar(conn, "SELECT COUNT(*) FROM jobs", 0)
        jobs_new = _safe_scalar(conn, "SELECT COUNT(*) FROM jobs WHERE workflow_status = 'New'", 0)
        jobs_applied = _safe_scalar(conn, "SELECT COUNT(*) FROM jobs WHERE workflow_status = 'Applied'", 0)
        removed_total = _safe_scalar(conn, "SELECT COUNT(*) FROM removed_jobs", 0)

        last_cover_row = _safe_row(
            conn,
            """
            SELECT output_path, created_at
            FROM cover_letter_artifacts
            ORDER BY id DESC
            LIMIT 1
            """,
        )

        last_import_row = _safe_row(
            conn,
            """
            SELECT completed_at, status
            FROM ingestion_runs
            ORDER BY id DESC
            LIMIT 1
            """,
        )

    latest_backup = get_latest_backup()
    saved_key = load_saved_openai_api_key()

    return {
        "jobs_total": str(jobs_total),
        "jobs_new": str(jobs_new),
        "jobs_applied": str(jobs_applied),
        "removed_total": str(removed_total),
        "last_cover_letter_path": last_cover_row["output_path"] if last_cover_row else "—",
        "last_cover_letter_at": last_cover_row["created_at"] if last_cover_row else "—",
        "last_import_at": last_import_row["completed_at"] if last_import_row else "—",
        "last_import_status": last_import_row["status"] if last_import_row else "—",
        "latest_backup_path": str(latest_backup) if latest_backup else "—",
        "openai_api_key_status": "Configured" if has_openai_api_key() else "Not configured",
        "openai_api_key_masked": mask_openai_api_key(saved_key) if saved_key else "Not saved",
    }
