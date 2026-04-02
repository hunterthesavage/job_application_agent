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
        if "save run inputs" in lowered:
            title = "Cleaning up your run inputs before the next search."
            copy = "Normalizing titles, tightening location lines, and saving the updated search shape back into the app."
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
    components_html(
        """
        <script>
        (function () {
          try { window.scrollTo(0, 0); } catch (e) {}
          try { parent.window.scrollTo(0, 0); } catch (e) {}
          try {
            const root = window.parent.document.querySelector('.main');
            if (root) { root.scrollTop = 0; }
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
    )

def initialize_app_once() -> None:
    if st.session_state.get("_app_initialized", False):
        return

    from services.storage import initialize_local_storage

    initialize_local_storage()
    register_current_process()
    st.session_state["_app_initialized"] = True


def trigger_close_application() -> None:
    st.session_state["_shutdown_requested"] = True
    st.rerun()


def render_shutdown_screen() -> None:
    st.markdown(
        """
        <div style="
            min-height: 68vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem 1rem;
        ">
            <div style="
                max-width: 34rem;
                width: 100%;
                border-radius: 24px;
                border: 1px solid rgba(255,255,255,0.10);
                background:
                    radial-gradient(circle at top left, rgba(59,130,246,0.10), transparent 28%),
                    radial-gradient(circle at top right, rgba(239,68,68,0.08), transparent 22%),
                    linear-gradient(180deg, rgba(15,23,42,0.98) 0%, rgba(9,13,24,0.99) 100%);
                box-shadow: 0 24px 56px rgba(0,0,0,0.28);
                padding: 1.6rem 1.55rem;
                text-align: center;
            ">
                <div style="
                    width: 3.15rem;
                    height: 3.15rem;
                    margin: 0 auto 0.95rem auto;
                    border-radius: 999px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.45rem;
                    font-weight: 800;
                    color: #fecaca;
                    border: 1px solid rgba(248,113,113,0.35);
                    background: rgba(127,29,29,0.34);
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
                ">×</div>
                <div style="
                    font-size: 1.22rem;
                    font-weight: 800;
                    color: rgba(255,255,255,0.97);
                    margin-bottom: 0.45rem;
                ">Job Application Agent is closing</div>
                <div style="
                    font-size: 0.98rem;
                    color: rgba(229,238,252,0.82);
                    line-height: 1.55;
                ">You can close this tab now if it does not close itself automatically.</div>
                <div style="
                    margin-top: 0.8rem;
                    font-size: 0.84rem;
                    color: rgba(229,238,252,0.58);
                ">The local app process is shutting down in the background.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    components_html(
        """
        <script>
        (function () {
          const shutdownHtml = `
            <!doctype html>
            <html>
              <head>
                <meta charset="utf-8">
                <title>Closing Job Application Agent</title>
                <style>
                  body {
                    margin: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background:
                      radial-gradient(circle at top left, rgba(59,130,246,0.12), transparent 28%),
                      radial-gradient(circle at top right, rgba(239,68,68,0.10), transparent 24%),
                      linear-gradient(180deg, #050914 0%, #090d18 100%);
                    color: #e5eefc;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                  }
                  .card {
                    max-width: 32rem;
                    padding: 1.4rem 1.5rem;
                    border-radius: 20px;
                    border: 1px solid rgba(255,255,255,0.10);
                    background: rgba(15, 23, 42, 0.96);
                    box-shadow: 0 20px 45px rgba(0,0,0,0.25);
                    text-align: center;
                    line-height: 1.5;
                  }
                  .icon {
                    width: 3rem;
                    height: 3rem;
                    margin: 0 auto 0.9rem auto;
                    border-radius: 999px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.35rem;
                    font-weight: 800;
                    color: #fecaca;
                    border: 1px solid rgba(248,113,113,0.35);
                    background: rgba(127,29,29,0.34);
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
                  }
                  .title {
                    font-size: 1.18rem;
                    font-weight: 700;
                    margin-bottom: 0.45rem;
                  }
                  .copy {
                    color: rgba(229,238,252,0.80);
                    font-size: 0.96rem;
                  }
                  .subtle {
                    margin-top: 0.7rem;
                    color: rgba(229,238,252,0.56);
                    font-size: 0.83rem;
                  }
                </style>
              </head>
              <body>
                <div class="card">
                  <div class="icon">×</div>
                  <div class="title">Job Application Agent has closed</div>
                  <div class="copy">You can close this tab now.</div>
                  <div class="subtle">The local app process has already been asked to shut down.</div>
                </div>
              </body>
            </html>
          `;

          const target = window.parent && window.parent !== window ? window.parent : window;
          const shutdownUrl = "data:text/html;charset=utf-8," + encodeURIComponent(shutdownHtml);

          setTimeout(function () {
            try { target.location.replace(shutdownUrl); } catch (e) {}
          }, 220);
        })();
        </script>
        """,
        height=0,
    )
    request_process_shutdown(delay_seconds=1.8)
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

    if st.session_state.get("_shutdown_requested", False):
        render_shutdown_screen()
        return

    pipeline_action = get_action("pipeline")
    new_roles_action = get_action("new_roles")
    show_pipeline_loading = bool(pipeline_action) and app_is_busy()
    show_new_roles_loading = bool(new_roles_action) and app_is_busy()

    close_requested = render_hero(show_busy_banner=not (show_pipeline_loading or show_new_roles_loading))
    if close_requested:
        trigger_close_application()

    if should_show_setup_wizard():
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
