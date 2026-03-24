import re

import streamlit as st

from services.cover_letters import generate_cover_letter_for_job_id
from services.data import (
    apply_new_role_filters,
    calculate_kpis,
    get_page_size,
    load_sqlite_applied_roles,
    load_sqlite_new_roles,
    normalize_fit_score,
    paginate_df,
)
from services.settings import load_settings
from services.sqlite_actions import mark_job_as_applied, remove_job
from services.ui_busy import (
    clear_action,
    get_action,
    move_action_to_execute,
    stop_busy,
)
from ui.components import (
    render_bottom_pagination_controls,
    render_filter_bar,
    render_job_card,
    render_kpis,
)


VALID_FIT_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]
NEW_ROLES_SORT_OPTIONS = [
    "Newest First",
    "Highest Fit Score",
    "Highest Compensation",
    "Highest Source Trust",
    "Company A-Z",
]


def _set_flash(level: str, message: str) -> None:
    st.session_state["new_roles_flash_level"] = level
    st.session_state["new_roles_flash_message"] = message


def _render_flash() -> None:
    message = st.session_state.pop("new_roles_flash_message", "")
    level = st.session_state.pop("new_roles_flash_level", "success")

    if not message:
        return

    if level == "error":
        st.error(message)
    else:
        st.success(message)


def _render_new_roles_empty_state(has_any_roles: bool) -> None:
    if not has_any_roles:
        st.info(
            "No new roles are in the app yet. Start in Pipeline with Find and Add Jobs, or paste a few job links to seed the list."
        )
        st.caption("Once jobs land here, you can review AI fit detail, generate cover letters, and mark roles as applied.")
        return

    st.info("No roles match the current on-screen filters.")
    st.caption("Try relaxing Minimum Fit Score, turning off Remote Only, or opening More Filters to widen the list again.")


def _process_pending_action_before_render() -> None:
    action = get_action("new_roles")
    if not action or action.get("phase") != "execute":
        return

    try:
        action_type = action.get("type")
        payload = action.get("payload", {})
        label = action.get("label", "Working")

        with st.spinner(f"{label}..."):
            if action_type == "generate_cover_letter":
                result = generate_cover_letter_for_job_id(int(payload["job_id"]))
                _set_flash("success", f"✓ Cover letter created: {result['output_path']}")
                st.cache_data.clear()

            elif action_type == "mark_applied":
                mark_job_as_applied(int(payload["job_id"]))
                apply_ready_key = payload.get("apply_ready_key", "")
                if apply_ready_key:
                    st.session_state[apply_ready_key] = False
                _set_flash("success", "✓ Job marked as applied")
                st.cache_data.clear()

            elif action_type == "remove_job":
                remove_job(int(payload["job_id"]))
                apply_ready_key = payload.get("apply_ready_key", "")
                if apply_ready_key:
                    st.session_state[apply_ready_key] = False
                _set_flash("success", "✓ Job removed")
                st.cache_data.clear()

    except Exception as exc:
        _set_flash("error", f"Action failed: {exc}")
    finally:
        clear_action("new_roles")
        stop_busy()
        st.rerun()


def _advance_pending_action_after_render() -> None:
    action = get_action("new_roles")
    if action and action.get("phase") == "prepare":
        move_action_to_execute("new_roles")
        st.rerun()


def _parse_compensation_value(value) -> float:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return -1.0

    normalized = text.replace(",", "")
    numbers = re.findall(r"\d+(?:\.\d+)?", normalized)
    if not numbers:
        return -1.0

    values = []
    for item in numbers:
        try:
            values.append(float(item))
        except Exception:
            continue

    if not values:
        return -1.0

    return max(values)


