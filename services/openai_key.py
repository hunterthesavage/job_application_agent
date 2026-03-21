from __future__ import annotations

import os
from pathlib import Path

from config import OPENAI_API_KEY_FILE


def save_openai_api_key(api_key: str) -> Path:
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("API key cannot be empty.")

    OPENAI_API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPENAI_API_KEY_FILE.write_text(key + "\n", encoding="utf-8")
    return OPENAI_API_KEY_FILE


def load_saved_openai_api_key() -> str:
    if not OPENAI_API_KEY_FILE.exists():
        return ""

    key = OPENAI_API_KEY_FILE.read_text(encoding="utf-8").strip()
    return key


def get_effective_openai_api_key() -> str:
    saved_key = load_saved_openai_api_key()
    if saved_key:
        return saved_key

    env_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    return env_key


def has_openai_api_key() -> bool:
    return bool(get_effective_openai_api_key())


def mask_openai_api_key(value: str) -> str:
    key = str(value or "").strip()
    if not key:
        return "Not saved"

    if len(key) <= 8:
        return "*" * len(key)

    return f"{key[:4]}{'*' * max(4, len(key) - 8)}{key[-4:]}"


def delete_saved_openai_api_key() -> None:
    if OPENAI_API_KEY_FILE.exists():
        OPENAI_API_KEY_FILE.unlink()
