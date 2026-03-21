from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

from openai import OpenAI

from config import OPENAI_API_STATE_FILE


def _empty_state() -> dict[str, str]:
    return {
        "api_key": "",
        "validated": "false",
        "validated_at": "",
        "validated_hash": "",
    }


def _key_fingerprint(api_key: str) -> str:
    key = str(api_key or "").strip()
    if not key:
        return ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _read_state() -> dict[str, str]:
    if not OPENAI_API_STATE_FILE.exists():
        return _empty_state()

    try:
        raw = json.loads(OPENAI_API_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()

    state = _empty_state()
    state["api_key"] = str(raw.get("api_key", "") or "").strip()
    state["validated"] = str(raw.get("validated", "false") or "false").strip().lower()
    state["validated_at"] = str(raw.get("validated_at", "") or "").strip()
    state["validated_hash"] = str(raw.get("validated_hash", "") or "").strip()
    return state


def _write_state(state: dict[str, str]) -> None:
    OPENAI_API_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPENAI_API_STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def save_openai_api_key(api_key: str):
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("API key cannot be empty.")

    state = _empty_state()
    state["api_key"] = key
    _write_state(state)

    return OPENAI_API_STATE_FILE


def load_saved_openai_api_key() -> str:
    state = _read_state()
    return state["api_key"]


def get_effective_openai_api_key() -> str:
    saved_key = load_saved_openai_api_key()
    if saved_key:
        return saved_key

    return str(os.getenv("OPENAI_API_KEY", "")).strip()


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
    if OPENAI_API_STATE_FILE.exists():
        OPENAI_API_STATE_FILE.unlink()


def validate_openai_api_key() -> dict[str, str]:
    api_key = get_effective_openai_api_key()
    if not api_key:
        raise ValueError("No API key is configured.")

    client = OpenAI(api_key=api_key)
    client.models.list()

    validated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    validated_hash = _key_fingerprint(api_key)

    state = _read_state()
    state["api_key"] = api_key
    state["validated"] = "true"
    state["validated_at"] = validated_at
    state["validated_hash"] = validated_hash
    _write_state(state)

    return {
        "status": "validated",
        "validated_at": validated_at,
    }


def is_openai_api_key_validated() -> bool:
    state = _read_state()
    current_key = get_effective_openai_api_key()

    if not current_key:
        return False

    if state["validated"] != "true":
        return False

    current_hash = _key_fingerprint(current_key)
    return bool(current_hash and current_hash == state["validated_hash"])


def is_openai_ready() -> bool:
    return has_openai_api_key() and is_openai_api_key_validated()


def get_openai_disabled_reason() -> str:
    if not has_openai_api_key():
        return "Enable API Key in Settings first"
    if not is_openai_api_key_validated():
        return "Validate API Key in Settings first"
    return ""


def get_openai_validation_status() -> dict[str, str]:
    state = _read_state()
    return {
        "has_key": "true" if has_openai_api_key() else "false",
        "validated": "true" if is_openai_api_key_validated() else "false",
        "last_validated_at": state["validated_at"],
    }
