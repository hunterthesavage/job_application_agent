import html

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_VERSION
from services.cover_letters import generate_cover_letter_for_job_id
from services.data import (
    clean_display_title,
    get_page_size,
    open_url,
    safe_value,
)
from services.openai_key import get_effective_openai_api_key
from services.settings import load_settings
from services.sqlite_actions import mark_job_as_applied, remove_job
from services.status import get_system_status
from services.ui_busy import app_is_busy, current_busy_label, start_busy, stop_busy


PAGE_SIZE_OPTIONS = [5, 10, 20, 500]
FIT_SCORE_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]


def _widget_nonce() -> int:
    return int(st.session_state.get("configuration_widget_nonce", 0))


def _get_openai_badge() -> tuple[str, str]:
    _ = load_settings()
    status = get_system_status()

    key_status = str(status.get("openai_api_key_status", "Not configured")).strip().lower()

    if key_status == "validated":
        return "OpenAI: Validated", "validated"

    if key_status in {"saved not validated", "configured"}:
        return "OpenAI: Configured", "saved"

    return "OpenAI: Not Configured", "not-configured"


def render_hero() -> None:
    badge_text, badge_class = _get_openai_badge()

    busy_text = ""
    if app_is_busy() and current_busy_label():
        busy_text = f'<div class="app-busy-banner">Working: {html.escape(current_busy_label())}</div>'

    st.markdown(
        f"""
        <div class="hero-wrap">
            <div style="display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;">
                <div class="hero-title">
                    <span class="hero-title-main">{html.escape(APP_NAME)}</span>
                    <span class="hero-title-version">{html.escape(APP_VERSION)}</span>
                </div>
                <div class="openai-badge openai-badge-{html.escape(badge_class)}">{html.escape(badge_text)}</div>
            </div>
            <div class="hero-subtle">High-signal roles, faster action, cleaner workflow.</div>
            {busy_text}
        </div>

        <style>
        .openai-badge {{
            font-size: 0.9rem;
            font-weight: 600;
            padding: 8px 12px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.12);
            letter-spacing: 0.01em;
            white-space: nowrap;
        }}
        .openai-badge-not-configured {{
            background: rgba(255, 99, 99, 0.12);
            color: #ffb3b3;
        }}
        .openai-badge-saved {{
            background: rgba(255, 193, 7, 0.12);
            color: #ffd666;
        }}
        .openai-badge-validated {{
            background: rgba(46, 204, 113, 0.12);
            color: #9af0b7;
        }}
        .app-busy-banner {{
            margin-top: 12px;
            font-size: 0.9rem;
            font-weight: 600;
            color: #b8c7ff;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(kpis: dict[str, str]) -> None:
    st.markdown(
        f"""
        <div class="kpi-grid">
            <div class="kpi-card blue">
                <div class="kpi-label">New Roles</div>
                <div class="kpi-value">{html.escape(kpis["new_roles"])}</div>
            </div>
            <div class="kpi-card green">
                <div class="kpi-label">Applied This Week</div>
                <div class="kpi-value">{html.escape(kpis["applied_this_week"])}</div>
            </div>
            <div class="kpi-card orange">
                <div class="kpi-label">Avg Fit Score</div>
                <div class="kpi-value">{html.escape(kpis["avg_fit"])}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_filter_bar() -> None:
    st.markdown('<div class="filters-shell">', unsafe_allow_html=True)
    st.markdown('<div class="filters-heading">Filters</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1, 1.2])
    nonce = _widget_nonce()

    with c1:
        st.markdown('<div class="control-label">Minimum Fit Score</div>', unsafe_allow_html=True)

        current_fit = st.session_state.get("filter_min_fit", "Any")
        selector_key = f"filter_min_fit_selector_{nonce}"

        selected_fit = st.selectbox(
            "Minimum Fit Score",
            FIT_SCORE_OPTIONS,
            index=FIT_SCORE_OPTIONS.index(current_fit) if current_fit in FIT_SCORE_OPTIONS else 0,
            key=selector_key,
            label_visibility="collapsed",
            disabled=app_is_busy(),
        )

        if selected_fit != st.session_state.get("filter_min_fit", "Any"):
            st.session_state["filter_min_fit"] = selected_fit
            st.session_state["new_roles_current_page"] = 1
            st.rerun()

    with c2:
        st.markdown('<div class="control-label">Remote Only</div>', unsafe_allow_html=True)
        st.toggle(
            "Remote Only",
            key="filter_remote_only",
            label_visibility="collapsed",
            disabled=app_is_busy(),
        )

    with c3:
        st.markdown('<div class="control-label">Compensation Available Only</div>', unsafe_allow_html=True)
        st.toggle(
            "Compensation Available Only",
            key="filter_compensation_only",
            label_visibility="collapsed",
            disabled=app_is_busy(),
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_bottom_pagination_controls(
    total_rows: int,
    current_page: int,
    total_pages: int,
    page_key: str,
    control_key_prefix: str,
    page_size_state_key: str,
) -> None:
    st.markdown(
        f"""
        <div class="bottom-controls-wrap">
            <div class="pagination-summary">
                Page {current_page} of {total_pages} | Showing {total_rows} total jobs
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_space, prev_col, next_col, right_space = st.columns([4, 1.15, 1.15, 4])

    with prev_col:
        if st.button(
            "← Previous",
            key=f"{control_key_prefix}_{page_key}_prev",
            disabled=current_page <= 1 or app_is_busy(),
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = max(1, current_page - 1)
            st.rerun()

    with next_col:
        if st.button(
            "Next →",
            key=f"{control_key_prefix}_{page_key}_next",
            disabled=current_page >= total_pages or app_is_busy(),
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = min(total_pages, current_page + 1)
            st.rerun()

    st.markdown('<div class="jobs-per-page-label">Jobs per page</div>', unsafe_allow_html=True)

    select_left, select_mid, select_right = st.columns([4, 2, 4])

    page_size = get_page_size(page_size_state_key, default=10)
    nonce = _widget_nonce()
    selector_key = f"{page_size_state_key}_selector_{nonce}"

    with select_mid:
        selected_page_size = st.selectbox(
            "Jobs per page",
            PAGE_SIZE_OPTIONS,
            index=PAGE_SIZE_OPTIONS.index(page_size) if page_size in PAGE_SIZE_OPTIONS else 1,
            key=selector_key,
            label_visibility="collapsed",
            disabled=app_is_busy(),
        )

    if selected_page_size != st.session_state[page_size_state_key]:
        st.session_state[page_size_state_key] = selected_page_size
        st.session_state[page_key] = 1
        st.rerun()


def render_job_card(
    job_id: int,
    row: pd.Series,
) -> None:
    company = safe_value(row, "Company")
    title = safe_value(row, "Title")
    location = safe_value(row, "Location")
    fit_score = safe_value(row, "Fit Score")
    compensation_raw = safe_value(row, "Compensation Raw")
    job_url = safe_value(row, "Job Posting URL")

    display_title = clean_display_title(company, title)
    apply_ready_key = f"apply_ready_{job_id}"

    if apply_ready_key not in st.session_state:
        st.session_state[apply_ready_key] = False

    st.markdown('<div class="job-card">', unsafe_allow_html=True)

    left, right = st.columns([4.2, 3.0], vertical_alignment="center")

    with left:
        st.markdown(
            f'<div class="job-title">{html.escape(display_title)}</div>',
            unsafe_allow_html=True,
        )

        pills = []
        if location:
            pills.append(f'<span class="meta-pill location">Location: {html.escape(location)}</span>')
        if fit_score:
            pills.append(f'<span class="meta-pill fit">Fit Score: {html.escape(fit_score)}</span>')
        if compensation_raw:
            pills.append(f'<span class="meta-pill comp">Compensation: {html.escape(compensation_raw)}</span>')

        if pills:
            st.markdown(f'<div class="meta-row">{"".join(pills)}</div>', unsafe_allow_html=True)

    with right:
        btn1, btn2, btn3, btn4 = st.columns([1.05, 0.95, 1.15, 0.95])

        api_key = get_effective_openai_api_key()
        cover_letter_enabled = bool(api_key)
        cover_letter_help = (
            "Generate a tailored cover letter"
            if cover_letter_enabled
            else "No OpenAI API key is configured. Add one in Settings > OpenAI API."
        )

        with btn1:
            if st.button(
                "✍️ Cover Letter",
                key=f"generate_cover_{job_id}",
                use_container_width=True,
                type="secondary",
                disabled=app_is_busy() or (not cover_letter_enabled),
                help=cover_letter_help,
            ):
                try:
                    start_busy("Generating cover letter")
                    with st.spinner("Creating cover letter file..."):
                        result = generate_cover_letter_for_job_id(job_id)
                    st.success("Cover letter created.")
                    st.text(result["output_path"])
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error("Failed to generate cover letter.")
                    st.text(str(exc))
                finally:
                    stop_busy()

        with btn2:
            apply_disabled = not bool(job_url)

            if st.button(
                "🚀 Apply",
                key=f"apply_{job_id}",
                use_container_width=True,
                type="primary",
                disabled=app_is_busy() or apply_disabled,
            ):
                opened = open_url(job_url)
                if opened:
                    st.session_state[apply_ready_key] = True
                    st.rerun()
                else:
                    st.warning("Could not automatically open the URL.")

        with btn3:
            if st.button(
                "Mark as Applied",
                key=f"mark_applied_{job_id}",
                use_container_width=True,
                type="secondary",
                disabled=app_is_busy() or (not st.session_state[apply_ready_key]),
            ):
                try:
                    start_busy("Marking job as applied")
                    with st.spinner("Marking job as applied..."):
                        mark_job_as_applied(job_id)
                    st.session_state[apply_ready_key] = False
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error("Failed to move job.")
                    st.text(str(exc))
                finally:
                    stop_busy()

        with btn4:
            if st.button(
                "Remove Job",
                key=f"remove_job_{job_id}",
                use_container_width=True,
                type="secondary",
                disabled=app_is_busy(),
            ):
                try:
                    start_busy("Removing job")
                    with st.spinner("Removing job..."):
                        remove_job(job_id)
                    st.session_state[apply_ready_key] = False
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error("Failed to remove job.")
                    st.text(str(exc))
                finally:
                    stop_busy()

    st.markdown("</div>", unsafe_allow_html=True)
