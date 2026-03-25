from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.db import db_connection, initialize_database


SUPPORTED_SCHEMA_VERSION = "1.0"
ALLOWED_CAREERS_STATUSES = {"validated", "candidate", "blocked", "not_found", "unresolved"}
ALLOWED_REVIEW_STATUSES = {"approved", "needs_review", "rejected", "unreviewed"}
IMPORTABLE_CAREERS_STATUSES = {"validated", "candidate"}
REQUIRED_RECORD_FIELDS = {
    "company_name",
    "canonical_company_domain",
    "careers_url",
    "careers_url_status",
    "review_status",
    "ats_provider",
    "confidence_score",
    "last_validated_at",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_bool(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if str(value or "").strip().lower() in {"1", "true", "yes", "y"} else 0


def _derive_extraction_method(ats_provider: str) -> str:
    normalized = _clean_text(ats_provider).lower()
    if normalized in {"greenhouse", "ashby", "lever", "workday", "smartrecruiters", "icims"}:
        return normalized
    if normalized in {"custom", "unknown"}:
        return "careers_page"
    if normalized:
        return normalized
    return "careers_page"


def _merge_notes(record: dict[str, Any]) -> str:
    parts = [
        _clean_text(record.get("confidence_reason")),
        _clean_text(record.get("review_notes")),
        _clean_text(record.get("notes")),
    ]
    return " | ".join(part for part in parts if part)


def _load_contract_payload(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("Import file must be a JSON object.")

    schema_version = _clean_text(payload.get("schema_version"))
    if not schema_version:
        raise ValueError("Import file is missing schema_version.")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version '{schema_version}'. Expected '{SUPPORTED_SCHEMA_VERSION}'."
        )

    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("Import file must contain a records list.")

    return payload


def _find_company_id(conn, company_name: str, canonical_domain: str) -> int | None:
    if canonical_domain:
        row = conn.execute(
            """
            SELECT id
            FROM companies
            WHERE canonical_domain = ?
            LIMIT 1
            """,
            (canonical_domain,),
        ).fetchone()
        if row is not None:
            return int(row["id"])

    row = conn.execute(
        """
        SELECT id
        FROM companies
        WHERE name = ?
        LIMIT 1
        """,
        (company_name,),
    ).fetchone()
    if row is None:
        return None
    return int(row["id"])


def _upsert_company(conn, record: dict[str, Any]) -> tuple[int, str]:
    company_name = _clean_text(record.get("company_name"))
    canonical_domain = _clean_text(record.get("canonical_company_domain")).lower()
    company_id = _find_company_id(conn, company_name, canonical_domain)

    if company_id is None:
        cursor = conn.execute(
            """
            INSERT INTO companies (
                name,
                canonical_domain,
                active,
                created_at,
                updated_at
            )
            VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (company_name, canonical_domain),
        )
        return int(cursor.lastrowid), "inserted"

    conn.execute(
        """
        UPDATE companies
        SET
            name = ?,
            canonical_domain = CASE
                WHEN canonical_domain = '' AND ? <> '' THEN ?
                ELSE canonical_domain
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (company_name, canonical_domain, canonical_domain, company_id),
    )
    return company_id, "updated"


def _upsert_endpoint(conn, company_id: int, record: dict[str, Any]) -> str:
    endpoint_url = _clean_text(record.get("careers_url"))
    ats_provider = _clean_text(record.get("ats_provider")).lower()
    review_status = _clean_text(record.get("review_status")).lower()
    careers_url_status = _clean_text(record.get("careers_url_status")).lower()
    confidence_score = float(record.get("confidence_score") or 0)
    last_validated_at = _clean_text(record.get("last_validated_at"))
    notes = _merge_notes(record)
    active = 0 if review_status == "rejected" else 1
    is_primary = _normalize_bool(record.get("is_primary_careers_url"))
    extraction_method = _derive_extraction_method(ats_provider)

    existing = conn.execute(
        """
        SELECT id
        FROM hiring_endpoints
        WHERE company_id = ? AND endpoint_url = ?
        LIMIT 1
        """,
        (company_id, endpoint_url),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO hiring_endpoints (
                company_id,
                endpoint_url,
                endpoint_type,
                ats_vendor,
                extraction_method,
                discovery_source,
                confidence_score,
                health_score,
                review_status,
                careers_url_status,
                is_primary,
                last_validated_at,
                active,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, 'careers_page', ?, ?, 'fortune500_registry_import', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                company_id,
                endpoint_url,
                ats_provider,
                extraction_method,
                confidence_score,
                confidence_score,
                review_status,
                careers_url_status,
                is_primary,
                last_validated_at,
                active,
                notes,
            ),
        )
        return "inserted"

    conn.execute(
        """
        UPDATE hiring_endpoints
        SET
            endpoint_type = 'careers_page',
            ats_vendor = ?,
            extraction_method = ?,
            discovery_source = 'fortune500_registry_import',
            confidence_score = ?,
            health_score = ?,
            review_status = ?,
            careers_url_status = ?,
            is_primary = ?,
            last_validated_at = ?,
            active = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = ? AND endpoint_url = ?
        """,
        (
            ats_provider,
            extraction_method,
            confidence_score,
            confidence_score,
            review_status,
            careers_url_status,
            is_primary,
            last_validated_at,
            active,
            notes,
            company_id,
            endpoint_url,
        ),
    )
    return "updated"


def _record_source_layer_run(
    conn,
    *,
    mode: str,
    import_file_path: str,
    imported_records: int,
    errors: int,
    notes: str,
) -> None:
    conn.execute(
        """
        INSERT INTO source_layer_runs (
            started_at,
            finished_at,
            mode,
            import_file_path,
            imported_records,
            errors,
            notes
        )
        VALUES (CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
        """,
        (mode, import_file_path, imported_records, errors, notes),
    )


def _validate_record_shape(record: dict[str, Any]) -> list[str]:
    missing_fields = [field for field in REQUIRED_RECORD_FIELDS if not _clean_text(record.get(field))]
    if missing_fields:
        return [f"missing required field(s): {', '.join(sorted(missing_fields))}"]

    careers_url_status = _clean_text(record.get("careers_url_status")).lower()
    review_status = _clean_text(record.get("review_status")).lower()
    errors: list[str] = []

    if careers_url_status not in ALLOWED_CAREERS_STATUSES:
        errors.append(f"invalid careers_url_status: {careers_url_status}")
    if review_status not in ALLOWED_REVIEW_STATUSES:
        errors.append(f"invalid review_status: {review_status}")

    try:
        float(record.get("confidence_score"))
    except Exception:
        errors.append("confidence_score must be numeric")

    return errors


def import_employer_endpoints(file_path: str | Path) -> dict[str, Any]:
    initialize_database()
    path = Path(file_path)
    payload = _load_contract_payload(path)
    records = payload.get("records", []) or []

    summary = {
        "status": "completed",
        "file_path": str(path),
        "schema_version": _clean_text(payload.get("schema_version")),
        "total_records": len(records),
        "company_inserted": 0,
        "company_updated": 0,
        "endpoint_inserted": 0,
        "endpoint_updated": 0,
        "skipped": 0,
        "invalid": 0,
        "errors": [],
    }

    with db_connection() as conn:
        for index, raw_record in enumerate(records, start=1):
            if not isinstance(raw_record, dict):
                summary["invalid"] += 1
                summary["errors"].append(f"Record {index}: record must be an object")
                continue

            validation_errors = _validate_record_shape(raw_record)
            if validation_errors:
                summary["invalid"] += 1
                summary["errors"].append(f"Record {index}: {'; '.join(validation_errors)}")
                continue

            careers_url = _clean_text(raw_record.get("careers_url"))
            careers_url_status = _clean_text(raw_record.get("careers_url_status")).lower()

            if not careers_url or careers_url_status not in IMPORTABLE_CAREERS_STATUSES:
                summary["skipped"] += 1
                continue

            company_id, company_action = _upsert_company(conn, raw_record)
            if company_action == "inserted":
                summary["company_inserted"] += 1
            else:
                summary["company_updated"] += 1

            endpoint_action = _upsert_endpoint(conn, company_id, raw_record)
            if endpoint_action == "inserted":
                summary["endpoint_inserted"] += 1
            else:
                summary["endpoint_updated"] += 1

        imported_records = summary["endpoint_inserted"] + summary["endpoint_updated"]
        _record_source_layer_run(
            conn,
            mode="import",
            import_file_path=str(path),
            imported_records=imported_records,
            errors=len(summary["errors"]),
            notes=(
                f"Imported {imported_records} endpoint record(s); "
                f"skipped {summary['skipped']}; invalid {summary['invalid']}."
            ),
        )

    if summary["errors"]:
        summary["status"] = "completed_with_errors"

    return summary
