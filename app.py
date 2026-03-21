import streamlit as st

from config import APP_NAME, APP_VERSION
from services.storage import initialize_local_storage
from ui.components import render_hero
from ui.styles import inject_custom_css
from views.applied_roles import render_applied_roles
from views.new_roles import render_new_roles
from views.pipeline import render_pipeline
from views.settings import render_settings


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", layout="wide")
    initialize_local_storage()
    inject_custom_css()
    render_hero()

    tab1, tab2, tab3, tab4 = st.tabs(["New Roles", "Applied Roles", "Pipeline", "Settings"])

    with tab1:
        render_new_roles()

    with tab2:
        render_applied_roles()

    with tab3:
        render_pipeline()

    with tab4:
        render_settings()


if __name__ == "__main__":
    main()
