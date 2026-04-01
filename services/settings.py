from __future__ import annotations

from pathlib import Path

from config import APP_NAME
from services.db import db_connection


def get_default_cover_letter_output_folder() -> str:
    home_dir = Path.home()
    documents_dir = home_dir / "Documents"
    base_dir = documents_dir if documents_dir.exists() and documents_dir.is_dir() else home_dir
    return str(base_dir / APP_NAME / "Cover Letters")


def get_default_cover_letter_filename_pattern() -> str:
    return "CL_{company}.txt"


DEFAULT_SETTINGS: dict[str, str] = {
    "resume_text": "",
    "profile_summary": "",
    "strengths_to_highlight": "",
    "cover_letter_voice": "",
    "cover_letter_output_folder": get_default_cover_letter_output_folder(),
    "cover_letter_filename_pattern": get_default_cover_letter_filename_pattern(),
    "target_titles": "",
    "preferred_job_levels": "",
    "preferred_locations": "",
    "include_keywords": "",
    "exclude_keywords": "",
    "remote_only": "false",
    "search_strategy": "broad_recall",
    "minimum_compensation": "",
    "default_min_fit_score": "Any",
    "default_jobs_per_page": "10",
    "default_new_roles_sort": "Highest Fit Score",
    "openai_api_key_validated": "false",
    "openai_api_key_last_validated_at": "",
    "openai_api_key_validated_hash": "",
    "source_layer_mode": "legacy",
    "show_internal_search_tools": "false",
}


SETTINGS_KEY_ALIASES: dict[str, str] = {
    "executive_summary": "profile_summary",
    "default_minimum_fit_score": "default_min_fit_score",
}


def _normalize_key(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        return ""
    return SETTINGS_KEY_ALIASES.get(normalized, normalized)


def _normalize_value(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def load_settings() -> dict[str, str]:
    settings = DEFAULT_SETTINGS.copy()

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT key, value
            FROM app_settings
            """
        ).fetchall()

    for row in rows:
        key = _normalize_key(row["key"])
        if not key:
            continue
        if key == "require_mark_as_applied":
            continue
        settings[key] = _normalize_value(row["value"])

    if not settings.get("cover_letter_output_folder", "").strip():
        settings["cover_letter_output_folder"] = get_default_cover_letter_output_folder()
    if not settings.get("cover_letter_filename_pattern", "").strip():
        settings["cover_letter_filename_pattern"] = get_default_cover_letter_filename_pattern()

    return settings


def save_settings(updates: dict[str, str]) -> dict[str, str]:
    cleaned_updates: dict[str, str] = {}

    for raw_key, raw_value in updates.items():
        key = _normalize_key(raw_key)
        if not key or key == "require_mark_as_applied":
            continue
        cleaned_value = _normalize_value(raw_value)
        if key == "cover_letter_output_folder" and not cleaned_value:
            cleaned_value = get_default_cover_letter_output_folder()
        if key == "cover_letter_filename_pattern" and not cleaned_value:
            cleaned_value = get_default_cover_letter_filename_pattern()
        cleaned_updates[key] = cleaned_value

    with db_connection() as conn:
        for key, value in cleaned_updates.items():
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    return load_settings()


def get_setting(key: str, default: str = "") -> str:
    normalized_key = _normalize_key(key)
    settings = load_settings()
    if normalized_key in settings:
        return settings[normalized_key]
    return default
