from pathlib import Path

from config import DEFAULT_STORAGE_BACKEND
from services.db import initialize_database
from services.ingestion import ensure_ingestion_tables


def get_storage_backend() -> str:
    return DEFAULT_STORAGE_BACKEND


def initialize_local_storage() -> Path:
    db_path = initialize_database()
    ensure_ingestion_tables()
    return db_path
