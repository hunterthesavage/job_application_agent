import stat


def test_save_and_load_openai_api_key(tmp_path, monkeypatch):
    import config
    import services.openai_key as key_module

    key_file = tmp_path / "openai_api_key.txt"

    monkeypatch.setattr(config, "OPENAI_API_KEY_FILE", key_file, raising=False)
    monkeypatch.setattr(key_module, "OPENAI_API_KEY_FILE", key_file, raising=False)

    key_module.save_openai_api_key("sk-test-1234567890")
    loaded = key_module.load_saved_openai_api_key()

    assert loaded == "sk-test-1234567890"
    assert key_module.has_openai_api_key() is True
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_mask_openai_api_key():
    import services.openai_key as key_module

    masked = key_module.mask_openai_api_key("sk-test-1234567890")
    assert masked.startswith("sk-t")
    assert masked.endswith("7890")


def test_get_openai_api_key_details_reports_environment_source_when_no_saved_key(monkeypatch):
    import services.openai_key as key_module

    monkeypatch.setattr(key_module, "load_saved_openai_api_key", lambda: "")
    monkeypatch.setattr(key_module, "load_environment_openai_api_key", lambda: "sk-env-1234567890")

    details = key_module.get_openai_api_key_details()

    assert details["saved_key_present"] is False
    assert details["environment_key_present"] is True
    assert details["active_source"] == "environment"
    assert details["active_key_present"] is True
    assert details["can_delete_saved_key"] is False


def test_get_openai_api_key_details_prefers_saved_key_over_environment(monkeypatch):
    import services.openai_key as key_module

    monkeypatch.setattr(key_module, "load_saved_openai_api_key", lambda: "sk-saved-1234567890")
    monkeypatch.setattr(key_module, "load_environment_openai_api_key", lambda: "sk-env-1234567890")

    details = key_module.get_openai_api_key_details()

    assert details["saved_key_present"] is True
    assert details["environment_key_present"] is True
    assert details["active_source"] == "saved"
    assert details["active_key_present"] is True
    assert details["can_delete_saved_key"] is True
