import html
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_VERSION
from services.data import (
    clean_display_title,
    get_page_size,
    open_url,
    safe_value,
)
from services.openai_key import get_effective_openai_api_key
from services.settings import load_settings
from services.status import get_system_status
from services.ui_busy import app_is_busy, current_busy_label, queue_action


PAGE_SIZE_OPTIONS = [5, 10, 20, 500]
FIT_SCORE_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]
TRUST_FILTER_OPTIONS = ["All", "ATS Confirmed", "Career Site Confirmed", "Web Discovered", "Third-Party Listing", "Unknown"]


def _widget_nonce() -> int:
    return int(st.session_state.get("configuration_widget_nonce", 0))


def _format_refresh_timestamp(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return raw

    if parsed.tzinfo is not None:
        try:
            parsed = parsed.astimezone()
        except Exception:
            pass

    return parsed.strftime("%Y-%m-%d %I:%M %p").lstrip("0")


def _get_openai_badge() -> tuple[str, str]:
    _ = load_settings()
    status = get_system_status()

    key_status = str(status.get("openai_api_key_status", "Not configured")).strip().lower()

    if key_status in {"saved not validated", "configured"}:
        return "OpenAI: Active", "active"

    if key_status == "validated":
        return "OpenAI: Active", "active"

    return "OpenAI: Not Active", "not-active"


def _split_semicolon_text(value: str) -> list[str]:
    items: list[str] = []
    for part in str(value or "").replace(";", "\n").splitlines():
        cleaned = part.strip(" -")
        if cleaned:
            items.append(cleaned)
    return items


def _split_scrub_corrections(risk_flags: str) -> tuple[list[str], list[str]]:
    corrections: list[str] = []
    remaining_risks: list[str] = []

    for item in _split_semicolon_text(risk_flags):
        lowered = item.lower()
        if lowered.startswith("ai scrub updated ") or lowered.startswith("live page refresh updated "):
            corrections.append(item)
        else:
            remaining_risks.append(item)

    return corrections, remaining_risks


def _parse_compensation_number(value: str) -> int | None:
    text = str(value or "").strip().upper().replace(",", "").replace("$", "")
    if not text:
        return None

    multiplier = 1
    if text.endswith("K"):
        multiplier = 1000
        text = text[:-1].strip()

    try:
        return int(round(float(text) * multiplier))
    except Exception:
        return None


def _format_currency_number(value: int) -> str:
    return f"${value:,}"


def _format_compensation_display(raw_value: str) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return ""

    lowered = text.lower()
    is_hourly = any(marker in lowered for marker in ["/hr", "per hour", "hourly", "/hour", "hr."])
    numbers = re.findall(r"\$?\d[\d,]*(?:\.\d+)?K?", text, re.IGNORECASE)
    inherit_k = any(str(item).strip().upper().endswith("K") for item in numbers)
    normalized_numbers: list[str] = []
    for item in numbers:
        token = str(item).strip()
        if inherit_k and not token.upper().endswith("K") and re.fullmatch(r"\$?\d[\d,]*(?:\.\d+)?", token):
            token = f"{token}K"
        normalized_numbers.append(token)

    parsed = [_parse_compensation_number(item) for item in normalized_numbers]
    parsed = [item for item in parsed if item is not None]

    if not parsed:
        return text

    if len(parsed) >= 2:
        formatted = f"{_format_currency_number(parsed[0])}-{_format_currency_number(parsed[1])}"
    else:
        formatted = _format_currency_number(parsed[0])

    if is_hourly:
        return f"{formatted}/hr"

    return formatted


def _render_ai_button_chip() -> None:
    st.markdown(
        '<div class="ai-button-chip-wrap"><span class="ai-button-chip" title="Uses OpenAI">AI</span></div>',
        unsafe_allow_html=True,
    )


def _render_ai_button_chip_placeholder() -> None:
    st.markdown(
        '<div class="ai-button-chip-wrap ai-button-chip-wrap-placeholder"><span class="ai-button-chip ai-button-chip-hidden">AI</span></div>',
        unsafe_allow_html=True,
    )


def render_hero(*, show_busy_banner: bool = True) -> bool:
    badge_text, badge_class = _get_openai_badge()

    busy_text = ""
    if show_busy_banner and app_is_busy() and current_busy_label():
        busy_text = f'<div class="app-busy-banner">Working: {html.escape(current_busy_label())}</div>'

    left_col, right_col = st.columns([6.2, 1.6], gap="large")

    with left_col:
        st.markdown(
            f"""
            <div class="hero-wrap">
                <div class="hero-title">
                    <span class="hero-title-main">{html.escape(APP_NAME)}</span>
                    <span class="hero-title-version">{html.escape(APP_VERSION)}</span>
                </div>
                <div class="hero-subtle">High-signal roles, faster action, cleaner workflow.</div>
                {busy_text}
            </div>

            <style>
            .openai-badge {{
                font-size: 0.9rem;
                font-weight: 700;
                padding: 0.6rem 0.9rem;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.12);
                letter-spacing: 0.01em;
                white-space: nowrap;
                justify-content: center;
                width: 100%;
                box-sizing: border-box;
            }}
            .openai-badge-active {{
                background: rgba(34, 197, 94, 0.14);
                border-color: rgba(34, 197, 94, 0.40);
                color: #b9f8ce;
            }}
            .openai-badge-not-active {{
                background: rgba(255, 99, 99, 0.12);
                border-color: rgba(255, 99, 99, 0.28);
                color: #ffb3b3;
            }}
            .hero-side-stack {{
                display: flex;
                flex-direction: column;
                align-items: stretch;
                gap: 0.75rem;
                width: 100%;
                max-width: 260px;
                margin-left: auto;
            }}
            .hero-status-label {{
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.52);
                margin-bottom: 0.28rem;
                text-align: right;
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

    close_requested = False
    with right_col:
        st.markdown('<div class="hero-side-stack">', unsafe_allow_html=True)
        close_requested = bool(
            st.button(
                "\u2715 Close Application",
                key="hero_close_application_button",
                use_container_width=True,
                type="secondary",
            )
        )
        st.markdown(
            f"""
            <div>
                <div class="hero-status-label">OpenAI Status</div>
                <div class="openai-badge openai-badge-{html.escape(badge_class)}">{html.escape(badge_text)}</div>
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return close_requested


def render_kpis(kpis: dict[str, str]) -> None:
    st.markdown(
        f"""
        <div class="kpi-grid">
            <div class="kpi-card blue">
                <div class="kpi-label">Ready to Review</div>
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
    st.markdown(
        '<div class="filters-heading">Refine Results</div>'
        '<div class="filters-subtle">Narrow the queue before you spend time opening cards.</div>',
        unsafe_allow_html=True,
    )

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

    with st.expander("More Filters", expanded=False):
        extra_left, extra_right = st.columns(2)

        with extra_left:
            st.markdown('<div class="control-label">Discovery State</div>', unsafe_allow_html=True)

            discovery_options = ["All", "Net New", "Rediscovered"]
            current_discovery = st.session_state.get("filter_discovery_state", "All")
            discovery_key = f"filter_discovery_state_selector_{nonce}"

            selected_discovery = st.selectbox(
                "Discovery State",
                discovery_options,
                index=discovery_options.index(current_discovery) if current_discovery in discovery_options else 0,
                key=discovery_key,
                label_visibility="collapsed",
                disabled=app_is_busy(),
            )

            if selected_discovery != st.session_state.get("filter_discovery_state", "All"):
                st.session_state["filter_discovery_state"] = selected_discovery
                st.session_state["new_roles_current_page"] = 1
                st.rerun()

        with extra_right:
            st.markdown('<div class="control-label">Source Trust</div>', unsafe_allow_html=True)

            current_trust = st.session_state.get("filter_source_trust", "All")
            trust_key = f"filter_source_trust_selector_{nonce}"

            selected_trust = st.selectbox(
                "Source Trust",
                TRUST_FILTER_OPTIONS,
                index=TRUST_FILTER_OPTIONS.index(current_trust) if current_trust in TRUST_FILTER_OPTIONS else 0,
                key=trust_key,
                label_visibility="collapsed",
                disabled=app_is_busy(),
                help="Separate ATS-confirmed roles from broader web discovery when you want a narrower review set.",
            )

            if selected_trust != st.session_state.get("filter_source_trust", "All"):
                st.session_state["filter_source_trust"] = selected_trust
                st.session_state["new_roles_current_page"] = 1
                st.rerun()

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
    fit_tier = safe_value(row, "Fit Tier")
    ai_recommendation = safe_value(row, "AI Recommendation")
    last_refreshed = safe_value(row, "Last Refreshed")
    match_rationale = safe_value(row, "Match Rationale")
    risk_flags = safe_value(row, "Risk Flags")
    application_angle = safe_value(row, "Application Angle")
    source = safe_value(row, "Source")
    source_type = safe_value(row, "Source Type")
    source_trust = safe_value(row, "Source Trust")
    source_detail = safe_value(row, "Source Detail")
    discovery_state = safe_value(row, "Discovery State")
    compensation_raw = safe_value(row, "Compensation Raw")
    compensation_display = _format_compensation_display(compensation_raw)
    job_url = safe_value(row, "Job Posting URL")
    scrub_corrections, display_risks = _split_scrub_corrections(risk_flags)

    display_title = clean_display_title(company, title)
    apply_ready_key = f"apply_ready_{job_id}"
    notice = st.session_state.pop(f"new_roles_job_notice_{job_id}", None)

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
        if ai_recommendation:
            pills.append(f'<span class="meta-pill comp">Recommendation: {html.escape(ai_recommendation)}</span>')
        if compensation_display:
            pills.append(f'<span class="meta-pill comp">Compensation: {html.escape(compensation_display)}</span>')

        if pills:
            st.markdown(f'<div class="meta-row">{"".join(pills)}</div>', unsafe_allow_html=True)

        has_ai_details = bool(match_rationale or risk_flags or application_angle or last_refreshed)
        has_source_details = bool(source or source_type or source_trust or source_detail or discovery_state)

        if has_ai_details or has_source_details:
            with st.expander("More Details", expanded=False):
                if has_ai_details:
                    st.markdown("**AI Fit**")
                    if last_refreshed:
                        st.caption(f"Score refreshed: {_format_refresh_timestamp(last_refreshed)}")

                    if match_rationale:
                        st.markdown("**Why it matches**")
                        st.write(match_rationale)

                    if scrub_corrections:
                        st.markdown("**AI corrections**")
                        for part in scrub_corrections:
                            st.write(f"• {part}")

                    if display_risks:
                        st.markdown("**Risks / gaps**")
                        for part in display_risks:
                            st.write(f"• {part}")

                    if application_angle:
                        st.markdown("**Suggested application angle**")
                        st.write(application_angle)

                if has_ai_details and has_source_details:
                    st.markdown("---")

                if has_source_details:
                    st.markdown("**Source**")
                    if source_trust:
                        st.markdown(f"**Trust**: {source_trust}")
                    if source_type:
                        st.markdown(f"**Source Type**: {source_type}")
                    if source:
                        st.markdown(f"**Source**: {source}")
                    if discovery_state:
                        st.markdown(f"**Discovery State**: {discovery_state}")
                    if source_detail:
                        st.markdown("**Source Detail**")
                        st.write(source_detail)

    with right:
        if isinstance(notice, dict) and str(notice.get("message", "")).strip():
            level = str(notice.get("level", "success")).strip().lower()
            message = str(notice.get("message", "")).strip()
            if level == "error":
                st.error(message)
            elif level == "warning":
                st.warning(message)
            else:
                st.success(message)

        top_actions = st.columns(2)
        bottom_actions = st.columns(2)

        api_key = get_effective_openai_api_key()
        cover_letter_enabled = bool(api_key)
        cover_letter_help = (
            "Generate a tailored cover letter"
            if cover_letter_enabled
            else "No OpenAI API key is configured. Add one in Settings > OpenAI API."
        )

        with top_actions[0]:
            _render_ai_button_chip_placeholder()
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

        with top_actions[1]:
            _render_ai_button_chip()
            if st.button(
                "✍️ Cover Letter",
                key=f"generate_cover_{job_id}",
                use_container_width=True,
                type="secondary",
                disabled=app_is_busy() or (not cover_letter_enabled),
                help=cover_letter_help,
            ):
                queue_action(
                    "new_roles",
                    "generate_cover_letter",
                    payload={"job_id": int(job_id)},
                    label="Generating Cover Letter",
                )
                st.rerun()

        with bottom_actions[0]:
            if st.button(
                "Mark as Applied",
                key=f"mark_applied_{job_id}",
                use_container_width=True,
                type="secondary",
                disabled=app_is_busy() or (not st.session_state[apply_ready_key]),
            ):
                queue_action(
                    "new_roles",
                    "mark_applied",
                    payload={"job_id": int(job_id), "apply_ready_key": apply_ready_key},
                    label="Marking Job as Applied",
                )
                st.rerun()

        with bottom_actions[1]:
            confirm_remove_key = f"confirm_remove_job_{job_id}"
            remove_label = "Confirm Remove" if st.session_state.get(confirm_remove_key, False) else "Remove Job"
            if st.button(
                remove_label,
                key=f"remove_job_{job_id}",
                use_container_width=True,
                type="secondary",
                disabled=app_is_busy(),
            ):
                if not st.session_state.get(confirm_remove_key, False):
                    st.session_state[confirm_remove_key] = True
                    st.rerun()

                st.session_state.pop(confirm_remove_key, None)
                queue_action(
                    "new_roles",
                    "remove_job",
                    payload={"job_id": int(job_id), "apply_ready_key": apply_ready_key},
                    label="Removing Job",
                )
                st.rerun()

            if st.session_state.get(confirm_remove_key, False):
                st.caption("Click Confirm Remove to permanently remove this job from New Roles.")

    st.markdown("</div>", unsafe_allow_html=True)
