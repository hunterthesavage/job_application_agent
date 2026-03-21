from __future__ import annotations

import json
from pathlib import Path

from config import PROJECT_ROOT
from services.settings import load_settings


RUNTIME_SETTINGS_FILE = PROJECT_ROOT / "runtime_settings.json"


def write_runtime_settings_file() -> Path:
    settings = load_settings()

    RUNTIME_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RUNTIME_SETTINGS_FILE.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)

    return RUNTIME_SETTINGS_FILE
