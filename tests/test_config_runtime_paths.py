from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_source_runs_keep_repo_data_dir(monkeypatch):
    monkeypatch.delenv("JAA_DATA_DIR", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    import config

    config = importlib.reload(config)

    assert config.DATA_DIR == config.PROJECT_ROOT / "data"
    assert config.RUNTIME_SETTINGS_FILE == config.DATA_DIR / "runtime_settings.json"


def test_frozen_macos_uses_application_support(monkeypatch):
    monkeypatch.delenv("JAA_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    import config

    config = importlib.reload(config)

    assert config.DATA_DIR == Path.home() / "Library" / "Application Support" / config.APP_NAME
    assert config.RUNTIME_SETTINGS_FILE == config.DATA_DIR / "runtime_settings.json"


def test_frozen_windows_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("JAA_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    import config

    config = importlib.reload(config)

    assert config.DATA_DIR == (tmp_path / "Roaming" / config.APP_NAME).resolve()
    assert config.RUNTIME_SETTINGS_FILE == config.DATA_DIR / "runtime_settings.json"
