from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from config import DATABASE_PATH
from services.backup import get_latest_backup
from services.openai_key import get_openai_validation_status, load_saved_openai_api_key
from services.settings import load_settings


REQUIRED_TABLES = [
    "schema_migrations",
    "app_settings",
    "jobs",
    "removed_jobs",
    "import_runs",
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
        "database_exists": False,
        "database_path": str(DATABASE_PATH),
        "required_tables_ok": False,
        "missing_tables": [],
        "cover_letter_folder_exists": False,
        "cover_letter_folder_path": "",
        "openai_api_key_present": False,
        "openai_api_key_validated": False,
        "openai_api_key_source": "none",
        "latest_backup_exists": False,
        "latest_backup_path": "",
        "status": "ok",
        "issues": [],
    }

    if DATABASE_PATH.exists():
        results["database_exists"] = True
    else:
        results["status"] = "warning"
        results["issues"].append("Database file is missing.")

    if results["database_exists"]:
        conn = sqlite3.connect(DATABASE_PATH)
        try:
            missing = [table for table in REQUIRED_TABLES if not _table_exists(conn, table)]
            results["missing_tables"] = missing
            results["required_tables_ok"] = len(missing) == 0
            if missing:
                results["status"] = "warning"
                results["issues"].append(f"Missing tables: {', '.join(missing)}")
        finally:
            conn.close()

    settings = load_settings()
    folder_path = str(settings.get("cover_letter_output_folder", "") or "").strip()
    results["cover_letter_folder_path"] = folder_path
    if folder_path:
        folder = Path(folder_path).expanduser()
        results["cover_letter_folder_exists"] = folder.exists() and folder.is_dir()
        if not results["cover_letter_folder_exists"]:
            results["status"] = "warning"
            results["issues"].append("Cover letter output folder does not exist.")

    validation = get_openai_validation_status()
    results["openai_api_key_present"] = validation["has_key"] == "true"
    results["openai_api_key_validated"] = validation["validated"] == "true"

    saved_key = load_saved_openai_api_key()
    env_key = str(os.getenv("OPENAI_API_KEY", "")).strip()

    if saved_key:
        results["openai_api_key_source"] = "saved_file"
    elif env_key:
        results["openai_api_key_source"] = "environment"

    if not results["openai_api_key_present"]:
        results["status"] = "warning"
        results["issues"].append("No OpenAI API key is configured.")
    elif not results["openai_api_key_validated"]:
        results["status"] = "warning"
        results["issues"].append("OpenAI API key is saved but not validated.")

    latest_backup = get_latest_backup()
    if latest_backup is not None and latest_backup.exists():
        results["latest_backup_exists"] = True
        results["latest_backup_path"] = str(latest_backup)
    else:
        results["status"] = "warning"
        results["issues"].append("No backup file found yet.")

    if results["issues"] and results["status"] != "failed":
        results["status"] = "warning"

    return results
