from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from services.db import db_connection
from services.source_trust import (
    choose_better_source_detail,
    choose_better_source_type,
    choose_better_trust,
    safe_text,
    trust_rank,
)


JOB_COLUMNS = [
    "date_found",
    "date_last_validated",
    "company",
    "title",
    "role_family",
    "normalized_title",
    "location",
    "remote_type",
    "dallas_dfw_match",
    "company_careers_url",
    "job_posting_url",
    "ats_type",
    "requisition_id",
    "source",
    "source_type",
    "source_trust",
    "source_detail",
    "parser_version",
    "compensation_raw",
    "compensation_status",
    "validation_status",
    "validation_confidence",
    "fit_score",
    "fit_tier",
    "ai_priority",
    "match_rationale",
    "risk_flags",
    "application_angle",
    "cover_letter_starter",
    "status",
    "duplicate_key",
    "active_status",
]


REQUIRED_JOB_COLUMNS = {
    "source_type": "TEXT NOT NULL DEFAULT ''",
    "source_trust": "TEXT NOT NULL DEFAULT ''",
    "source_detail": "TEXT NOT NULL DEFAULT ''",
    "first_seen_at": "TEXT NOT NULL DEFAULT ''",
    "last_seen_at": "TEXT NOT NULL DEFAULT ''",
    "last_seen_run_id": "INTEGER NOT NULL DEFAULT 0",
    "seen_count": "INTEGER NOT NULL DEFAULT 0",
    "canonical_job_posting_url": "TEXT NOT NULL DEFAULT ''",
    "last_page_refresh_at": "TEXT NOT NULL DEFAULT ''",
    "last_score_refresh_at": "TEXT NOT NULL DEFAULT ''",
    "last_refresh_status": "TEXT NOT NULL DEFAULT ''",
    "parser_version": "TEXT NOT NULL DEFAULT ''",
}


DEFAULT_PARSER_VERSION = "validate_job_url_v1"


TRACKING_QUERY_PREFIXES = (
    "utm_",
    "gh_",
    "ghsrc",
    "gh_src",
    "lever-",
    "lever_",
    "source",
    "src",
    "ref",
    "refs",
    "trk",
    "tracking",
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _normalize_token_text(value: Any) -> str:
    text = _clean(value).lower()
    if not text:
        return ""
    normalized = []
    last_was_sep = False
    for ch in text:
        if ch.isalnum():
            normalized.append(ch)
            last_was_sep = False
        else:
            if not last_was_sep:
                normalized.append(" ")
            last_was_sep = True
    return " ".join("".join(normalized).split())


def _to_float(value: Any):
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _to_int(value: Any, default: int = 0) -> int:
    text = _clean(value)
    if not text:
        return default
    try:
        return int(float(text))
    except Exception:
        return default


def normalize_duplicate_key(value: Any) -> str:
    text = _normalize_token_text(value)
    if not text:
        return ""
    return "|".join(part for part in text.split() if part)


def canonicalize_job_posting_url(url: Any) -> str:
    raw = _clean(url)
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()

        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = parsed.path or ""
        while "//" in path:
            path = path.replace("//", "/")
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        kept_params = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=False):
            key_lower = key.lower()
            if key_lower.startswith(TRACKING_QUERY_PREFIXES):
                continue
            kept_params.append((key, value))

        query = urlencode(kept_params, doseq=True)

        canonical = urlunparse((scheme, netloc, path, "", query, ""))
        return canonical.strip()
    except Exception:
        return raw.strip().lower()


def build_fallback_duplicate_key(payload: dict[str, Any]) -> str:
    requisition_id = _normalize_token_text(payload.get("requisition_id", ""))
    ats_type = _normalize_token_text(payload.get("ats_type", ""))
    company = _normalize_token_text(payload.get("company", ""))
    title = _normalize_token_text(payload.get("title", ""))
    location = _normalize_token_text(payload.get("location", ""))

    if requisition_id and company:
        return normalize_duplicate_key(f"{company}|{ats_type}|{requisition_id}")

    parts = [company, title, location]
    if any(parts):
        return normalize_duplicate_key("|".join(part for part in parts if part))

    canonical_url = canonicalize_job_posting_url(payload.get("job_posting_url", ""))
    if canonical_url:
        return normalize_duplicate_key(canonical_url)

    return ""


def ensure_job_columns() -> None:
    with db_connection() as conn:
        rows = conn.execute("PRAGMA table_info(jobs)").fetchall()
        existing = {str(row[1]) for row in rows}

        for column_name, column_sql in REQUIRED_JOB_COLUMNS.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_sql}")


