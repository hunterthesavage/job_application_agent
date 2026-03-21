import streamlit as st

from config import APP_NAME, APP_VERSION
from services.status import get_system_status
from services.storage import initialize_local_storage
from ui.components import render_hero
from ui.styles import inject_custom_css
from views.applied_roles import render_applied_roles
from views.new_roles import render_new_roles
from views.pipeline import render_pipeline
from views.settings import render_settings


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


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", layout="wide")
    initialize_local_storage()
    inject_custom_css()
    render_hero()

    first_run = is_first_run()

    if first_run:
        render_first_run_callout()
        tab_settings, tab_new, tab_applied, tab_pipeline = st.tabs(
            ["Settings", "New Roles", "Applied Roles", "Pipeline"]
        )

        with tab_settings:
            render_settings()

        with tab_new:
            render_new_roles()

        with tab_applied:
            render_applied_roles()

        with tab_pipeline:
            render_pipeline()

    else:
        tab_new, tab_applied, tab_pipeline, tab_settings = st.tabs(
            ["New Roles", "Applied Roles", "Pipeline", "Settings"]
        )

        with tab_new:
            render_new_roles()

        with tab_applied:
            render_applied_roles()

        with tab_pipeline:
            render_pipeline()

        with tab_settings:
            render_settings()


if __name__ == "__main__":
    main()
