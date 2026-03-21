import json
from typing import Any

import pandas as pd

from config import APPLIED_SHEET, NEW_ROLES_SHEET, REMOVED_SHEET, SETTINGS_SHEET
from services.db import db_connection
from services.sheets_legacy import load_sheet


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _to_float(value: Any):
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_col(row: pd.Series, col: str) -> str:
    if col in row.index:
        return _clean(row[col])
    return ""


def _workflow_defaults(legacy_sheet: str, workflow_status: str, status: str, active_status: str):
    if legacy_sheet == APPLIED_SHEET:
        workflow_status = workflow_status or "Applied"
        status = status or "Applied"
    else:
        workflow_status = workflow_status or "New"
        status = status or "New"

    active_status = active_status or "Active"
    return workflow_status, status, active_status


def _build_job_payload(row: pd.Series, legacy_sheet: str) -> dict[str, Any]:
    workflow_status = _safe_col(row, "Workflow Status")
    applied_date = _safe_col(row, "Applied Date")
    status = _safe_col(row, "Status")
    active_status = _safe_col(row, "Active Status")

    workflow_status, status, active_status = _workflow_defaults(
        legacy_sheet=legacy_sheet,
        workflow_status=workflow_status,
        status=status,
        active_status=active_status,
    )

    return {
        "legacy_sheet": legacy_sheet,
        "legacy_row_number": row.name + 2,
        "date_found": _safe_col(row, "Date Found"),
        "date_last_validated": _safe_col(row, "Date Last Validated"),
        "company": _safe_col(row, "Company"),
        "title": _safe_col(row, "Title"),
        "role_family": _safe_col(row, "Role Family"),
        "normalized_title": _safe_col(row, "Normalized Title"),
        "location": _safe_col(row, "Location"),
        "remote_type": _safe_col(row, "Remote Type"),
        "dallas_dfw_match": _safe_col(row, "Dallas/DFW Match"),
        "company_careers_url": _safe_col(row, "Company Careers URL"),
        "job_posting_url": _safe_col(row, "Job Posting URL"),
        "ats_type": _safe_col(row, "ATS Type"),
        "requisition_id": _safe_col(row, "Requisition ID"),
        "source": _safe_col(row, "Source"),
        "compensation_raw": _safe_col(row, "Compensation Raw"),
        "compensation_status": _safe_col(row, "Compensation Status"),
        "validation_status": _safe_col(row, "Validation Status"),
        "validation_confidence": _safe_col(row, "Validation Confidence"),
        "fit_score": _to_float(row["Fit Score"]) if "Fit Score" in row.index else None,
        "fit_tier": _safe_col(row, "Fit Tier"),
        "ai_priority": _safe_col(row, "AI Priority"),
        "match_rationale": _safe_col(row, "Match Rationale"),
        "risk_flags": _safe_col(row, "Risk Flags"),
        "application_angle": _safe_col(row, "Application Angle"),
        "cover_letter_starter": _safe_col(row, "Cover Letter Starter"),
        "workflow_status": workflow_status,
        "applied_date": applied_date,
        "status": status,
        "duplicate_key": _safe_col(row, "Duplicate Key"),
        "active_status": active_status,
        "cover_letter_path": _safe_col(row, "Cover Letter Path"),
    }


def _insert_job_row(conn, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO jobs (
            legacy_sheet,
            legacy_row_number,
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
            ats_type,
            requisition_id,
            source,
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
            workflow_status,
            applied_date,
            status,
            duplicate_key,
            active_status,
            cover_letter_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["legacy_sheet"],
            payload["legacy_row_number"],
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
            payload["ats_type"],
            payload["requisition_id"],
            payload["source"],
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
            payload["workflow_status"],
            payload["applied_date"],
            payload["status"],
            payload["duplicate_key"],
            payload["active_status"],
            payload["cover_letter_path"],
        ),
    )