def coerce_job_payload(job: Any) -> dict[str, Any]:
    ensure_job_columns()

    if is_dataclass(job):
        raw = asdict(job)
    elif isinstance(job, dict):
        raw = dict(job)
    else:
        raise TypeError("job must be a dict or dataclass instance")

    payload: dict[str, Any] = {}
    for key in JOB_COLUMNS:
        payload[key] = raw.get(key, "")

    payload["fit_score"] = _to_float(payload.get("fit_score"))
    payload["status"] = _clean(payload.get("status")) or "New"
    payload["active_status"] = _clean(payload.get("active_status")) or "Active"
    payload["source"] = _clean(payload.get("source")) or "Local Pipeline"
    payload["source_type"] = _clean(payload.get("source_type"))
    payload["source_trust"] = _clean(payload.get("source_trust"))
    payload["source_detail"] = _clean(payload.get("source_detail"))
    payload["parser_version"] = _clean(payload.get("parser_version")) or DEFAULT_PARSER_VERSION
    payload["job_posting_url"] = _clean(payload.get("job_posting_url"))
    payload["canonical_job_posting_url"] = canonicalize_job_posting_url(payload.get("job_posting_url", ""))

    normalized_duplicate_key = normalize_duplicate_key(payload.get("duplicate_key", ""))
    payload["duplicate_key"] = normalized_duplicate_key or build_fallback_duplicate_key(payload)

    return payload


def get_existing_job_by_duplicate_key(duplicate_key: str):
    ensure_job_columns()
    normalized = normalize_duplicate_key(duplicate_key)
    if not normalized:
        return None

    with db_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE duplicate_key = ?
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()


def get_existing_job_by_posting_url(job_posting_url: str):
    job_posting_url = _clean(job_posting_url)
    canonical = canonicalize_job_posting_url(job_posting_url)

    if not job_posting_url and not canonical:
        return None

    ensure_job_columns()
    with db_connection() as conn:
        row = None
        if canonical:
            row = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE canonical_job_posting_url = ?
                LIMIT 1
                """,
                (canonical,),
            ).fetchone()

        if row is not None:
            return row

        if job_posting_url:
            return conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE job_posting_url = ?
                LIMIT 1
                """,
                (job_posting_url,),
            ).fetchone()

    return None

def _build_rescore_selection_query(
    *,
    select_clause: str,
    stale_days: int | None = None,
) -> tuple[str, tuple[Any, ...]]:
    query = f"""
        {select_clause}
        FROM jobs
        WHERE active_status != 'Removed'
    """
    params: list[Any] = []

    if stale_days is not None and int(stale_days) > 0:
        query += """
          AND datetime(COALESCE(NULLIF(updated_at, ''), CURRENT_TIMESTAMP))
              <= datetime('now', ?)
        """
        params.append(f"-{int(stale_days)} days")

    query += """
        ORDER BY
            CASE
                WHEN workflow_status = 'New' THEN 0
                WHEN workflow_status = 'Applied' THEN 1
                ELSE 2
            END,
            updated_at DESC,
            id DESC
    """
    return query, tuple(params)


def count_jobs_for_rescoring(stale_days: int | None = None) -> int:
    ensure_job_columns()
    query, params = _build_rescore_selection_query(
        select_clause="SELECT COUNT(*) AS rescore_count",
        stale_days=stale_days,
    )

    with db_connection() as conn:
        row = conn.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row[0] or 0)


def list_jobs_for_rescoring(limit: int | None = None, stale_days: int | None = None) -> list[Any]:
    ensure_job_columns()

    query, params = _build_rescore_selection_query(
        select_clause="SELECT *",
        stale_days=stale_days,
    )

    if limit is not None and int(limit) > 0:
        query += "\nLIMIT ?"
        params = (*params, int(limit))

    with db_connection() as conn:
        return conn.execute(query, params).fetchall()


