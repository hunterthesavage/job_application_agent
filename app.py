import subprocess
import sys

import streamlit as st
from streamlit.components.v1 import html as components_html

from config import APP_NAME, APP_VERSION
from services.app_control import register_current_process, request_process_shutdown
from services.settings import load_settings
from services.status import get_system_status
from services.ui_busy import app_is_busy, current_busy_label, get_action
from ui.navigation import initialize_nav_state, render_button_nav


TOP_NAV_OPTIONS = ["New Roles", "Applied Roles", "Pipeline", "Settings"]


def _safe_int(value: object) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def has_jobs() -> bool:
    status = get_system_status()
    return _safe_int(status.get("jobs_total", 0)) > 0


def should_show_setup_wizard() -> bool:
    settings = load_settings()
    dismissed = str(settings.get("setup_wizard_dismissed", "false")).strip().lower() == "true"
    completed = str(settings.get("setup_wizard_completed", "false")).strip().lower() == "true"

    if has_jobs():
        return False

    if completed or dismissed:
        return False

    return True


def initialize_top_nav(default_value: str = "New Roles") -> None:
    initialize_nav_state(
        state_key="top_nav_selection",
        default_value=default_value,
    )


def render_top_nav() -> str:
    st.caption("Main navigation")
    return render_button_nav(
        options=TOP_NAV_OPTIONS,
        state_key="top_nav_selection",
        key_prefix="top_nav",
    )


