from datetime import datetime

import pandas as pd
import streamlit as st

from services.data import (
    get_page_size,
    load_sqlite_applied_roles,
    paginate_df,
    safe_text,
)
from services.settings import load_settings
from ui.components import render_bottom_pagination_controls


def parse_applied_date(value: object):
    text = safe_text(value)
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue

    return None


def build_applied_display_df(df_applied: pd.DataFrame) -> pd.DataFrame:
    df = df_applied.copy()

    if "Applied Date" not in df.columns:
        df["Applied Date"] = ""

    if "Company" not in df.columns:
        df["Company"] = ""

    if "Title" not in df.columns:
        df["Title"] = ""

    if "Job Posting URL" not in df.columns:
        df["Job Posting URL"] = ""

    df["__parsed_applied_date"] = df["Applied Date"].apply(parse_applied_date)

    today = datetime.now().date()

    def days_ago(date_value):
        if not date_value:
            return ""
        try:
            return (today - date_value).days
        except Exception:
            return ""

    df["Days Ago"] = df["__parsed_applied_date"].apply(days_ago)

    df = df.sort_values(
        by="__parsed_applied_date",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    df["Posting URL"] = df["Job Posting URL"].apply(safe_text)

    display_df = df[
        ["Company", "Title", "Applied Date", "Days Ago", "Posting URL"]
    ].copy()

    return display_df


def render_applied_roles() -> None:
    st.subheader("Applied Roles")

    settings = load_settings()

    try:
        df_applied = load_sqlite_applied_roles()
    except Exception as exc:
        st.error(f"Failed to load applied roles from SQLite: {exc}")
        st.stop()

    if df_applied.empty:
        st.info("No applied jobs yet.")
        return

    df_applied_display = build_applied_display_df(df_applied)

    default_jobs_per_page = int(settings.get("default_jobs_per_page", "10"))
    page_size = get_page_size("applied_roles_page_size", default=default_jobs_per_page)

    paged_df, current_page, total_pages = paginate_df(
        df_applied_display,
        page_size=page_size,
        page_key="applied_roles_current_page",
    )

    st.data_editor(
        paged_df,
        use_container_width=True,
        hide_index=True,
        disabled=True,
        column_config={
            "Company": st.column_config.TextColumn(
                "Company",
                width="medium",
            ),
            "Title": st.column_config.TextColumn(
                "Title",
                width="large",
            ),
            "Applied Date": st.column_config.TextColumn(
                "Applied Date",
                width="small",
            ),
            "Days Ago": st.column_config.NumberColumn(
                "Days Ago",
                width="small",
                format="%d",
            ),
            "Posting URL": st.column_config.LinkColumn(
                "Posting URL",
                width="medium",
                display_text="Open Posting",
            ),
        },
    )

    render_bottom_pagination_controls(
        total_rows=len(df_applied_display),
        current_page=current_page,
        total_pages=total_pages,
        page_key="applied_roles_current_page",
        control_key_prefix="bottom",
        page_size_state_key="applied_roles_page_size",
    )