def _build_run_maintenance_selection_query(
    *,
    select_clause: str,
    stale_days: int,
    exclude_run_id: int = 0,
) -> tuple[str, tuple[Any, ...]]:
    effective_stale_days = max(int(stale_days or 0), 1)
    query = f"""
        {select_clause}
        FROM jobs
        WHERE active_status != 'Removed'
          AND (
                TRIM(COALESCE(company, '')) = ''
                OR TRIM(COALESCE(title, '')) = ''
                OR TRIM(COALESCE(compensation_raw, '')) = ''
                OR TRIM(COALESCE(validation_status, '')) = ''
                OR TRIM(COALESCE(last_page_refresh_at, '')) = ''
                OR datetime(COALESCE(NULLIF(last_page_refresh_at, ''), '1970-01-01 00:00:00'))
                    <= datetime('now', ?)
          )
    """
    params: list[Any] = [f"-{effective_stale_days} days"]

    if int(exclude_run_id or 0) > 0:
        query += """
          AND COALESCE(last_seen_run_id, 0) != ?
        """
        params.append(int(exclude_run_id))

    query += """
        ORDER BY
            CASE
                WHEN TRIM(COALESCE(company, '')) = '' OR TRIM(COALESCE(title, '')) = '' THEN 0
                WHEN TRIM(COALESCE(compensation_raw, '')) = '' THEN 1
                WHEN TRIM(COALESCE(last_page_refresh_at, '')) = '' THEN 2
                ELSE 3
            END,
            CASE
                WHEN workflow_status = 'New' THEN 0
                WHEN workflow_status = 'Applied' THEN 1
                ELSE 2
            END,
            fit_score DESC,
            updated_at DESC,
            id DESC
    """
    return query, tuple(params)


def count_jobs_for_maintenance(stale_days: int = 7, exclude_run_id: int = 0) -> int:
    ensure_job_columns()
    query, params = _build_run_maintenance_selection_query(
        select_clause="SELECT COUNT(*) AS maintenance_count",
        stale_days=stale_days,
        exclude_run_id=exclude_run_id,
    )

    with db_connection() as conn:
        row = conn.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row[0] or 0)


def list_jobs_for_maintenance(
    *,
    limit: int | None = None,
    stale_days: int = 7,
    exclude_run_id: int = 0,
) -> list[Any]:
    ensure_job_columns()
    query, params = _build_run_maintenance_selection_query(
        select_clause="SELECT *",
        stale_days=stale_days,
        exclude_run_id=exclude_run_id,
    )

    if limit is not None and int(limit) > 0:
        query += "\nLIMIT ?"
        params = (*params, int(limit))

    with db_connection() as conn:
        return conn.execute(query, params).fetchall()


def is_removed_duplicate_key(duplicate_key: str) -> bool:
    normalized = normalize_duplicate_key(duplicate_key)
    if not normalized:
        return False

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM removed_jobs
            WHERE duplicate_key = ?
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()

    return row is not None


