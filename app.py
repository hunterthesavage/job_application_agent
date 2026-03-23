import subprocess
import sys

import streamlit as st

from config import APP_NAME, APP_VERSION
from services.settings import load_settings
from services.status import get_system_status
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

def initialize_app_once() -> None:
    if st.session_state.get("_app_initialized", False):
        return

    from services.storage import initialize_local_storage

    initialize_local_storage()
    st.session_state["_app_initialized"] = True


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
    from views.new_roles import render_new_roles
    from views.pipeline import render_pipeline
    from views.settings import render_settings
    from views.setup_wizard import render_setup_wizard

    initialize_app_once()
    inject_custom_css()

    if boot_placeholder is not None:
        boot_placeholder.empty()

    render_hero()

    if should_show_setup_wizard():
        render_setup_wizard()
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
