from __future__ import annotations

from datetime import datetime

from services.ai_job_scoring import (
    apply_score_to_job_payload,
    load_scoring_profile_text,
    score_accepted_job,
)
from services.ai_job_scrub import apply_scrub_to_job_payload, scrub_accepted_job
from services.db import db_connection
from services.job_store import update_job_scoring_fields


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


def rescore_job(job_id: int) -> dict:
    job = get_job_by_id(job_id)
    if job is None:
        raise ValueError(f"Job id {job_id} not found.")

    resume_profile_text, resume_profile_source = load_scoring_profile_text()
    if not str(resume_profile_text or "").strip():
        raise ValueError(
            "No saved Profile Context or fallback profile text was found. "
            "Add content in Settings -> Profile Context, or use profile_context.txt / JOB_AGENT_RESUME_PROFILE as fallback."
        )

    score_result = score_accepted_job(job, resume_profile_text)
    score_status = str(score_result.get("status", "") or "").strip().lower()
    if score_status != "scored":
        raise ValueError(
            f"Job rescore was skipped with status '{score_status or 'unknown'}' "
            f"using profile source '{resume_profile_source}'."
        )

    apply_score_to_job_payload(job, score_result)
    scrub_result = scrub_accepted_job(job, resume_profile_text)
    apply_scrub_to_job_payload(job, scrub_result)
    update_job_scoring_fields(job_id, job)

    updated = get_job_by_id(job_id)
    if updated is None:
        raise ValueError(f"Job id {job_id} could not be reloaded after rescoring.")

    return updated


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
