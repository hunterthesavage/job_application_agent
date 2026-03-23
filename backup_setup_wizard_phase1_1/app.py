import streamlit as st

from config import APP_NAME, APP_VERSION
from services.settings import load_settings
from services.status import get_system_status
from ui.navigation import initialize_nav_state, render_button_nav


TOP_NAV_OPTIONS = ["New Roles", "Applied Roles", "Pipeline", "Settings"]


def has_jobs() -> bool:
    status = get_system_status()
    jobs_total = str(status.get("jobs_total", "0")).strip()
    return jobs_total not in {"", "0"}


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


def initialize_app_once() -> None:
    if st.session_state.get("_app_initialized", False):
        return

    from services.storage import initialize_local_storage

    initialize_local_storage()
    st.session_state["_app_initialized"] = True


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", layout="wide")

    from ui.components import render_hero
    from ui.styles import inject_custom_css
    from views.applied_roles import render_applied_roles
    from views.new_roles import render_new_roles
    from views.pipeline import render_pipeline
    from views.settings import render_settings
    from views.setup_wizard import render_setup_wizard

    initialize_app_once()
    inject_custom_css()
    render_hero()

    if should_show_setup_wizard():
        render_setup_wizard()
        return

    initialize_top_nav(default_value="New Roles")
    selected_view = render_top_nav()

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
