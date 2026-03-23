from __future__ import annotations

import json
from typing import Any

from services.db import db_connection
from services.job_store import upsert_job
from services.run_source_yield import increment_source_yield, summarize_source_yield, detect_source_dominance
from services.source_trust import (
    determine_source_trust,
    determine_source_type,
    hostname_for_url,
    safe_text,
    source_key_for_job,
    source_root_for_job,
)


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

            CREATE TABLE IF NOT EXISTS source_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT NOT NULL UNIQUE,
                source_root TEXT NOT NULL DEFAULT '',
                hostname TEXT NOT NULL DEFAULT '',
                ats_type TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_trust TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                source_detail TEXT NOT NULL DEFAULT '',
                example_job_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                seen_count INTEGER NOT NULL DEFAULT 0,
                matching_job_count INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_success_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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


def _increment_counter(bucket: dict[str, int], key: str) -> None:
    label = safe_text(key) or "Unknown"
    bucket[label] = bucket.get(label, 0) + 1


def _register_source(job: Any, source_name: str, source_detail: str) -> None:
    job_url = safe_text(getattr(job, "job_posting_url", "") if not isinstance(job, dict) else job.get("job_posting_url", ""))
    ats_type = safe_text(getattr(job, "ats_type", "") if not isinstance(job, dict) else job.get("ats_type", ""))
    source_type = safe_text(getattr(job, "source_type", "") if not isinstance(job, dict) else job.get("source_type", "")) or determine_source_type(job_url, ats_type)
    source_trust = safe_text(getattr(job, "source_trust", "") if not isinstance(job, dict) else job.get("source_trust", "")) or determine_source_trust(job_url, ats_type)

    source_key = source_key_for_job(job_url, ats_type)
    if not source_key:
        return

    source_root = source_root_for_job(job_url, ats_type)
    hostname = hostname_for_url(job_url)

    with db_connection() as conn:
        existing = conn.execute(
            "SELECT id, seen_count, matching_job_count FROM source_registry WHERE source_key = ? LIMIT 1",
            (source_key,),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO source_registry (
                    source_key,
                    source_root,
                    hostname,
                    ats_type,
                    source_type,
                    source_trust,
                    source_name,
                    source_detail,
                    example_job_url,
                    status,
                    seen_count,
                    matching_job_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, 1)
                """,
                (
                    source_key,
                    source_root,
                    hostname,
                    ats_type,
                    source_type,
                    source_trust,
                    source_name,
                    source_detail,
                    job_url,
                ),
            )
            return

        conn.execute(
            """
            UPDATE source_registry
            SET
                source_root = ?,
                hostname = ?,
                ats_type = ?,
                source_type = ?,
                source_trust = ?,
                source_name = ?,
                source_detail = ?,
                example_job_url = ?,
                status = 'active',
                seen_count = ?,
                matching_job_count = ?,
                last_seen_at = CURRENT_TIMESTAMP,
                last_success_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                source_root,
                hostname,
                ats_type,
                source_type,
                source_trust,
                source_name,
                source_detail,
                job_url,
                int(existing["seen_count"] or 0) + 1,
                int(existing["matching_job_count"] or 0) + 1,
                int(existing["id"]),
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
        "net_new_count": 0,
        "rediscovered_count": 0,
        "duplicate_in_run_count": 0,
        "net_new_job_ids": [],
        "rediscovered_job_ids": [],
        "duplicate_in_run_job_ids": [],
        "source_trust_counts": {},
        "source_type_counts": {},
        "source_yield_counts": {},
        "source_yield_top": [],
        "source_dominance": {},
    }

    try:
        for job in job_records:
            summary["total_seen"] += 1

            try:
                result = upsert_job(job, run_id=run_id)
                result_status = str(result.get("status", "unknown"))
                discovery_state = str(result.get("discovery_state", "") or "")
                job_id = result.get("job_id")

                source_trust = safe_text(getattr(job, "source_trust", "") if not isinstance(job, dict) else job.get("source_trust", ""))
                source_type = safe_text(getattr(job, "source_type", "") if not isinstance(job, dict) else job.get("source_type", ""))
                _increment_counter(summary["source_trust_counts"], source_trust)
                _increment_counter(summary["source_type_counts"], source_type)
                increment_source_yield(summary["source_yield_counts"], job)

                if result_status == "inserted":
                    summary["inserted_count"] += 1
                elif result_status == "updated":
                    summary["updated_count"] += 1
                elif result_status == "skipped_removed":
                    summary["skipped_removed_count"] += 1
                else:
                    summary["skipped_invalid_count"] += 1

                if discovery_state == "net_new":
                    summary["net_new_count"] += 1
                    if job_id is not None:
                        summary["net_new_job_ids"].append(int(job_id))
                elif discovery_state == "rediscovered":
                    summary["rediscovered_count"] += 1
                    if job_id is not None:
                        summary["rediscovered_job_ids"].append(int(job_id))
                elif discovery_state == "duplicate_in_run":
                    summary["duplicate_in_run_count"] += 1
                    if job_id is not None:
                        summary["duplicate_in_run_job_ids"].append(int(job_id))

                item_value = ""
                duplicate_key = str(result.get("duplicate_key", "") or "")

                try:
                    item_value = str(getattr(job, "job_posting_url"))
                except Exception:
                    if isinstance(job, dict):
                        item_value = str(job.get("job_posting_url", "") or job.get("title", "") or duplicate_key)
                    else:
                        item_value = str(getattr(job, "title", "")) or duplicate_key

                _register_source(job, source_name=source_name, source_detail=source_detail)

                _log_item(
                    run_id=run_id,
                    item_value=item_value,
                    status=result_status,
                    duplicate_key=duplicate_key,
                    job_id=job_id,
                    message=discovery_state,
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
        summary["source_yield_top"] = summarize_source_yield(summary.get("source_yield_counts", {}))
        summary["source_dominance"] = detect_source_dominance(
            summary.get("source_yield_counts", {}),
            int(summary.get("total_seen", 0)),
        )
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
                error_count,
                details_json
            FROM ingestion_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        details_json = safe_text(item.get("details_json", ""))
        if details_json:
            try:
                item["details"] = json.loads(details_json)
            except Exception:
                item["details"] = {}
        else:
            item["details"] = {}
        items.append(item)
    return items


def get_source_registry_summary() -> dict[str, Any]:
    ensure_ingestion_tables()
    with db_connection() as conn:
        totals_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_sources,
                SUM(CASE WHEN source_trust = 'ATS Confirmed' THEN 1 ELSE 0 END) AS ats_confirmed_sources,
                SUM(CASE WHEN source_trust = 'Career Site Confirmed' THEN 1 ELSE 0 END) AS career_site_sources,
                SUM(CASE WHEN source_trust = 'Web Discovered' THEN 1 ELSE 0 END) AS web_discovered_sources,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_sources,
                COALESCE(SUM(seen_count), 0) AS total_seen_count,
                COALESCE(SUM(matching_job_count), 0) AS total_matching_job_count
            FROM source_registry
            """
        ).fetchone()

        recent_rows = conn.execute(
            """
            SELECT
                source_name,
                hostname,
                source_trust,
                source_type,
                matching_job_count,
                last_success_at
            FROM source_registry
            ORDER BY datetime(last_success_at) DESC, id DESC
            LIMIT 8
            """
        ).fetchall()

    totals = dict(totals_row) if totals_row else {}
    recent_sources = [dict(row) for row in recent_rows]
    return {
        "totals": totals,
        "recent_sources": recent_sources,
    }


def update_ingestion_run_details(run_id: int, extra_details: dict[str, Any]) -> None:
    if not run_id or not extra_details:
        return

    with db_connection() as conn:
        row = conn.execute(
            "SELECT details_json FROM ingestion_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

        current = {}
        existing_json = safe_text(row["details_json"] if row and "details_json" in row.keys() else (row[0] if row else ""))
        if existing_json:
            try:
                current = json.loads(existing_json)
            except Exception:
                current = {}

        current.update(extra_details)

        conn.execute(
            """
            UPDATE ingestion_runs
            SET details_json = ?
            WHERE id = ?
            """,
            (json.dumps(current), run_id),
        )
