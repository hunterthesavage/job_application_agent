import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolate_openai_key_file(tmp_path, monkeypatch):
    import config
    import services.openai_key as key_module

    key_file = tmp_path / "openai_api_key.txt"

    monkeypatch.setattr(config, "DATA_DIR", tmp_path, raising=False)
    monkeypatch.setattr(config, "OPENAI_API_KEY_FILE", key_file, raising=False)
    monkeypatch.setattr(key_module, "OPENAI_API_KEY_FILE", key_file, raising=False)


@pytest.fixture()
def temp_db_path(tmp_path, monkeypatch):
    import config
    import services.db as db_module
    import services.ingestion as ingestion_module

    db_path = tmp_path / "test_job_agent.db"
    data_dir = tmp_path

    monkeypatch.setattr(config, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(config, "DATABASE_PATH", db_path, raising=False)
    monkeypatch.setattr(db_module, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(db_module, "DATABASE_PATH", db_path, raising=False)

    db_module.initialize_database()
    ingestion_module.ensure_ingestion_tables()

    return db_path


@pytest.fixture()
def seeded_db(temp_db_path):
    import sqlite3

    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture()
def patch_backup_dir(tmp_path, monkeypatch):
    import config
    import services.backup as backup_module

    backups_dir = tmp_path / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "BACKUPS_DIR", backups_dir, raising=False)
    monkeypatch.setattr(backup_module, "BACKUPS_DIR", backups_dir, raising=False)

    return backups_dir


@pytest.fixture()
def sample_job_payload():
    return {
        "date_found": "2026-03-20",
        "date_last_validated": "2026-03-20",
        "company": "TestCo",
        "title": "VP Technology",
        "role_family": "Technology",
        "normalized_title": "VP Technology",
        "location": "Remote",
        "remote_type": "Remote",
        "dallas_dfw_match": "No",
        "company_careers_url": "https://example.com/careers",
        "job_posting_url": "https://example.com/jobs/1",
        "ats_type": "Greenhouse",
        "requisition_id": "REQ-1",
        "source": "Unit Test",
        "compensation_raw": "$250,000",
        "compensation_status": "Listed",
        "validation_status": "Valid",
        "validation_confidence": "High",
        "fit_score": 90,
        "fit_tier": "A",
        "ai_priority": "High",
        "match_rationale": "Strong match",
        "risk_flags": "",
        "application_angle": "Executive transformation",
        "cover_letter_starter": "I am excited",
        "status": "New",
        "duplicate_key": "testco|vptechnology|remote|1",
        "active_status": "Active",
    }
