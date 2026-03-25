from __future__ import annotations

import os

from services.settings import get_setting, save_settings


ALLOWED_SOURCE_LAYER_MODES = {"legacy", "shadow", "next_gen"}
SOURCE_LAYER_MODE_ENV_VAR = "JOB_AGENT_SOURCE_LAYER_MODE"
DEFAULT_SOURCE_LAYER_MODE = "legacy"


def _normalize_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in ALLOWED_SOURCE_LAYER_MODES:
        return normalized
    return DEFAULT_SOURCE_LAYER_MODE


def get_source_layer_mode() -> str:
    env_value = os.getenv(SOURCE_LAYER_MODE_ENV_VAR, "")
    if str(env_value or "").strip():
        return _normalize_mode(env_value)

    return _normalize_mode(get_setting("source_layer_mode", DEFAULT_SOURCE_LAYER_MODE))


def set_source_layer_mode(value: str) -> str:
    normalized = _normalize_mode(value)
    save_settings({"source_layer_mode": normalized})
    return normalized
