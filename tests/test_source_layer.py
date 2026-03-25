def test_get_source_layer_mode_defaults_to_legacy(monkeypatch):
    import services.source_layer as source_layer

    monkeypatch.delenv(source_layer.SOURCE_LAYER_MODE_ENV_VAR, raising=False)
    monkeypatch.setattr(source_layer, "get_setting", lambda key, default="": "", raising=False)

    assert source_layer.get_source_layer_mode() == "legacy"


def test_get_source_layer_mode_prefers_environment_override(monkeypatch):
    import services.source_layer as source_layer

    monkeypatch.setenv(source_layer.SOURCE_LAYER_MODE_ENV_VAR, "shadow")
    monkeypatch.setattr(source_layer, "get_setting", lambda key, default="": "legacy", raising=False)

    assert source_layer.get_source_layer_mode() == "shadow"


def test_set_source_layer_mode_persists_normalized_value(monkeypatch):
    import services.source_layer as source_layer

    captured = {}

    def fake_save_settings(updates):
        captured.update(updates)
        return updates

    monkeypatch.setattr(source_layer, "save_settings", fake_save_settings, raising=False)

    result = source_layer.set_source_layer_mode("NEXT_GEN")

    assert result == "next_gen"
    assert captured["source_layer_mode"] == "next_gen"
