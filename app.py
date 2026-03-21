import streamlit as st

from config import APP_NAME, APP_VERSION
from services.status import get_system_status
from ui.navigation import initialize_nav_state, render_button_nav


TOP_NAV_OPTIONS = ["New Roles", "Applied Roles", "Pipeline", "Settings"]


def is_first_run() -> bool:
    status = get_system_status()

    jobs_total = str(status.get("jobs_total", "0")).strip()
    last_import_at = str(status.get("last_import_at", "—")).strip()

    return jobs_total == "0" and last_import_at == "—"


def render_first_run_callout() -> None:
    st.info(
        """
This looks like a fresh setup.

Start in **Settings** to configure:
1. Search Criteria so the app knows what roles to look for
2. Profile Context to improve AI-generated content
3. OpenAI API if you want cover letter generation

After setup, run your initial job discovery/import workflow to pull jobs into the app.
        """
    )


def initialize_top_nav(first_run: bool) -> None:
    initialize_nav_state(
        state_key="top_nav_selection",
        default_value="Settings" if first_run else "New Roles",
    )


def render_top_nav() -> str:
    st.caption("Main navigation")
    return render_button_nav(
        options=TOP_NAV_OPTIONS,
        state_key="top_nav_selection",
        key_prefix="top_nav",
    )


def render_startup_loading_message() -> st.delta_generator.DeltaGenerator:
    placeholder = st.empty()
    placeholder.info(
        """
**Warming up the job engine...**

Hang tight while we get your workspace, settings, and local database ready.
        """
    )
    return placeholder


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", layout="wide")

    startup_placeholder = render_startup_loading_message()

    from services.storage import initialize_local_storage
    from ui.components import render_hero
    from ui.styles import inject_custom_css
    from views.applied_roles import render_applied_roles
    from views.new_roles import render_new_roles
    from views.pipeline import render_pipeline
    from views.settings import render_settings

    initialize_local_storage()
    inject_custom_css()

    startup_placeholder.empty()

    render_hero()

    first_run = is_first_run()
    initialize_top_nav(first_run)

    if first_run:
        render_first_run_callout()

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
