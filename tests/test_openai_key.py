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


def test_mask_openai_api_key():
    import services.openai_key as key_module

    masked = key_module.mask_openai_api_key("sk-test-1234567890")
    assert masked.startswith("sk-t")
    assert masked.endswith("7890")
