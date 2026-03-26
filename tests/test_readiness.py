def test_readiness_summary_reports_ai_and_profile_ready(temp_db_path, tmp_path, monkeypatch):
    import services.readiness as readiness
    import services.settings as settings_module

    output_dir = tmp_path / "letters"
    output_dir.mkdir(parents=True, exist_ok=True)

    settings_module.save_settings(
        {
            "profile_summary": "Executive technology leader",
            "preferred_job_levels": "VP, SVP",
            "cover_letter_output_folder": str(output_dir),
        }
    )

    monkeypatch.setattr(readiness, "has_openai_api_key", lambda: True)

    summary = readiness.get_readiness_summary()

    capability_map = {tile["label"]: tile for tile in summary["capabilities"]}

    assert capability_map["Discovery AI"]["value"] == "Ready"
    assert capability_map["Scoring AI"]["value"] == "Ready"
    assert capability_map["Cover Letters"]["value"] == "Ready"
    assert "OpenAI key configured" in summary["setup_snapshot"]
    assert "Job levels set to VP, SVP" in summary["setup_snapshot"]
    assert "Next step: run Find and Add Jobs" in summary["next_step"]


def test_readiness_summary_reports_missing_setup(temp_db_path, monkeypatch):
    import services.readiness as readiness

    monkeypatch.setattr(readiness, "has_openai_api_key", lambda: False)
    monkeypatch.setattr(readiness, "load_scoring_profile_text", lambda: ("", ""))

    summary = readiness.get_readiness_summary()

    capability_map = {tile["label"]: tile for tile in summary["capabilities"]}

    assert capability_map["Discovery AI"]["value"] == "Needs Setup"
    assert capability_map["Scoring AI"]["value"] == "Needs Setup"
    assert capability_map["Cover Letters"]["value"] == "Needs Setup"
    assert "OpenAI-backed features stay off" in summary["note"]
    assert "OpenAI key missing" in summary["setup_snapshot"]
    assert "Next step: add an OpenAI API key" in summary["next_step"]


def test_readiness_summary_uses_default_cover_letter_folder_when_not_explicitly_set(
    temp_db_path, monkeypatch
):
    import services.readiness as readiness
    import services.settings as settings_module

    settings_module.save_settings(
        {
            "profile_summary": "Executive technology leader",
            "cover_letter_output_folder": "",
        }
    )

    monkeypatch.setattr(readiness, "has_openai_api_key", lambda: True)

    summary = readiness.get_readiness_summary()
    tile_map = {tile["label"]: tile for tile in summary["tiles"]}
    capability_map = {tile["label"]: tile for tile in summary["capabilities"]}

    assert tile_map["Cover Letter Folder"]["value"] == "Ready"
    assert tile_map["Cover Letter Folder"]["detail"] == settings_module.get_default_cover_letter_output_folder()
    assert capability_map["Cover Letters"]["value"] == "Ready"
