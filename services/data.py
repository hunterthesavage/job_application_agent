import math
import re
import sqlite3
import subprocess
import webbrowser
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATABASE_PATH


NEW_ROLES_COLUMNS = [
    "Company",
    "Title",
    "Location",
    "Fit Score",
    "Fit Tier",
    "AI Recommendation",
    "Last Refreshed",
    "Match Rationale",
    "Risk Flags",
    "Application Angle",
    "Compensation Raw",
    "Job Posting URL",
    "Duplicate Key",
    "Cover Letter Path",
    "Workflow Status",
    "Active Status",
    "Date Found",
    "Source",
    "Source Type",
    "Source Trust",
    "Source Detail",
    "Discovery State",
]

APPLIED_ROLES_COLUMNS = [
    "Company",
    "Title",
    "Applied Date",
    "Job Posting URL",
    "Fit Score",
    "Workflow Status",
    "Active Status",
]


def _empty_new_roles_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=["__job_id__", "__seen_count__", "__last_seen_run_id__", *NEW_ROLES_COLUMNS])
    df["__job_id__"] = pd.Series(dtype="int64")
    df["__seen_count__"] = pd.Series(dtype="int64")
    df["__last_seen_run_id__"] = pd.Series(dtype="int64")
    return df.set_index("__job_id__", drop=True)


def _empty_applied_roles_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=["__job_id__", *APPLIED_ROLES_COLUMNS])
    df["__job_id__"] = pd.Series(dtype="int64")
    return df.set_index("__job_id__", drop=True)


@st.cache_data(ttl=30)
def load_sqlite_new_roles() -> pd.DataFrame:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        query = """
        WITH latest_run AS (
            SELECT COALESCE(MAX(id), 0) AS latest_run_id
            FROM ingestion_runs
        )
        SELECT
            jobs.id AS "__job_id__",
            jobs.company AS "Company",
            jobs.title AS "Title",
            jobs.location AS "Location",
            jobs.fit_score AS "Fit Score",
            jobs.fit_tier AS "Fit Tier",
            jobs.ai_priority AS "AI Recommendation",
            jobs.updated_at AS "Last Refreshed",
            jobs.match_rationale AS "Match Rationale",
            jobs.risk_flags AS "Risk Flags",
            jobs.application_angle AS "Application Angle",
            jobs.compensation_raw AS "Compensation Raw",
            jobs.job_posting_url AS "Job Posting URL",
            jobs.duplicate_key AS "Duplicate Key",
            jobs.cover_letter_path AS "Cover Letter Path",
            jobs.workflow_status AS "Workflow Status",
            jobs.active_status AS "Active Status",
            jobs.date_found AS "Date Found",
            jobs.source AS "Source",
            jobs.source_type AS "Source Type",
            jobs.source_trust AS "Source Trust",
            jobs.source_detail AS "Source Detail",
            COALESCE(jobs.seen_count, 0) AS "__seen_count__",
            COALESCE(jobs.last_seen_run_id, 0) AS "__last_seen_run_id__",
            CASE
                WHEN COALESCE(jobs.last_seen_run_id, 0) = (SELECT latest_run_id FROM latest_run)
                     AND COALESCE(jobs.seen_count, 0) <= 1
                    THEN 'Net New'
                WHEN COALESCE(jobs.last_seen_run_id, 0) = (SELECT latest_run_id FROM latest_run)
                     AND COALESCE(jobs.seen_count, 0) > 1
                    THEN 'Rediscovered'
                ELSE ''
            END AS "Discovery State"
        FROM jobs
        WHERE jobs.workflow_status = 'New'
          AND COALESCE(jobs.active_status, 'Active') = 'Active'
        ORDER BY
            CASE
                WHEN jobs.fit_score IS NULL THEN 1
                ELSE 0
            END,
            jobs.fit_score DESC,
            jobs.company ASC,
            jobs.title ASC
        """
        try:
            df = pd.read_sql_query(query, conn)
        except (pd.errors.DatabaseError, sqlite3.OperationalError) as exc:
            message = str(exc).lower()
            if "no such table" in message or "unable to open database file" in message:
                return _empty_new_roles_df()
            raise
    finally:
        conn.close()

    if df.empty:
        return _empty_new_roles_df()

    df["__job_id__"] = pd.to_numeric(df["__job_id__"], errors="coerce").fillna(0).astype(int)
    df["__seen_count__"] = pd.to_numeric(df["__seen_count__"], errors="coerce").fillna(0).astype(int)
    df["__last_seen_run_id__"] = pd.to_numeric(df["__last_seen_run_id__"], errors="coerce").fillna(0).astype(int)
    df = df.set_index("__job_id__", drop=True)

    return df


@st.cache_data(ttl=30)
def load_sqlite_applied_roles() -> pd.DataFrame:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        query = """
        SELECT
            id AS "__job_id__",
            company AS "Company",
            title AS "Title",
            applied_date AS "Applied Date",
            job_posting_url AS "Job Posting URL",
            fit_score AS "Fit Score",
            workflow_status AS "Workflow Status",
            active_status AS "Active Status"
        FROM jobs
        WHERE workflow_status = 'Applied'
        ORDER BY
            COALESCE(applied_date, '') DESC,
            company ASC,
            title ASC
        """
        try:
            df = pd.read_sql_query(query, conn)
        except (pd.errors.DatabaseError, sqlite3.OperationalError) as exc:
            message = str(exc).lower()
            if "no such table" in message or "unable to open database file" in message:
                return _empty_applied_roles_df()
            raise
    finally:
        conn.close()

    if df.empty:
        return _empty_applied_roles_df()

    df["__job_id__"] = pd.to_numeric(df["__job_id__"], errors="coerce").fillna(0).astype(int)
    df = df.set_index("__job_id__", drop=True)

    return df


