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
    row_matches_settings_filters,
)
from services.settings import load_settings
from services.sqlite_actions import mark_job_as_applied, remove_job
from services.ui_busy import (
    clear_action,
    get_action,
    move_action_to_execute,
    queue_action,
    stop_busy,
)
from ui.components import (
    render_bottom_pagination_controls,
    render_filter_bar,
    render_job_card,
    render_kpis,
)


VALID_FIT_OPTIONS = ["Any", 60, 70, 75, 80, 85, 90]


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


def apply_settings_role_filters(df, settings: dict):
    if df.empty:
        return df

    mask = df.apply(lambda row: row_matches_settings_filters(row, settings), axis=1)
    return df[mask]


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
        st.info("No roles found in SQLite yet.")
        _advance_pending_action_after_render()
        return

    df_display = df.copy()

    for col in ["Fit Score", "Location", "Compensation Raw"]:
        if col not in df_display.columns:
            df_display[col] = ""

    if "Fit Score" in df_display.columns:
        df_display["_fit_sort"] = df_display["Fit Score"].apply(normalize_fit_score)
        df_display = df_display.sort_values(by="_fit_sort", ascending=False).drop(columns=["_fit_sort"])

    df_targeted = apply_settings_role_filters(df_display, settings)

    kpis = calculate_kpis(df, df_applied)
    render_kpis(kpis)
    render_filter_bar()

    df_filtered = apply_new_role_filters(df_targeted)

    default_jobs_per_page = int(settings.get("default_jobs_per_page", "10"))
    page_size = get_page_size("new_roles_page_size", default=default_jobs_per_page)

    paged_df, current_page, total_pages = paginate_df(
        df_filtered,
        page_size=page_size,
        page_key="new_roles_current_page",
    )

    st.markdown(
        f"""
        <div class="section-row">
            <div class="section-title">New Roles</div>
            <div class="section-meta">
                Page {current_page} of {total_pages} | Showing {len(df_filtered)} total jobs
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if paged_df.empty:
        st.info("No roles match the current settings and filters.")
    else:
        for job_id, row in paged_df.iterrows():
            render_job_card(
                int(job_id),
                row,
            )

    render_bottom_pagination_controls(
        total_rows=len(df_filtered),
        current_page=current_page,
        total_pages=total_pages,
        page_key="new_roles_current_page",
        control_key_prefix="bottom",
        page_size_state_key="new_roles_page_size",
    )

    _advance_pending_action_after_render()
