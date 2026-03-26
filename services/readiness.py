from __future__ import annotations

from pathlib import Path
from typing import Any

from services.ai_job_scoring import load_scoring_profile_text
from services.job_levels import parse_preferred_job_levels
from services.openai_key import has_openai_api_key
from services.settings import get_default_cover_letter_output_folder, load_settings


def _status_label(is_ready: bool, missing_text: str = "Needs Setup", ready_text: str = "Ready") -> str:
    return ready_text if is_ready else missing_text


def _build_setup_snapshot(
    *,
    openai_ready: bool,
    scoring_profile_ready: bool,
    preferred_levels: list[str],
    cover_letter_folder_ready: bool,
) -> str:
    parts: list[str] = []

    parts.append("OpenAI key configured" if openai_ready else "OpenAI key missing")
    parts.append("Profile Context ready" if scoring_profile_ready else "Profile Context missing")

    if preferred_levels:
        preview = ", ".join(preferred_levels[:3])
        if len(preferred_levels) > 3:
            preview += ", ..."
        parts.append(f"Job levels set to {preview}")
    else:
        parts.append("Job levels optional")

    parts.append(
        "Cover letter folder ready" if cover_letter_folder_ready else "Cover letter folder missing"
    )

    return "Setup snapshot: " + " | ".join(parts)


def _build_readiness_note(
    *,
    openai_ready: bool,
    scoring_profile_ready: bool,
    cover_letter_folder_ready: bool,
) -> str:
    if openai_ready and scoring_profile_ready and cover_letter_folder_ready:
        return "This install is ready for discovery, AI scoring, and cover letters."
    if not openai_ready:
        return "You can still discover jobs now, but OpenAI-backed features stay off until an API key is configured."
    if not scoring_profile_ready:
        return "OpenAI is configured, but AI scoring stays off until Profile Context is filled in or a fallback profile file is present."
    return "Most of the app is ready. Review the tiles below for any missing setup."


def _build_next_step(
    *,
    openai_ready: bool,
    scoring_profile_ready: bool,
    cover_letter_folder_ready: bool,
) -> str:
    if not openai_ready:
        return "Next step: add an OpenAI API key in Settings -> OpenAI API so AI title expansion, scoring, scrub, and cover letters can turn on."
    if not scoring_profile_ready:
        return "Next step: fill in Settings -> Profile Context so accepted jobs can be scored against your background."
    return "Next step: run Find and Add Jobs, then review New Roles and rescore older jobs only when needed."


def get_readiness_summary() -> dict[str, Any]:
    settings = load_settings()
    openai_ready = has_openai_api_key()

    scoring_profile_text, scoring_profile_source = load_scoring_profile_text()
    scoring_profile_ready = bool(str(scoring_profile_text or "").strip())

    preferred_levels = parse_preferred_job_levels(settings.get("preferred_job_levels", ""))
    preferred_levels_ready = bool(preferred_levels)

    cover_letter_folder = str(settings.get("cover_letter_output_folder", "") or "").strip()
    if not cover_letter_folder:
        cover_letter_folder = get_default_cover_letter_output_folder()
    folder = Path(cover_letter_folder).expanduser()
    cover_letter_folder_ready = True

    ai_title_expansion_ready = openai_ready
    ai_scoring_ready = openai_ready and scoring_profile_ready
    cover_letters_ready = openai_ready and cover_letter_folder_ready

    return {
        "tiles": [
            {
                "label": "OpenAI Key",
                "value": _status_label(openai_ready),
                "detail": "Configured" if openai_ready else "Needed for AI features",
                "ready": openai_ready,
            },
            {
                "label": "Profile Context",
                "value": _status_label(scoring_profile_ready),
                "detail": scoring_profile_source or "Fill in Settings -> Profile Context",
                "ready": scoring_profile_ready,
            },
            {
                "label": "Job Levels",
                "value": _status_label(preferred_levels_ready, missing_text="Optional"),
                "detail": ", ".join(preferred_levels[:3]) if preferred_levels_ready else "Improves score targeting",
                "ready": preferred_levels_ready,
            },
            {
                "label": "Cover Letter Folder",
                "value": _status_label(cover_letter_folder_ready),
                "detail": str(folder),
                "ready": cover_letter_folder_ready,
            },
        ],
        "capabilities": [
            {
                "label": "Discovery AI",
                "value": _status_label(ai_title_expansion_ready),
                "detail": (
                    "Can expand search titles during discovery runs"
                    if ai_title_expansion_ready
                    else "Needs OpenAI key"
                ),
                "ready": ai_title_expansion_ready,
            },
            {
                "label": "Scoring AI",
                "value": _status_label(ai_scoring_ready),
                "detail": (
                    f"Scores and scrubs accepted jobs using {scoring_profile_source}"
                    if ai_scoring_ready and scoring_profile_source
                    else "Needs OpenAI key and Profile Context"
                ),
                "ready": ai_scoring_ready,
            },
            {
                "label": "Cover Letters",
                "value": _status_label(cover_letters_ready),
                "detail": (
                    "Can generate letters into your output folder"
                    if cover_letters_ready
                    else "Needs OpenAI key"
                ),
                "ready": cover_letters_ready,
            },
        ],
        "setup_snapshot": _build_setup_snapshot(
            openai_ready=openai_ready,
            scoring_profile_ready=scoring_profile_ready,
            preferred_levels=preferred_levels,
            cover_letter_folder_ready=cover_letter_folder_ready,
        ),
        "note": _build_readiness_note(
            openai_ready=openai_ready,
            scoring_profile_ready=scoring_profile_ready,
            cover_letter_folder_ready=cover_letter_folder_ready,
        ),
        "next_step": _build_next_step(
            openai_ready=openai_ready,
            scoring_profile_ready=scoring_profile_ready,
            cover_letter_folder_ready=cover_letter_folder_ready,
        ),
    }