def run_command(command: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def open_url(url: str) -> bool:
    try:
        webbrowser.open_new_tab(str(url or "").strip())
        return True
    except Exception:
        return False


def safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_value(row: pd.Series, key: str) -> str:
    return safe_text(row.get(key, ""))


def normalize_fit_score(value: object) -> float:
    text = safe_text(value)
    if not text:
        return -1.0

    try:
        return float(text)
    except Exception:
        match = re.search(r"(\d+(\.\d+)?)", text)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                return -1.0
        return -1.0


def is_remote_location(location: str) -> bool:
    text = safe_text(location).lower()
    return "remote" in text


def has_compensation(text: str) -> bool:
    text = safe_text(text)
    if not text:
        return False

    lowered = text.lower()
    blockers = {
        "not disclosed",
        "unknown",
        "n/a",
        "na",
        "none",
        "not listed",
        "not provided",
    }

    if lowered in blockers:
        return False

    return True


def apply_new_role_filters(df: pd.DataFrame) -> pd.DataFrame:
    df_filtered = df.copy()

    min_fit = st.session_state.get("filter_min_fit", "Any")
    discovery_state = st.session_state.get("filter_discovery_state", "All")
    remote_only = st.session_state.get("filter_remote_only", False)
    compensation_only = st.session_state.get("filter_compensation_only", False)

    if min_fit != "Any" and "Fit Score" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["Fit Score"].apply(normalize_fit_score) >= float(min_fit)
        ]

    if discovery_state != "All" and "Discovery State" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["Discovery State"].apply(safe_text) == discovery_state
        ]

    if remote_only and "Location" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["Location"].apply(is_remote_location)
        ]

    if compensation_only and "Compensation Raw" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["Compensation Raw"].apply(has_compensation)
        ]

    return df_filtered


def calculate_kpis(df_new_roles: pd.DataFrame, df_applied: pd.DataFrame) -> dict[str, str]:
    new_roles_count = str(len(df_new_roles))

    applied_this_week = "0"
    if not df_applied.empty and "Applied Date" in df_applied.columns:
        today = datetime.now().date()
        count = 0

        for value in df_applied["Applied Date"]:
            text = safe_text(value)
            if not text:
                continue

            try:
                applied_date = datetime.strptime(text, "%Y-%m-%d").date()
                if (today - applied_date).days <= 7:
                    count += 1
            except Exception:
                continue

        applied_this_week = str(count)

    avg_fit = "—"
    if not df_new_roles.empty and "Fit Score" in df_new_roles.columns:
        scores = df_new_roles["Fit Score"].apply(normalize_fit_score)
        valid_scores = scores[scores >= 0]
        if not valid_scores.empty:
            avg_fit = str(int(round(valid_scores.mean())))

    return {
        "new_roles": new_roles_count,
        "applied_this_week": applied_this_week,
        "avg_fit": avg_fit,
    }


def get_page_size(state_key: str, default: int = 10) -> int:
    if state_key not in st.session_state:
        st.session_state[state_key] = default
    return int(st.session_state[state_key])


def paginate_df(
    df: pd.DataFrame,
    page_size: int,
    page_key: str,
) -> tuple[pd.DataFrame, int, int]:
    total_rows = len(df)
    total_pages = max(1, math.ceil(total_rows / page_size))

    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    current_page = int(st.session_state[page_key])
    current_page = max(1, min(current_page, total_pages))
    st.session_state[page_key] = current_page

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    paged_df = df.iloc[start_idx:end_idx]

    return paged_df, current_page, total_pages


def slug_to_words(text: str) -> str:
    text = safe_text(text)
    if not text:
        return ""
    text = re.sub(r"[_\\-]+", " ", text)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def normalize_compare_text(text: str) -> str:
    text = safe_text(text).lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def clean_display_title(company: str, title: str) -> str:
    company = safe_text(company)
    title = safe_text(title)

    if not company and not title:
        return ""
    if not title:
        return company
    if not company:
        return title

    pretty_company = slug_to_words(company) or company
    company_norm = normalize_compare_text(company)
    company_words_norm = normalize_compare_text(pretty_company)
    title_norm = normalize_compare_text(title)

    title_parts = [part.strip() for part in re.split(r"\\s[-–—]\\s", title) if part.strip()]

    if len(title_parts) >= 2:
        first_part = title_parts[0]
        first_part_norm = normalize_compare_text(first_part)

        if first_part_norm and first_part_norm not in {company_norm, company_words_norm}:
            return title

        if first_part_norm in {company_norm, company_words_norm}:
            return " - ".join(title_parts[1:]).strip() or title

    if company_norm and company_norm in title_norm:
        return title

    if company_words_norm and company_words_norm in title_norm:
        return title

    return f"{pretty_company} - {title}"