def render_boot_loading_card() -> st.delta_generator.DeltaGenerator:
    placeholder = st.empty()
    placeholder.markdown(
        """
        <style>
        @keyframes jobAgentPulse {
            0% { transform: scale(0.85); opacity: 0.55; box-shadow: 0 0 0 0 rgba(59,130,246,0.45); }
            70% { transform: scale(1.02); opacity: 1; box-shadow: 0 0 0 18px rgba(59,130,246,0.0); }
            100% { transform: scale(0.92); opacity: 0.7; box-shadow: 0 0 0 0 rgba(59,130,246,0.0); }
        }
        @keyframes jobAgentSweep {
            0% { transform: rotate(0deg); opacity: 0.55; }
            100% { transform: rotate(360deg); opacity: 1; }
        }
        </style>
        <div style="
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(16,22,36,0.96) 0%, rgba(10,14,24,0.98) 100%);
            box-shadow: 0 18px 48px rgba(0,0,0,0.24);
            padding: 1.2rem 1.35rem;
            margin-top: 0.8rem;
            margin-bottom: 1rem;
            display:flex;
            align-items:center;
            gap:1rem;
        ">
            <div style="
                position:relative;
                width:56px;
                height:56px;
                flex:0 0 56px;
                display:flex;
                align-items:center;
                justify-content:center;
            ">
                <div style="
                    position:absolute;
                    width:22px;
                    height:22px;
                    border-radius:999px;
                    background: radial-gradient(circle, rgba(147,197,253,1) 0%, rgba(59,130,246,0.96) 65%, rgba(37,99,235,0.96) 100%);
                    animation: jobAgentPulse 1.8s ease-out infinite;
                "></div>
                <div style="
                    position:absolute;
                    width:52px;
                    height:52px;
                    border-radius:999px;
                    border: 2px solid rgba(59,130,246,0.24);
                "></div>
                <div style="
                    position:absolute;
                    width:52px;
                    height:52px;
                    border-radius:999px;
                    border-top: 2px solid rgba(96,165,250,0.95);
                    border-right: 2px solid transparent;
                    border-bottom: 2px solid transparent;
                    border-left: 2px solid transparent;
                    animation: jobAgentSweep 1.2s linear infinite;
                "></div>
            </div>
            <div>
                <div style="font-size:1.22rem;font-weight:800;color:rgba(255,255,255,0.96);margin-bottom:0.35rem;">
                    Sharpening pencils and stalking job boards...
                </div>
                <div style="font-size:0.98rem;color:rgba(255,255,255,0.78);">
                    Scanning signals, waking up the database, and getting your search rig ready.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return placeholder


def render_action_loading_screen(scope: str) -> None:
    busy_label = str(current_busy_label() or "Working").strip()
    is_first_discovery = bool(st.session_state.get("_wizard_first_discovery_loading", False))

    title = "Searching all the corners of the internet for your best fits."
    copy = "Building search queries, probing trusted sources, and lining up the strongest roles so your first results feel worth the wait."
    kicker = "First Search"

    if scope == "new_roles":
        kicker = "New Roles Action"
        lowered = busy_label.lower()
        if "cover letter" in lowered:
            title = "Writing a tailored cover letter for this role."
            copy = "Combining your profile context, the job details, and your saved output folder so the finished draft lands where you expect it."
        elif "applied" in lowered:
            title = "Moving this role into your applied workflow."
            copy = "Updating the workflow state, refreshing the lists, and getting the role out of New Roles cleanly."
        elif "remove" in lowered:
            title = "Removing this role from your review list."
            copy = "Cleaning up the record so your New Roles view stays focused on the jobs you still care about."
        else:
            title = "Finishing your requested New Roles action."
            copy = "Updating the role, saving the result, and refreshing the app state before you continue."
    elif not is_first_discovery:
        kicker = "Pipeline Run"
        lowered = busy_label.lower()
        if "rescore" in lowered:
            title = "Rechecking your saved jobs for fresher signals."
            copy = "Refreshing live pages, applying updated scoring, and tightening stale job data before the results come back into view."
        elif "links only" in lowered:
            title = "Searching for new job links without changing your saved roles."
            copy = "Expanding the search surface, validating URLs, and collecting the strongest discovery leads for review."
        elif "pasted" in lowered or "saved job links" in lowered:
            title = "Validating the job links you handed over."
            copy = "Checking each link, extracting the important details, and preparing the strongest matches for the app."
        else:
            title = "Searching all the corners of the internet for your best fits."
            copy = "Running the full discovery flow, validating links, and stacking the best-fit roles where you can review them next."

    st.markdown(
        """
        <style>
        @keyframes pipelineRunPulse {
            0% { transform: scale(0.88); opacity: 0.58; box-shadow: 0 0 0 0 rgba(96,165,250,0.40); }
            70% { transform: scale(1.03); opacity: 1; box-shadow: 0 0 0 20px rgba(96,165,250,0.0); }
            100% { transform: scale(0.94); opacity: 0.72; box-shadow: 0 0 0 0 rgba(96,165,250,0.0); }
        }
        @keyframes pipelineRunSweep {
            0% { transform: rotate(0deg); opacity: 0.55; }
            100% { transform: rotate(360deg); opacity: 1; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div style="
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            background:
                radial-gradient(circle at top right, rgba(96,165,250,0.14), transparent 30%),
                linear-gradient(180deg, rgba(16,22,36,0.96) 0%, rgba(10,14,24,0.99) 100%);
            box-shadow: 0 18px 48px rgba(0,0,0,0.24);
            padding: 1.35rem 1.4rem 1.2rem 1.4rem;
            margin-top: 1rem;
            margin-bottom: 1rem;
            display:flex;
            align-items:center;
            gap:1.05rem;
        ">
            <div style="
                position:relative;
                width:58px;
                height:58px;
                flex:0 0 58px;
                display:flex;
                align-items:center;
                justify-content:center;
            ">
                <div style="
                    position:absolute;
                    width:24px;
                    height:24px;
                    border-radius:999px;
                    background: radial-gradient(circle, rgba(191,219,254,1) 0%, rgba(96,165,250,0.98) 65%, rgba(37,99,235,0.98) 100%);
                    animation: pipelineRunPulse 1.8s ease-out infinite;
                "></div>
                <div style="
                    position:absolute;
                    width:54px;
                    height:54px;
                    border-radius:999px;
                    border: 2px solid rgba(96,165,250,0.22);
                "></div>
                <div style="
                    position:absolute;
                    width:54px;
                    height:54px;
                    border-radius:999px;
                    border-top: 2px solid rgba(125,211,252,0.96);
                    border-right: 2px solid transparent;
                    border-bottom: 2px solid transparent;
                    border-left: 2px solid transparent;
                    animation: pipelineRunSweep 1.15s linear infinite;
                "></div>
            </div>
            <div>
                <div style="font-size:0.8rem;font-weight:800;letter-spacing:0.10em;text-transform:uppercase;color:rgba(147,197,253,0.92);margin-bottom:0.28rem;">
                    {kicker}
                </div>
                <div style="font-size:1.28rem;font-weight:820;color:rgba(255,255,255,0.97);margin-bottom:0.34rem;line-height:1.08;">
                    {title}
                </div>
                <div style="font-size:0.97rem;color:rgba(255,255,255,0.74);line-height:1.48;max-width:760px;">
                    {copy}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def initialize_app_once() -> None:
    if st.session_state.get("_app_initialized", False):
        return

    from services.storage import initialize_local_storage

    initialize_local_storage()
    register_current_process()
    st.session_state["_app_initialized"] = True


def render_close_application_button() -> bool:
    _, action_col = st.columns([5, 1])
    with action_col:
        st.markdown("<div style='height: 1.65rem;'></div>", unsafe_allow_html=True)
        return bool(
            st.button(
                "Close Application",
                key="close_application_button",
                use_container_width=True,
                type="tertiary",
            )
        )


def handle_close_application() -> None:
    st.info("Closing Job Application Agent...")
    components_html(
        """
        <script>
        setTimeout(function () {
          try { window.location.replace("about:blank"); } catch (e) {}
          try { window.open("", "_self"); window.close(); } catch (e) {}
        }, 150);
        </script>
        """,
        height=0,
    )
    request_process_shutdown()
    st.stop()


def maybe_run_wizard_discovery_bootstrap() -> None:
    return


def render_post_wizard_message() -> None:
    message = st.session_state.pop("_post_wizard_run_message", None)
    if not message:
        return

    kind = str(message.get("kind", "info")).strip().lower()
    text = str(message.get("text", "")).strip()

    if not text:
        return

    if kind == "success":
        st.success(text)
    elif kind == "error":
        st.error(text)
    else:
        st.info(text)


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", layout="wide")

    boot_placeholder = None
    if not st.session_state.get("_app_initialized", False):
        boot_placeholder = render_boot_loading_card()

    from ui.components import render_hero
    from ui.styles import inject_custom_css
    from views.applied_roles import render_applied_roles
    from views.new_roles import process_new_roles_action_cycle, render_new_roles
    from views.pipeline import process_pipeline_action_cycle, render_pipeline
    from views.settings import render_settings
    from views.setup_wizard import render_setup_wizard

    initialize_app_once()
    inject_custom_css()

    if boot_placeholder is not None:
        boot_placeholder.empty()

    pipeline_action = get_action("pipeline")
    new_roles_action = get_action("new_roles")
    show_pipeline_loading = bool(pipeline_action) and app_is_busy()
    show_new_roles_loading = bool(new_roles_action) and app_is_busy()

    render_hero(show_busy_banner=not (show_pipeline_loading or show_new_roles_loading))

    if should_show_setup_wizard():
        if render_close_application_button():
            handle_close_application()
        render_setup_wizard()
        return

    if show_pipeline_loading:
        render_action_loading_screen("pipeline")
        process_pipeline_action_cycle()
        return

    if show_new_roles_loading:
        render_action_loading_screen("new_roles")
        process_new_roles_action_cycle()
        return

    initialize_top_nav(default_value="New Roles")
    selected_view = render_top_nav()
    if render_close_application_button():
        handle_close_application()

    render_post_wizard_message()

    if selected_view == "New Roles":
        render_new_roles()
    elif selected_view == "Applied Roles":
        render_applied_roles()
    elif selected_view == "Pipeline":
        render_pipeline()
    else:
        render_settings()


if __name__ == "__main__":
    main()
