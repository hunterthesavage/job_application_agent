from __future__ import annotations

import os
from pathlib import Path

from config import OPENAI_API_KEY_FILE


_KEY_WRAPPER_CHARS = "\"'“”‘’`"


def _normalize_openai_api_key(value: str) -> str:
    key = str(value or "").strip()
    while len(key) >= 2 and key[0] in _KEY_WRAPPER_CHARS and key[-1] in _KEY_WRAPPER_CHARS:
        key = key[1:-1].strip()
    return key


def save_openai_api_key(api_key: str) -> Path:
    key = _normalize_openai_api_key(api_key)
    if not key:
        raise ValueError("API key cannot be empty.")

    OPENAI_API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPENAI_API_KEY_FILE.write_text(key + "\n", encoding="utf-8")
    try:
        OPENAI_API_KEY_FILE.chmod(0o600)
    except Exception:
        # Best effort on platforms that may not support POSIX-like permissions.
        pass
    return OPENAI_API_KEY_FILE


def load_saved_openai_api_key() -> str:
    if not OPENAI_API_KEY_FILE.exists():
        return ""

    return _normalize_openai_api_key(OPENAI_API_KEY_FILE.read_text(encoding="utf-8"))


def load_environment_openai_api_key() -> str:
    return _normalize_openai_api_key(os.getenv("OPENAI_API_KEY", ""))


def get_effective_openai_api_key() -> str:
    saved_key = load_saved_openai_api_key()
    if saved_key:
        return saved_key

    return load_environment_openai_api_key()


def has_openai_api_key() -> bool:
    return bool(get_effective_openai_api_key())


def mask_openai_api_key(value: str) -> str:
    key = str(value or "").strip()
    if not key:
        return "Not saved"

    if len(key) <= 8:
        return "*" * len(key)

    return f"{key[:4]}{'*' * max(4, len(key) - 8)}{key[-4:]}"


def get_openai_api_key_details() -> dict[str, object]:
    saved_key = load_saved_openai_api_key()
    env_key = load_environment_openai_api_key()

    if saved_key:
        active_key = saved_key
        active_source = "saved"
    elif env_key:
        active_key = env_key
        active_source = "environment"
    else:
        active_key = ""
        active_source = "none"

    return {
        "saved_key_present": bool(saved_key),
        "environment_key_present": bool(env_key),
        "active_key_present": bool(active_key),
        "active_source": active_source,
        "can_delete_saved_key": bool(saved_key),
        "saved_key_masked": mask_openai_api_key(saved_key),
        "environment_key_masked": mask_openai_api_key(env_key),
        "active_key_masked": mask_openai_api_key(active_key),
        "saved_file_path": str(OPENAI_API_KEY_FILE),
    }


def delete_saved_openai_api_key() -> None:
    if OPENAI_API_KEY_FILE.exists():
        OPENAI_API_KEY_FILE.unlink()