def _update_existing_job(conn, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET
            legacy_sheet = ?,
            legacy_row_number = ?,
            date_found = ?,
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
            ats_type = ?,
            requisition_id = ?,
            source = ?,
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
            workflow_status = ?,
            applied_date = ?,
            status = ?,
            active_status = ?,
            cover_letter_path = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE duplicate_key = ?
        """,
        (
            payload["legacy_sheet"],
            payload["legacy_row_number"],
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
            payload["ats_type"],
            payload["requisition_id"],
            payload["source"],
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
            payload["workflow_status"],
            payload["applied_date"],
            payload["status"],
            payload["active_status"],
            payload["cover_letter_path"],
            payload["duplicate_key"],
        ),
    )


def _insert_removed_row(conn, row: pd.Series) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO removed_jobs (
            removed_date,
            duplicate_key,
            company,
            title,
            location,
            job_posting_url,
            removal_reason,
            source_sheet
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _safe_col(row, "Removed Date"),
            _safe_col(row, "Duplicate Key"),
            _safe_col(row, "Company"),
            _safe_col(row, "Title"),
            _safe_col(row, "Location"),
            _safe_col(row, "Job Posting URL"),
            _safe_col(row, "Removal Reason"),
            _safe_col(row, "Source Sheet"),
        ),
    )


def _import_settings(conn, df: pd.DataFrame) -> int:
    imported = 0

    if df.empty:
        return imported

    columns_lower = {str(col).strip().lower(): col for col in df.columns}
    key_col = columns_lower.get("key")
    value_col = columns_lower.get("value")

    if key_col and value_col:
        for _, row in df.iterrows():
            key = _safe_col(row, key_col)
            value = _safe_col(row, value_col)
            if not key or key == "require_mark_as_applied":
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (key, value),
            )
            imported += 1
        return imported

    first_col = list(df.columns)[0]
    for _, row in df.iterrows():
        key = _clean(row[first_col])
        if not key or key == "require_mark_as_applied":
            continue

        value_parts = []
        for col in df.columns[1:]:
            part = _clean(row[col])
            if part:
                value_parts.append(part)

        value = " | ".join(value_parts)
        conn.execute(
            """
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (key, value),
        )
        imported += 1

    return imported


def _source_rank(sheet_name: str) -> int:
    if sheet_name == APPLIED_SHEET:
        return 2
    if sheet_name == NEW_ROLES_SHEET:
        return 1
    return 0


def _existing_job_for_duplicate_key(conn, duplicate_key: str):
    cur = conn.execute(
        """
        SELECT id, legacy_sheet, workflow_status, status, applied_date
        FROM jobs
        WHERE duplicate_key = ?
        LIMIT 1
        """,
        (duplicate_key,),
    )
    return cur.fetchone()


def import_all_from_sheets() -> dict[str, Any]:
    new_df = load_sheet(NEW_ROLES_SHEET)
    applied_df = load_sheet(APPLIED_SHEET)
    removed_df = load_sheet(REMOVED_SHEET)
    settings_df = load_sheet(SETTINGS_SHEET)

    results = {
        "new_roles_rows_seen": int(len(new_df)),
        "applied_rows_seen": int(len(applied_df)),
        "removed_rows_seen": int(len(removed_df)),
        "settings_rows_seen": int(len(settings_df)),
        "jobs_imported": 0,
        "jobs_inserted": 0,
        "jobs_updated_from_collision": 0,
        "jobs_skipped_from_collision": 0,
        "jobs_without_duplicate_key": 0,
        "removed_imported": 0,
        "settings_imported": 0,
        "collisions": [],
    }

    with db_connection() as conn:
        conn.execute("DELETE FROM jobs")
        conn.execute("DELETE FROM removed_jobs")
        conn.execute("DELETE FROM app_settings")

        ordered_sources = [
            (NEW_ROLES_SHEET, new_df),
            (APPLIED_SHEET, applied_df),
        ]

        for legacy_sheet, df in ordered_sources:
            for _, row in df.iterrows():
                payload = _build_job_payload(row, legacy_sheet)
                duplicate_key = payload["duplicate_key"]

                results["jobs_imported"] += 1

                if not duplicate_key:
                    _insert_job_row(conn, payload)
                    results["jobs_inserted"] += 1
                    results["jobs_without_duplicate_key"] += 1
                    continue

                existing = _existing_job_for_duplicate_key(conn, duplicate_key)

                if existing is None:
                    _insert_job_row(conn, payload)
                    results["jobs_inserted"] += 1
                    continue

                existing_rank = _source_rank(existing["legacy_sheet"])
                incoming_rank = _source_rank(legacy_sheet)

                collision_record = {
                    "duplicate_key": duplicate_key,
                    "existing_sheet": existing["legacy_sheet"],
                    "incoming_sheet": legacy_sheet,
                    "existing_workflow_status": existing["workflow_status"],
                    "incoming_workflow_status": payload["workflow_status"],
                    "resolution": "",
                }

                if incoming_rank >= existing_rank:
                    _update_existing_job(conn, payload)
                    results["jobs_updated_from_collision"] += 1
                    collision_record["resolution"] = f"kept_{legacy_sheet.lower().replace(' ', '_')}"
                else:
                    results["jobs_skipped_from_collision"] += 1
                    collision_record["resolution"] = f"kept_{existing['legacy_sheet'].lower().replace(' ', '_')}"

                results["collisions"].append(collision_record)

        for _, row in removed_df.iterrows():
            _insert_removed_row(conn, row)
            results["removed_imported"] += 1

        results["settings_imported"] = _import_settings(conn, settings_df)

        conn.execute(
            """
            INSERT INTO import_runs (source_name, completed_at, status, details_json)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?)
            """,
            (
                "google_sheets",
                "completed",
                json.dumps(results),
            ),
        )

    return results
