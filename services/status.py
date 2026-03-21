from services.backup import get_latest_backup
from services.db import db_connection
from services.openai_key import get_openai_validation_status, load_saved_openai_api_key, mask_openai_api_key


def get_system_status() -> dict[str, str]:
    with db_connection() as conn:
        jobs_total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        jobs_new = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE workflow_status = 'New'"
        ).fetchone()[0]
        jobs_applied = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE workflow_status = 'Applied'"
        ).fetchone()[0]
        removed_total = conn.execute("SELECT COUNT(*) FROM removed_jobs").fetchone()[0]

        last_cover_row = conn.execute(
            """
            SELECT output_path, created_at
            FROM cover_letter_artifacts
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        last_import_row = conn.execute(
            """
            SELECT completed_at, status
            FROM import_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    latest_backup = get_latest_backup()
    saved_key = load_saved_openai_api_key()
    validation = get_openai_validation_status()

    key_status = "Not configured"
    if validation["has_key"] == "true" and validation["validated"] == "false":
        key_status = "Saved not validated"
    elif validation["has_key"] == "true" and validation["validated"] == "true":
        key_status = "Validated"

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
        "openai_api_key_status": key_status,
        "openai_api_key_masked": mask_openai_api_key(saved_key) if saved_key else "Not saved",
        "openai_api_key_last_validated_at": validation["last_validated_at"] or "—",
    }
