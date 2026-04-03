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


def _looks_like_cover_letter_filename(value: str) -> bool:
    text = _normalize_value(value)
    if not text:
        return False
    lower = text.lower()
    has_path_separator = "/" in text or "\\" in text
    return not has_path_separator and (
        lower.endswith((".txt", ".doc", ".docx", ".md", ".pdf")) or "{" in text or "}" in text
    )


def _looks_like_folder_path(value: str) -> bool:
    text = _normalize_value(value)
    if not text:
        return False
    return any(marker in text for marker in ("/", "\\", "~")) or (
        len(text) >= 2 and text[1] == ":"
    )


def normalize_cover_letter_output_settings(folder_value, pattern_value) -> tuple[str, str]:
    folder = _normalize_value(folder_value)
    pattern = _normalize_value(pattern_value)

    if not folder or _looks_like_cover_letter_filename(folder):
        folder = get_default_cover_letter_output_folder()
    if not pattern or _looks_like_folder_path(pattern):
        pattern = get_default_cover_letter_filename_pattern()

    return folder, pattern


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
    "include_remote": "true",
    "remote_only": "false",
    "search_strategy": "broad_recall",
    "minimum_compensation": "",
    "default_min_fit_score": "Any",
    "default_jobs_per_page": "10",
    "default_new_roles_sort": "Newest First",
    "openai_api_key_validated": "false",
    "openai_api_key_last_validated_at": "",
    "openai_api_key_validated_hash": "",
    "source_layer_mode": "legacy",
    "show_internal_search_tools": "false",
    "auto_run_enabled": "false",
    "auto_run_frequency": "off",
    "auto_run_time": "08:00",
    "auto_run_days": "mon,tue,wed,thu,fri",
    "auto_run_last_started_at": "",
    "auto_run_last_finished_at": "",
    "auto_run_last_status": "",
    "auto_run_last_summary": "",
    "auto_run_last_log_path": "",
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
    (
        settings["cover_letter_output_folder"],
        settings["cover_letter_filename_pattern"],
    ) = normalize_cover_letter_output_settings(
        settings.get("cover_letter_output_folder", ""),
        settings.get("cover_letter_filename_pattern", ""),
    )

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

    if "cover_letter_output_folder" in cleaned_updates or "cover_letter_filename_pattern" in cleaned_updates:
        current_settings = load_settings()
        normalized_folder, normalized_pattern = normalize_cover_letter_output_settings(
            cleaned_updates.get("cover_letter_output_folder", current_settings.get("cover_letter_output_folder", "")),
            cleaned_updates.get(
                "cover_letter_filename_pattern",
                current_settings.get("cover_letter_filename_pattern", ""),
            ),
        )
        cleaned_updates["cover_letter_output_folder"] = normalized_folder
        cleaned_updates["cover_letter_filename_pattern"] = normalized_pattern

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
