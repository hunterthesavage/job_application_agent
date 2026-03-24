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
