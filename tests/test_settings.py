def test_settings_save_and_load(temp_db_path, monkeypatch):
    import services.settings as settings_module

    monkeypatch.setattr(
        settings_module,
        "db_connection",
        __import__("services.db", fromlist=["db_connection"]).db_connection,
        raising=False,
    )

    settings_module.save_settings(
        {
            "default_min_fit_score": "80",
            "default_jobs_per_page": "20",
            "profile_summary": "Test summary",
            "preferred_job_levels": "VP, SVP",
        }
    )

    loaded = settings_module.load_settings()

    assert loaded["default_min_fit_score"] == "80"
    assert loaded["default_jobs_per_page"] == "20"
    assert loaded["profile_summary"] == "Test summary"
    assert loaded["preferred_job_levels"] == "VP, SVP"


def test_settings_blank_cover_letter_folder_falls_back_to_default(temp_db_path, monkeypatch):
    import services.settings as settings_module

    monkeypatch.setattr(
        settings_module,
        "db_connection",
        __import__("services.db", fromlist=["db_connection"]).db_connection,
        raising=False,
    )

    settings_module.save_settings({"cover_letter_output_folder": ""})
    loaded = settings_module.load_settings()

    assert loaded["cover_letter_output_folder"] == settings_module.get_default_cover_letter_output_folder()


def test_initialize_settings_state_restores_saved_cover_letter_values_when_session_is_blank(
    temp_db_path, monkeypatch
):
    import services.settings as settings_module
    import views.settings as settings_view
    import streamlit as st

    monkeypatch.setattr(
        settings_module,
        "db_connection",
        __import__("services.db", fromlist=["db_connection"]).db_connection,
        raising=False,
    )

    settings_module.save_settings(
        {
            "cover_letter_output_folder": "/tmp/cover-letters",
            "cover_letter_filename_pattern": "CL_{company}_{date}.txt",
        }
    )

    st.session_state.clear()
    st.session_state["settings_cover_letter_output_folder_value"] = ""
    st.session_state["settings_cover_letter_filename_pattern_value"] = ""

    settings_view.initialize_settings_state(settings_module.load_settings())

    assert st.session_state["settings_cover_letter_output_folder_value"] == "/tmp/cover-letters"
    assert st.session_state["settings_cover_letter_filename_pattern_value"] == "CL_{company}_{date}.txt"


def test_initialize_settings_state_uses_default_cover_letter_folder_when_saved_value_is_blank(
    temp_db_path, monkeypatch
):
    import services.settings as settings_module
    import views.settings as settings_view
    import streamlit as st

    monkeypatch.setattr(
        settings_module,
        "db_connection",
        __import__("services.db", fromlist=["db_connection"]).db_connection,
        raising=False,
    )

    settings_module.save_settings(
        {
            "cover_letter_output_folder": "",
            "cover_letter_filename_pattern": "CL_{company}.txt",
        }
    )

    st.session_state.clear()
    settings_view.initialize_settings_state(settings_module.load_settings())

    assert (
        st.session_state["settings_cover_letter_output_folder_value"]
        == settings_module.get_default_cover_letter_output_folder()
    )
