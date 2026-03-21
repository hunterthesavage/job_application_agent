from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from config import BACKUPS_DIR, DATABASE_PATH


def ensure_backup_dir() -> None:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def backup_database() -> Path:
    ensure_backup_dir()

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found at: {DATABASE_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"job_agent_{timestamp}.db"
    shutil.copy2(DATABASE_PATH, backup_path)
    return backup_path


def list_backups() -> list[Path]:
    ensure_backup_dir()
    backups = sorted(BACKUPS_DIR.glob("job_agent_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups


def get_latest_backup() -> Path | None:
    backups = list_backups()
    return backups[0] if backups else None


def restore_latest_backup() -> Path:
    latest = get_latest_backup()
    if latest is None:
        raise FileNotFoundError("No backups found to restore.")

    if not latest.exists():
        raise FileNotFoundError(f"Backup file not found: {latest}")

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(latest, DATABASE_PATH)
    return latest