def insert_job(payload: dict[str, Any], run_id: int | None = None) -> int:
    ensure_job_columns()
    effective_run_id = int(run_id or 0)

    with db_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                date_found,
                date_last_validated,
                company,
                title,
                role_family,
                normalized_title,
                location,
                remote_type,
                dallas_dfw_match,
                company_careers_url,
                job_posting_url,
                canonical_job_posting_url,
                ats_type,
                requisition_id,
                source,
                source_type,
                source_trust,
                source_detail,
                compensation_raw,
                compensation_status,
                validation_status,
                validation_confidence,
                fit_score,
                fit_tier,
                ai_priority,
                match_rationale,
                risk_flags,
                application_angle,
                cover_letter_starter,
                status,
                duplicate_key,
                active_status,
                workflow_status,
                applied_date,
                first_seen_at,
                last_seen_at,
                last_seen_run_id,
                seen_count,
                last_page_refresh_at,
                last_score_refresh_at,
                last_refresh_status,
                parser_version
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', '',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                ?,
                1,
                CURRENT_TIMESTAMP,
                CASE WHEN ? IS NOT NULL OR TRIM(COALESCE(?, '')) <> '' OR TRIM(COALESCE(?, '')) <> '' THEN CURRENT_TIMESTAMP ELSE '' END,
                'discovered',
                ?
            )
            """,
            (
                payload["date_found"],
                payload["date_last_validated"],
                payload["company"],
                payload["title"],
                payload["role_family"],
                payload["normalized_title"],
                payload["location"],
                payload["remote_type"],
                payload["dallas_dfw_match"],
                payload["company_careers_url"],
                payload["job_posting_url"],
                payload["canonical_job_posting_url"],
                payload["ats_type"],
                payload["requisition_id"],
                payload["source"],
                payload["source_type"],
                payload["source_trust"],
                payload["source_detail"],
                payload["compensation_raw"],
                payload["compensation_status"],
                payload["validation_status"],
                payload["validation_confidence"],
                payload["fit_score"],
                payload["fit_tier"],
                payload["ai_priority"],
                payload["match_rationale"],
                payload["risk_flags"],
                payload["application_angle"],
                payload["cover_letter_starter"],
                payload["status"],
                payload["duplicate_key"],
                payload["active_status"],
                effective_run_id,
                payload["fit_score"],
                payload["fit_tier"],
                payload["ai_priority"],
                payload["parser_version"],
            ),
        )
        return int(cur.lastrowid)


def _resolve_source_fields(existing: Any, payload: dict[str, Any]) -> tuple[str, str, str, bool]:
    existing_trust = safe_text(existing["source_trust"] if existing else "")
    new_trust = safe_text(payload.get("source_trust", ""))
    final_trust = choose_better_trust(existing_trust, new_trust)

    existing_type = safe_text(existing["source_type"] if existing else "")
    new_type = safe_text(payload.get("source_type", ""))
    final_type = choose_better_source_type(existing_type, new_type)

    existing_detail = safe_text(existing["source_detail"] if existing else "")
    new_detail = safe_text(payload.get("source_detail", ""))
    final_detail = choose_better_source_detail(existing_detail, new_detail, existing_trust, new_trust)

    was_promoted = trust_rank(final_trust) > trust_rank(existing_trust)
    return final_type, final_trust, final_detail, was_promoted


def update_existing_job(existing_id: int, payload: dict[str, Any], preserve_applied: bool = True, run_id: int | None = None) -> bool:
    ensure_job_columns()
    effective_run_id = int(run_id or 0)

    with db_connection() as conn:
        existing = conn.execute(
            """
            SELECT workflow_status, applied_date, source_type, source_trust, source_detail, seen_count
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (existing_id,),
        ).fetchone()

        workflow_status = "New"
        applied_date = ""
        existing_seen_count = 0

        if existing is not None:
            existing_seen_count = _to_int(existing["seen_count"], default=0)

        if existing is not None and preserve_applied and str(existing["workflow_status"]) == "Applied":
            workflow_status = "Applied"
            applied_date = str(existing["applied_date"] or "").strip()

        final_source_type, final_source_trust, final_source_detail, was_promoted = _resolve_source_fields(existing, payload)

        conn.execute(
            """
            UPDATE jobs
            SET
                date_last_validated = ?,
                company = ?,
                title = ?,
                role_family = ?,
                normalized_title = ?,
                location = ?,
                remote_type = ?,
                dallas_dfw_match = ?,
                company_careers_url = ?,
                job_posting_url = ?,
                canonical_job_posting_url = ?,
                ats_type = ?,
                requisition_id = ?,
                source = ?,
                source_type = ?,
                source_trust = ?,
                source_detail = ?,
                compensation_raw = ?,
                compensation_status = ?,
                validation_status = ?,
                validation_confidence = ?,
                fit_score = ?,
                fit_tier = ?,
                ai_priority = ?,
                match_rationale = ?,
                risk_flags = ?,
                application_angle = ?,
                cover_letter_starter = ?,
                status = ?,
                active_status = ?,
                duplicate_key = ?,
                workflow_status = ?,
                applied_date = ?,
                last_seen_at = CURRENT_TIMESTAMP,
                last_seen_run_id = ?,
                seen_count = ?,
                last_page_refresh_at = CURRENT_TIMESTAMP,
                last_score_refresh_at = CASE
                    WHEN ? IS NOT NULL OR TRIM(COALESCE(?, '')) <> '' OR TRIM(COALESCE(?, '')) <> '' THEN CURRENT_TIMESTAMP
                    ELSE last_score_refresh_at
                END,
                last_refresh_status = 'discovered',
                parser_version = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload["date_last_validated"],
                payload["company"],
                payload["title"],
                payload["role_family"],
                payload["normalized_title"],
                payload["location"],
                payload["remote_type"],
                payload["dallas_dfw_match"],
                payload["company_careers_url"],
                payload["job_posting_url"],
                payload["canonical_job_posting_url"],
                payload["ats_type"],
                payload["requisition_id"],
                payload["source"],
                final_source_type,
                final_source_trust,
                final_source_detail,
                payload["compensation_raw"],
                payload["compensation_status"],
                payload["validation_status"],
                payload["validation_confidence"],
                payload["fit_score"],
                payload["fit_tier"],
                payload["ai_priority"],
                payload["match_rationale"],
                payload["risk_flags"],
                payload["application_angle"],
                payload["cover_letter_starter"],
                payload["status"],
                payload["active_status"],
                payload["duplicate_key"],
                workflow_status,
                applied_date,
                effective_run_id,
                existing_seen_count + 1,
                payload["fit_score"],
                payload["fit_tier"],
                payload["ai_priority"],
                payload["parser_version"],
                existing_id,
            ),
        )
        return was_promoted


def update_job_refresh_fields(
    job_id: int,
    payload: dict[str, Any],
    *,
    scored: bool,
    refresh_status: str,
) -> None:
    ensure_job_columns()
    coerced = coerce_job_payload(payload)

    with db_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET
                company = ?,
                title = ?,
                role_family = ?,
                normalized_title = ?,
                location = ?,
                remote_type = ?,
                dallas_dfw_match = ?,
                job_posting_url = ?,
                canonical_job_posting_url = ?,
                compensation_raw = ?,
                compensation_status = ?,
                validation_status = ?,
                validation_confidence = ?,
                fit_score = ?,
                fit_tier = ?,
                ai_priority = ?,
                match_rationale = ?,
                risk_flags = ?,
                application_angle = ?,
                parser_version = ?,
                last_page_refresh_at = CURRENT_TIMESTAMP,
                last_score_refresh_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE last_score_refresh_at END,
                last_refresh_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                coerced["company"],
                coerced["title"],
                coerced["role_family"],
                coerced["normalized_title"],
                coerced["location"],
                coerced["remote_type"],
                coerced["dallas_dfw_match"],
                coerced["job_posting_url"],
                coerced["canonical_job_posting_url"],
                coerced["compensation_raw"],
                coerced["compensation_status"],
                coerced["validation_status"],
                coerced["validation_confidence"],
                coerced["fit_score"],
                coerced["fit_tier"],
                coerced["ai_priority"],
                coerced["match_rationale"],
                coerced["risk_flags"],
                coerced["application_angle"],
                coerced["parser_version"],
                1 if scored else 0,
                _clean(refresh_status),
                int(job_id),
            ),
        )


def update_job_refresh_status(job_id: int, refresh_status: str) -> None:
    ensure_job_columns()
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET
                last_refresh_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (_clean(refresh_status), int(job_id)),
        )


def update_job_scoring_fields(job_id: int, payload: dict[str, Any], *, include_core_fields: bool = False) -> None:
    ensure_job_columns()
    coerced = coerce_job_payload(payload)

    with db_connection() as conn:
        if include_core_fields:
            conn.execute(
                """
                UPDATE jobs
                SET
                    company = ?,
                    title = ?,
                    location = ?,
                    compensation_raw = ?,
                    fit_score = ?,
                    fit_tier = ?,
                    ai_priority = ?,
                    match_rationale = ?,
                    risk_flags = ?,
                    application_angle = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    coerced["company"],
                    coerced["title"],
                    coerced["location"],
                    coerced["compensation_raw"],
                    coerced["fit_score"],
                    coerced["fit_tier"],
                    coerced["ai_priority"],
                    coerced["match_rationale"],
                    coerced["risk_flags"],
                    coerced["application_angle"],
                    int(job_id),
                ),
            )
        else:
            conn.execute(
                """
                UPDATE jobs
                SET
                    fit_score = ?,
                    fit_tier = ?,
                    ai_priority = ?,
                    match_rationale = ?,
                    risk_flags = ?,
                    application_angle = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    coerced["fit_score"],
                    coerced["fit_tier"],
                    coerced["ai_priority"],
                    coerced["match_rationale"],
                    coerced["risk_flags"],
                    coerced["application_angle"],
                    int(job_id),
                ),
            )


def upsert_job(job: Any, run_id: int | None = None) -> dict[str, Any]:
    payload = coerce_job_payload(job)
    duplicate_key = payload["duplicate_key"]
    effective_run_id = int(run_id or 0)

    if duplicate_key and is_removed_duplicate_key(duplicate_key):
        return {
            "status": "skipped_removed",
            "duplicate_key": duplicate_key,
            "job_id": None,
            "trust_promoted": False,
            "discovery_state": "skipped_removed",
        }

    existing = None
    if duplicate_key:
        existing = get_existing_job_by_duplicate_key(duplicate_key)
    if existing is None and payload["job_posting_url"]:
        existing = get_existing_job_by_posting_url(payload["job_posting_url"])

    if existing is None:
        job_id = insert_job(payload, run_id=effective_run_id)
        return {
            "status": "inserted",
            "duplicate_key": duplicate_key,
            "job_id": job_id,
            "trust_promoted": False,
            "discovery_state": "net_new",
        }

    existing_id = int(existing["id"])
    prior_last_seen_run_id = _to_int(existing["last_seen_run_id"], default=0)

    was_promoted = update_existing_job(existing_id, payload, run_id=effective_run_id)

    if effective_run_id and prior_last_seen_run_id == effective_run_id:
        discovery_state = "duplicate_in_run"
    else:
        discovery_state = "rediscovered"

    return {
        "status": "updated",
        "duplicate_key": duplicate_key or _clean(existing["duplicate_key"]),
        "job_id": existing_id,
        "trust_promoted": was_promoted,
        "discovery_state": discovery_state,
    }
