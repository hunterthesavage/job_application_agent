import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DATA_DIR, DATABASE_PATH


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dir()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


@contextmanager
def db_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()

    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    names: set[str] = set()

    for row in rows:
        try:
            names.add(str(row["name"]))
        except Exception:
            names.add(str(row[1]))

    return names


def create_schema() -> None:
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legacy_sheet TEXT NOT NULL DEFAULT '',
                legacy_row_number INTEGER,
                date_found TEXT NOT NULL DEFAULT '',
                date_last_validated TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                role_family TEXT NOT NULL DEFAULT '',
                normalized_title TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                remote_type TEXT NOT NULL DEFAULT '',
                dallas_dfw_match TEXT NOT NULL DEFAULT '',
                company_careers_url TEXT NOT NULL DEFAULT '',
                job_posting_url TEXT NOT NULL DEFAULT '',
                ats_type TEXT NOT NULL DEFAULT '',
                requisition_id TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_trust TEXT NOT NULL DEFAULT '',
                source_detail TEXT NOT NULL DEFAULT '',
                compensation_raw TEXT NOT NULL DEFAULT '',
                compensation_status TEXT NOT NULL DEFAULT '',
                validation_status TEXT NOT NULL DEFAULT '',
                validation_confidence TEXT NOT NULL DEFAULT '',
                fit_score REAL,
                fit_tier TEXT NOT NULL DEFAULT '',
                ai_priority TEXT NOT NULL DEFAULT '',
                match_rationale TEXT NOT NULL DEFAULT '',
                risk_flags TEXT NOT NULL DEFAULT '',
                application_angle TEXT NOT NULL DEFAULT '',
                cover_letter_starter TEXT NOT NULL DEFAULT '',
                workflow_status TEXT NOT NULL DEFAULT 'New',
                applied_date TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'New',
                duplicate_key TEXT NOT NULL DEFAULT '',
                active_status TEXT NOT NULL DEFAULT 'Active',
                cover_letter_path TEXT NOT NULL DEFAULT '',
                seen_count INTEGER NOT NULL DEFAULT 0,
                last_seen_run_id INTEGER NOT NULL DEFAULT 0,
                last_page_refresh_at TEXT NOT NULL DEFAULT '',
                last_score_refresh_at TEXT NOT NULL DEFAULT '',
                last_refresh_status TEXT NOT NULL DEFAULT '',
                parser_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_duplicate_key
            ON jobs(duplicate_key)
            WHERE duplicate_key <> '';

            CREATE INDEX IF NOT EXISTS idx_jobs_workflow_status
            ON jobs(workflow_status);

            CREATE INDEX IF NOT EXISTS idx_jobs_applied_date
            ON jobs(applied_date);

            CREATE INDEX IF NOT EXISTS idx_jobs_fit_score
            ON jobs(fit_score);

            CREATE TABLE IF NOT EXISTS removed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                removed_date TEXT NOT NULL DEFAULT '',
                duplicate_key TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                job_posting_url TEXT NOT NULL DEFAULT '',
                removal_reason TEXT NOT NULL DEFAULT '',
                source_sheet TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_removed_jobs_duplicate_key
            ON removed_jobs(duplicate_key)
            WHERE duplicate_key <> '';

            CREATE TABLE IF NOT EXISTS cover_letter_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_duplicate_key TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                canonical_domain TEXT NOT NULL DEFAULT '',
                industry TEXT NOT NULL DEFAULT '',
                size_band TEXT NOT NULL DEFAULT '',
                hq TEXT NOT NULL DEFAULT '',
                priority_tier TEXT NOT NULL DEFAULT '',
                exec_relevance_score REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_canonical_domain
            ON companies(canonical_domain)
            WHERE canonical_domain <> '';

            CREATE INDEX IF NOT EXISTS idx_companies_name
            ON companies(name);

            CREATE TABLE IF NOT EXISTS hiring_endpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                endpoint_url TEXT NOT NULL,
                endpoint_type TEXT NOT NULL DEFAULT 'careers_page',
                ats_vendor TEXT NOT NULL DEFAULT '',
                extraction_method TEXT NOT NULL DEFAULT '',
                discovery_source TEXT NOT NULL DEFAULT '',
                confidence_score REAL NOT NULL DEFAULT 0,
                health_score REAL NOT NULL DEFAULT 0,
                review_status TEXT NOT NULL DEFAULT '',
                careers_url_status TEXT NOT NULL DEFAULT '',
                is_primary INTEGER NOT NULL DEFAULT 0,
                last_validated_at TEXT NOT NULL DEFAULT '',
                next_check_at TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, endpoint_url),
                FOREIGN KEY(company_id) REFERENCES companies(id)
            );

            CREATE INDEX IF NOT EXISTS idx_hiring_endpoints_company_id
            ON hiring_endpoints(company_id);

            CREATE INDEX IF NOT EXISTS idx_hiring_endpoints_ats_vendor
            ON hiring_endpoints(ats_vendor);

            CREATE TABLE IF NOT EXISTS endpoint_validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER NOT NULL,
                checked_at TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                jobs_found INTEGER,
                latency_ms INTEGER,
                parser_name TEXT NOT NULL DEFAULT '',
                parser_version TEXT NOT NULL DEFAULT '',
                failure_reason TEXT NOT NULL DEFAULT '',
                content_fingerprint TEXT NOT NULL DEFAULT '',
                source_payload_json TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(endpoint_id) REFERENCES hiring_endpoints(id)
            );

            CREATE INDEX IF NOT EXISTS idx_endpoint_validation_runs_endpoint_id
            ON endpoint_validation_runs(endpoint_id);

            CREATE TABLE IF NOT EXISTS source_layer_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL DEFAULT 'legacy',
                import_file_path TEXT NOT NULL DEFAULT '',
                imported_records INTEGER NOT NULL DEFAULT 0,
                selected_endpoints INTEGER NOT NULL DEFAULT 0,
                discovered_urls INTEGER NOT NULL DEFAULT 0,
                accepted_jobs INTEGER NOT NULL DEFAULT 0,
                errors INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT ''
            );
            """
        )


def ensure_schema_compatibility() -> None:
    jobs_add_columns = {
        "source_type": "ALTER TABLE jobs ADD COLUMN source_type TEXT NOT NULL DEFAULT ''",
        "source_trust": "ALTER TABLE jobs ADD COLUMN source_trust TEXT NOT NULL DEFAULT ''",
        "source_detail": "ALTER TABLE jobs ADD COLUMN source_detail TEXT NOT NULL DEFAULT ''",
        "seen_count": "ALTER TABLE jobs ADD COLUMN seen_count INTEGER NOT NULL DEFAULT 0",
        "last_seen_run_id": "ALTER TABLE jobs ADD COLUMN last_seen_run_id INTEGER NOT NULL DEFAULT 0",
        "last_page_refresh_at": "ALTER TABLE jobs ADD COLUMN last_page_refresh_at TEXT NOT NULL DEFAULT ''",
        "last_score_refresh_at": "ALTER TABLE jobs ADD COLUMN last_score_refresh_at TEXT NOT NULL DEFAULT ''",
        "last_refresh_status": "ALTER TABLE jobs ADD COLUMN last_refresh_status TEXT NOT NULL DEFAULT ''",
        "parser_version": "ALTER TABLE jobs ADD COLUMN parser_version TEXT NOT NULL DEFAULT ''",
    }

    with db_connection() as conn:
        existing_jobs_columns = _get_column_names(conn, "jobs")
        for column_name, statement in jobs_add_columns.items():
            if column_name not in existing_jobs_columns:
                conn.execute(statement)


def seed_schema_migration(version: str) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version)
            VALUES (?)
            """,
            (version,),
        )


def initialize_database() -> Path:
    create_schema()
    ensure_schema_compatibility()
    seed_schema_migration("001_initial_foundation")
    seed_schema_migration("002_jobs_source_metadata_columns")
    seed_schema_migration("003_source_layer_foundation")
    seed_schema_migration("004_jobs_refresh_metadata_columns")
    return DATABASE_PATH


def database_exists() -> bool:
    return DATABASE_PATH.exists()
