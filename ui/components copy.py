import html
import sys

import pandas as pd
import streamlit as st

from services.data import (
    clean_display_title,
    get_page_size,
    open_url,
    run_command,
    safe_value,
)


PAGE_SIZE_OPTIONS = [5, 10, 20, 500]
FIT_SCORE_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero-wrap">
            <div class="hero-title">
                <span class="hero-title-main">Job Application Agent</span>
                <span class="hero-title-version">v1.1</span>
            </div>
            <div class="hero-subtle">High-signal roles, faster action, cleaner workflow.</div>
        </div>
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

    with c1:
        st.markdown('<div class="control-label">Minimum Fit Score</div>', unsafe_allow_html=True)

        fit_selector_key = "filter_min_fit_selector"
        current_fit = st.session_state.get("filter_min_fit", "Any")

        if fit_selector_key in st.session_state:
            selected_fit = st.selectbox(
                "Minimum Fit Score",
                FIT_SCORE_OPTIONS,
                key=fit_selector_key,
                label_visibility="collapsed",
            )
        else:
            selected_fit = st.selectbox(
                "Minimum Fit Score",
                FIT_SCORE_OPTIONS,
                index=FIT_SCORE_OPTIONS.index(current_fit) if current_fit in FIT_SCORE_OPTIONS else 0,
                key=fit_selector_key,
                label_visibility="collapsed",
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
        )

    with c3:
        st.markdown('<div class="control-label">Compensation Available Only</div>', unsafe_allow_html=True)
        st.toggle(
            "Compensation Available Only",
            key="filter_compensation_only",
            label_visibility="collapsed",
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
            disabled=current_page <= 1,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = max(1, current_page - 1)
            st.rerun()

    with next_col:
        if st.button(
            "Next →",
            key=f"{control_key_prefix}_{page_key}_next",
            disabled=current_page >= total_pages,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = min(total_pages, current_page + 1)
            st.rerun()

    st.markdown('<div class="jobs-per-page-label">Jobs per page</div>', unsafe_allow_html=True)

    select_left, select_mid, select_right = st.columns([4, 2, 4])

    page_size = get_page_size(page_size_state_key, default=10)
    selector_key = f"{page_size_state_key}_selector"

    with select_mid:
        if selector_key in st.session_state:
            selected_page_size = st.selectbox(
                "Jobs per page",
                PAGE_SIZE_OPTIONS,
                key=selector_key,
                label_visibility="collapsed",
            )
        else:
            selected_page_size = st.selectbox(
                "Jobs per page",
                PAGE_SIZE_OPTIONS,
                index=PAGE_SIZE_OPTIONS.index(page_size),
                key=selector_key,
                label_visibility="collapsed",
            )

    if selected_page_size != st.session_state[page_size_state_key]:
        st.session_state[page_size_state_key] = selected_page_size
        st.session_state[page_key] = 1
        st.rerun()


def render_job_card(
    row_number: int,
    row: pd.Series,
    require_mark_as_applied: bool = True,
) -> None:
    company = safe_value(row, "Company")
    title = safe_value(row, "Title")
    location = safe_value(row, "Location")
    fit_score = safe_value(row, "Fit Score")
    compensation_raw = safe_value(row, "Compensation Raw")
    job_url = safe_value(row, "Job Posting URL")

    display_title = clean_display_title(company, title)
    apply_ready_key = f"apply_ready_{row_number}"

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
            pills.append(
                f'<span class="meta-pill location">Location: {html.escape(location)}</span>'
            )
        if fit_score:
            pills.append(
                f'<span class="meta-pill fit">Fit Score: {html.escape(fit_score)}</span>'
            )
        if compensation_raw:
            pills.append(
                f'<span class="meta-pill comp">Compensation: {html.escape(compensation_raw)}</span>'
            )

        if pills:
            st.markdown(
                f'<div class="meta-row">{"".join(pills)}</div>',
                unsafe_allow_html=True,
            )

    with right:
        btn1, btn2, btn3, btn4 = st.columns([1.05, 0.95, 1.15, 0.95])

        with btn1:
            if st.button(
                "✍️ Cover Letter",
                key=f"generate_cover_{row_number}",
                use_container_width=True,
                type="secondary",
            ):
                with st.spinner("Creating cover letter file..."):
                    code, out, err = run_command(
                        [sys.executable, "-m", "src.generate_cover_letter", str(row_number)]
                    )

                if code == 0:
                    st.success("Cover letter created.")
                    if out.strip():
                        st.text(out)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to generate cover letter.")
                    st.text(err or out)

        with btn2:
            apply_disabled = not bool(job_url)

            if st.button(
                "🚀 Apply",
                key=f"apply_{row_number}",
                use_container_width=True,
                type="primary",
                disabled=apply_disabled,
            ):
                opened = open_url(job_url)

                if require_mark_as_applied:
                    if opened:
                        st.session_state[apply_ready_key] = True
                        st.rerun()
                    else:
                        st.warning("Could not automatically open the URL.")
                else:
                    code, out, err = run_command(
                        [sys.executable, "-m", "src.move_job", str(row_number)]
                    )
                    if code == 0:
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Failed to move job.")
                        st.text(err or out)

        with btn3:
            if st.button(
                "Mark as Applied",
                key=f"mark_applied_{row_number}",
                use_container_width=True,
                type="secondary",
                disabled=(not require_mark_as_applied) or (not st.session_state[apply_ready_key]),
            ):
                code, out, err = run_command(
                    [sys.executable, "-m", "src.move_job", str(row_number)]
                )
                if code == 0:
                    st.session_state[apply_ready_key] = False
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to move job.")
                    st.text(err or out)

        with btn4:
            if st.button(
                "Remove Job",
                key=f"remove_job_{row_number}",
                use_container_width=True,
                type="secondary",
            ):
                code, out, err = run_command(
                    [sys.executable, "-m", "src.remove_job", str(row_number)]
                )
                if code == 0:
                    st.session_state[apply_ready_key] = False
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to remove job.")
                    st.text(err or out)

    st.markdown("</div>", unsafe_allow_html=True)
