from __future__ import annotations

import json
from pathlib import Path

from config import RUNTIME_SETTINGS_FILE
from services.settings import load_settings


def write_runtime_settings_file() -> Path:
    settings = load_settings()

    RUNTIME_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RUNTIME_SETTINGS_FILE.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)

    return RUNTIME_SETTINGS_FILE
