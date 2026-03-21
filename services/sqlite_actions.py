from datetime import datetime

from services.db import db_connection


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def get_job_by_id(job_id: int) -> dict | None:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

    return _row_to_dict(row)


def mark_job_as_applied(job_id: int) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Job id {job_id} not found.")

        conn.execute(
            """
            UPDATE jobs
            SET
                workflow_status = 'Applied',
                status = 'Applied',
                applied_date = CASE
                    WHEN TRIM(COALESCE(applied_date, '')) = '' THEN ?
                    ELSE applied_date
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (today, job_id),
        )

        updated = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

    return _row_to_dict(updated)


def remove_job(job_id: int, removal_reason: str = "Removed in app") -> dict:
    removed_date = datetime.now().strftime("%Y-%m-%d")

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Job id {job_id} not found.")

        job = dict(row)

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
                removed_date,
                str(job.get("duplicate_key", "") or "").strip(),
                str(job.get("company", "") or "").strip(),
                str(job.get("title", "") or "").strip(),
                str(job.get("location", "") or "").strip(),
                str(job.get("job_posting_url", "") or "").strip(),
                removal_reason,
                str(job.get("legacy_sheet", "") or "").strip(),
            ),
        )

        conn.execute(
            """
            DELETE FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        )

    return job


def record_cover_letter_artifact(job_id: int, output_path: str) -> dict:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Job id {job_id} not found.")

        job = dict(row)

        conn.execute(
            """
            UPDATE jobs
            SET
                cover_letter_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (output_path, job_id),
        )

        conn.execute(
            """
            INSERT INTO cover_letter_artifacts (
                job_duplicate_key,
                company,
                title,
                output_path
            ) VALUES (?, ?, ?, ?)
            """,
            (
                str(job.get("duplicate_key", "") or "").strip(),
                str(job.get("company", "") or "").strip(),
                str(job.get("title", "") or "").strip(),
                output_path,
            ),
        )

        updated = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

    return _row_to_dict(updated)