def _get_first_existing_column(df, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _apply_new_roles_sort(df, sort_label: str):
    sort_label = str(sort_label or "Newest First").strip()
    if df.empty:
        return df

    if sort_label == "Highest Fit Score":
        fit_col = _get_first_existing_column(df, ["Fit Score", "fit_score"])
        if fit_col:
            df["_fit_sort"] = df[fit_col].apply(normalize_fit_score)
            df = df.sort_values(by="_fit_sort", ascending=False, kind="stable").drop(columns=["_fit_sort"])
        return df

    if sort_label == "Highest Compensation":
        comp_col = _get_first_existing_column(
            df,
            ["Compensation", "compensation", "Compensation Raw", "compensation_raw", "Compensation Max", "compensation_max"],
        )
        if comp_col:
            df["_comp_sort"] = df[comp_col].apply(_parse_compensation_value)
            df = df.sort_values(by="_comp_sort", ascending=False, kind="stable").drop(columns=["_comp_sort"])
        return df

    if sort_label == "Highest Source Trust":
        trust_col = _get_first_existing_column(df, ["Source Trust", "source_trust"])
        if trust_col:
            trust_rank = {
                "ATS Confirmed": 4,
                "Career Site Confirmed": 3,
                "Web Discovered": 2,
                "Third-Party Listing": 1,
                "Unknown": 0,
                "": 0,
            }
            df["_trust_sort"] = (
                df[trust_col]
                .fillna("")
                .astype(str)
                .str.strip()
                .map(lambda value: trust_rank.get(value, 0))
            )
            df = df.sort_values(by="_trust_sort", ascending=False, kind="stable").drop(columns=["_trust_sort"])
        return df

    if sort_label == "Company A-Z":
        company_col = _get_first_existing_column(df, ["Company", "company"])
        if company_col:
            df["_company_sort"] = df[company_col].fillna("").astype(str).str.lower().str.strip()
            df = df.sort_values(by="_company_sort", ascending=True, kind="stable").drop(columns=["_company_sort"])
        return df

    newest_col = _get_first_existing_column(
        df,
        ["Date Found", "date_found", "first_seen_at", "created_at", "Date Last Validated", "date_last_validated"],
    )
    if newest_col:
        try:
            import pandas as pd
            df["_newest_sort"] = pd.to_datetime(df[newest_col], errors="coerce")
            df = df.sort_values(by="_newest_sort", ascending=False, kind="stable").drop(columns=["_newest_sort"])
            return df
        except Exception:
            pass

    return df


def _render_header_sort_controls(current_page: int, total_pages: int, total_rows: int) -> None:
    left, right = st.columns([3.2, 1.45], vertical_alignment="bottom")

    with left:
        st.markdown('<div class="section-title">New Roles</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="soft-control-label">Sort jobs by</div>', unsafe_allow_html=True)
        st.selectbox(
            "Sort jobs by",
            NEW_ROLES_SORT_OPTIONS,
            key="new_roles_sort",
            label_visibility="collapsed",
            help="The default sort comes from Settings. Change it here when you want a different review order.",
        )
        st.markdown(
            f'<div class="section-meta section-meta-right">Page {current_page} of {total_pages} | Showing {total_rows} total jobs</div>',
            unsafe_allow_html=True,
        )


def initialize_filter_state_from_settings(settings: dict) -> None:
    raw_fit = settings.get("default_min_fit_score", "Any")

    try:
        default_fit = int(raw_fit)
    except Exception:
        default_fit = "Any"

    if default_fit not in VALID_FIT_OPTIONS:
        default_fit = "Any"

    if "filter_min_fit" not in st.session_state:
        st.session_state["filter_min_fit"] = default_fit

    remote_only_setting = str(settings.get("remote_only", "false")).strip().lower() == "true"
    if "filter_remote_only" not in st.session_state:
        st.session_state["filter_remote_only"] = remote_only_setting

    if "filter_compensation_only" not in st.session_state:
        st.session_state["filter_compensation_only"] = False

    if "filter_discovery_state" not in st.session_state:
        st.session_state["filter_discovery_state"] = "All"

    if "filter_source_trust" not in st.session_state:
        st.session_state["filter_source_trust"] = "All"

    default_sort = str(settings.get("default_new_roles_sort", "Newest First") or "Newest First").strip()
    if default_sort not in NEW_ROLES_SORT_OPTIONS:
        default_sort = "Newest First"

    if "new_roles_sort" not in st.session_state:
        st.session_state["new_roles_sort"] = default_sort


def _apply_source_trust_filter(df):
    selected = str(st.session_state.get("filter_source_trust", "All") or "All").strip()
    if selected == "All":
        return df

    trust_col = None
    for candidate in ["Source Trust", "source_trust"]:
        if candidate in df.columns:
            trust_col = candidate
            break

    if trust_col is None:
        return df

    series = df[trust_col].fillna("").astype(str).str.strip()
    if selected == "Unknown":
        return df[series.eq("") | series.eq("Unknown")]
    return df[series.eq(selected)]


def render_new_roles() -> None:
    _process_pending_action_before_render()

    st.subheader("New Roles")

    settings = load_settings()
    initialize_filter_state_from_settings(settings)

    try:
        df = load_sqlite_new_roles()
        df_applied = load_sqlite_applied_roles()
    except Exception as exc:
        st.error(f"Failed to load SQLite roles: {exc}")
        st.stop()

    _render_flash()

    if df.empty:
        _render_new_roles_empty_state(has_any_roles=False)
        _advance_pending_action_after_render()
        return

    df_display = df.copy()

    for col in ["Fit Score", "Location", "Compensation Raw", "Discovery State", "Source Trust", "Source Type", "Source Detail"]:
        if col not in df_display.columns:
            df_display[col] = ""

    kpis = calculate_kpis(df, df_applied)
    render_kpis(kpis)
    render_filter_bar()

    df_filtered = apply_new_role_filters(df_display)
    df_filtered = _apply_source_trust_filter(df_filtered)
    df_filtered = _apply_new_roles_sort(df_filtered, st.session_state.get("new_roles_sort", "Newest First"))

    default_jobs_per_page = int(settings.get("default_jobs_per_page", "10"))
    page_size = get_page_size("new_roles_page_size", default=default_jobs_per_page)

    paged_df, current_page, total_pages = paginate_df(
        df_filtered,
        page_size=page_size,
        page_key="new_roles_current_page",
    )

    _render_header_sort_controls(
        current_page=current_page,
        total_pages=total_pages,
        total_rows=len(df_filtered),
    )

    if paged_df.empty:
        _render_new_roles_empty_state(has_any_roles=True)
    else:
        for job_id, row in paged_df.iterrows():
            render_job_card(
                int(job_id),
                row,
            )
            st.markdown("---")

    render_bottom_pagination_controls(
        total_rows=len(df_filtered),
        current_page=current_page,
        total_pages=total_pages,
        page_key="new_roles_current_page",
        control_key_prefix="bottom",
        page_size_state_key="new_roles_page_size",
    )

    _advance_pending_action_after_render()
