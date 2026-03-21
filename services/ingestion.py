from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from services.db import db_connection
from services.job_store import upsert_job


def ensure_ingestion_tables() -> None:
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                source_detail TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'started',
                total_seen INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                updated_count INTEGER NOT NULL DEFAULT 0,
                skipped_removed_count INTEGER NOT NULL DEFAULT 0,
                skipped_invalid_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS ingestion_run_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                item_value TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                duplicate_key TEXT NOT NULL DEFAULT '',
                job_id INTEGER,
                message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(run_id) REFERENCES ingestion_runs(id) ON DELETE CASCADE
            );
            """
        )


def _start_run(run_type: str, source_name: str, source_detail: str) -> int:
    ensure_ingestion_tables()
    with db_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO ingestion_runs (run_type, source_name, source_detail, status)
            VALUES (?, ?, ?, 'started')
            """,
            (run_type, source_name, source_detail),
        )
        return int(cur.lastrowid)


def _log_item(run_id: int, item_value: str, status: str, duplicate_key: str = "", job_id: int | None = None, message: str = "") -> None:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_run_items (run_id, item_value, status, duplicate_key, job_id, message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, item_value, status, duplicate_key, job_id, message),
        )


def _finish_run(run_id: int, summary: dict[str, Any], status: str) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE ingestion_runs
            SET
                completed_at = CURRENT_TIMESTAMP,
                status = ?,
                total_seen = ?,
                inserted_count = ?,
                updated_count = ?,
                skipped_removed_count = ?,
                skipped_invalid_count = ?,
                error_count = ?,
                details_json = ?
            WHERE id = ?
            """,
            (
                status,
                int(summary.get("total_seen", 0)),
                int(summary.get("inserted_count", 0)),
                int(summary.get("updated_count", 0)),
                int(summary.get("skipped_removed_count", 0)),
                int(summary.get("skipped_invalid_count", 0)),
                int(summary.get("error_count", 0)),
                json.dumps(summary),
                run_id,
            ),
        )


def ingest_job_records(job_records: list[Any], source_name: str, source_detail: str = "", run_type: str = "ingest_jobs") -> dict[str, Any]:
    run_id = _start_run(run_type=run_type, source_name=source_name, source_detail=source_detail)

    summary = {
        "run_id": run_id,
        "run_type": run_type,
        "source_name": source_name,
        "source_detail": source_detail,
        "total_seen": 0,
        "inserted_count": 0,
        "updated_count": 0,
        "skipped_removed_count": 0,
        "skipped_invalid_count": 0,
        "error_count": 0,
    }

    try:
        for job in job_records:
            summary["total_seen"] += 1

            try:
                result = upsert_job(job)
                result_status = str(result.get("status", "unknown"))

                if result_status == "inserted":
                    summary["inserted_count"] += 1
                elif result_status == "updated":
                    summary["updated_count"] += 1
                elif result_status == "skipped_removed":
                    summary["skipped_removed_count"] += 1
                else:
                    summary["skipped_invalid_count"] += 1

                item_value = ""
                duplicate_key = str(result.get("duplicate_key", "") or "")
                job_id = result.get("job_id")

                try:
                    item_value = str(getattr(job, "job_posting_url"))
                except Exception:
                    item_value = str(getattr(job, "title", "")) or duplicate_key

                _log_item(
                    run_id=run_id,
                    item_value=item_value,
                    status=result_status,
                    duplicate_key=duplicate_key,
                    job_id=job_id,
                    message="",
                )
            except Exception as exc:
                summary["error_count"] += 1
                _log_item(
                    run_id=run_id,
                    item_value=str(getattr(job, "job_posting_url", "") or getattr(job, "title", "") or ""),
                    status="error",
                    duplicate_key=str(getattr(job, "duplicate_key", "") or ""),
                    job_id=None,
                    message=str(exc),
                )

        final_status = "completed"
        _finish_run(run_id, summary, final_status)
        return summary
    except Exception as exc:
        summary["error_count"] += 1
        summary["fatal_error"] = str(exc)
        _finish_run(run_id, summary, "failed")
        raise


def get_recent_ingestion_runs(limit: int = 10) -> list[dict[str, Any]]:
    ensure_ingestion_tables()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                run_type,
                source_name,
                source_detail,
                started_at,
                completed_at,
                status,
                total_seen,
                inserted_count,
                updated_count,
                skipped_removed_count,
                skipped_invalid_count,
                error_count
            FROM ingestion_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
