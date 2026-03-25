from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DATABASE_PATH
from services.backup import get_latest_backup
from services.openai_key import load_environment_openai_api_key, load_saved_openai_api_key
from services.settings import load_settings


REQUIRED_TABLES = [
    "schema_migrations",
    "app_settings",
    "jobs",
    "removed_jobs",
    "cover_letter_artifacts",
    "ingestion_runs",
    "ingestion_run_items",
]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def run_health_check() -> dict:
    results = {
        "status": "ok",
        "issues": [],
        "errors": [],
        "checks": {},
        "database_exists": False,
        "database_path": str(DATABASE_PATH),
        "required_tables_ok": False,
        "missing_tables": [],
        "cover_letter_folder_exists": False,
        "cover_letter_folder_path": "",
        "openai_api_key_present": False,
        "openai_api_key_source": "none",
        "latest_backup_exists": False,
        "latest_backup_path": "",
    }

    database_exists = DATABASE_PATH.exists()
    results["database_exists"] = database_exists
    results["checks"]["database_file"] = {
        "label": "Database file",
        "status": "ok" if database_exists else "warning",
        "message": str(DATABASE_PATH) if database_exists else "Database file is missing.",
    }
    if not database_exists:
        results["status"] = "warning"
        results["issues"].append("Database file is missing.")

    if database_exists:
        conn = sqlite3.connect(DATABASE_PATH)
        try:
            missing = [table for table in REQUIRED_TABLES if not _table_exists(conn, table)]
            results["missing_tables"] = missing
            results["required_tables_ok"] = len(missing) == 0
            results["checks"]["required_tables"] = {
                "label": "Required tables",
                "status": "ok" if not missing else "warning",
                "message": "All required tables are present." if not missing else f"Missing tables: {', '.join(missing)}",
            }
            if missing:
                results["status"] = "warning"
                results["issues"].append(f"Missing tables: {', '.join(missing)}")
        except Exception as exc:
            results["status"] = "failed"
            results["errors"].append(f"Database check failed: {exc}")
            results["checks"]["required_tables"] = {
                "label": "Required tables",
                "status": "error",
                "message": f"Database check failed: {exc}",
            }
        finally:
            conn.close()
    else:
        results["checks"]["required_tables"] = {
            "label": "Required tables",
            "status": "warning",
            "message": "Skipped because the database file is missing.",
        }

    settings = load_settings()
    folder_path = str(settings.get("cover_letter_output_folder", "") or "").strip()
    results["cover_letter_folder_path"] = folder_path
    if folder_path:
        folder = Path(folder_path).expanduser()
        folder_ok = folder.exists() and folder.is_dir()
        results["cover_letter_folder_exists"] = folder_ok
        results["checks"]["cover_letter_output_folder"] = {
            "label": "Cover letter output folder",
            "status": "ok" if folder_ok else "warning",
            "message": str(folder) if folder_ok else "Configured folder does not exist.",
        }
        if not folder_ok:
            results["status"] = "warning" if results["status"] != "failed" else results["status"]
            results["issues"].append("Cover letter output folder does not exist.")
    else:
        results["checks"]["cover_letter_output_folder"] = {
            "label": "Cover letter output folder",
            "status": "warning",
            "message": "No output folder is configured yet.",
        }
        results["status"] = "warning" if results["status"] != "failed" else results["status"]
        results["issues"].append("No cover letter output folder is configured yet.")

    saved_key = load_saved_openai_api_key()
    env_key = load_environment_openai_api_key()
    if saved_key:
        results["openai_api_key_present"] = True
        results["openai_api_key_source"] = "saved_file"
        results["checks"]["openai_api_key"] = {
            "label": "OpenAI API key",
            "status": "ok",
            "message": "Saved in the app.",
        }
    elif env_key:
        results["openai_api_key_present"] = True
        results["openai_api_key_source"] = "environment"
        results["checks"]["openai_api_key"] = {
            "label": "OpenAI API key",
            "status": "ok",
            "message": "Available from the environment.",
        }
    else:
        results["status"] = "warning" if results["status"] != "failed" else results["status"]
        results["issues"].append("No OpenAI API key is configured.")
        results["checks"]["openai_api_key"] = {
            "label": "OpenAI API key",
            "status": "warning",
            "message": "No API key is configured yet.",
        }

    latest_backup = get_latest_backup()
    if latest_backup is not None and latest_backup.exists():
        results["latest_backup_exists"] = True
        results["latest_backup_path"] = str(latest_backup)
        results["checks"]["latest_backup"] = {
            "label": "Latest backup",
            "status": "ok",
            "message": str(latest_backup),
        }
    else:
        results["status"] = "warning" if results["status"] != "failed" else results["status"]
        results["issues"].append("No backup file found yet.")
        results["checks"]["latest_backup"] = {
            "label": "Latest backup",
            "status": "warning",
            "message": "No backup file found yet.",
        }

    return results
