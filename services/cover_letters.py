from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from services.openai_key import get_effective_openai_api_key
from services.settings import DEFAULT_SETTINGS, get_default_cover_letter_output_folder, load_settings
from services.sqlite_actions import get_job_by_id, record_cover_letter_artifact


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def slugify_filename_part(value: str, fallback: str = "Value") -> str:
    text = safe_text(value)
    if not text:
        return fallback

    text = re.sub(r'[\\/:*?"<>|]+', "", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def load_profile_context_from_settings(settings: dict[str, str]) -> str:
    parts = []

    resume_text = safe_text(settings.get("resume_text", ""))
    profile_summary = safe_text(settings.get("profile_summary", ""))
    strengths_to_highlight = safe_text(settings.get("strengths_to_highlight", ""))
    cover_letter_voice = safe_text(settings.get("cover_letter_voice", ""))

    if profile_summary:
        parts.append("Executive Summary:\n" + profile_summary)

    if strengths_to_highlight:
        parts.append("Strengths to Highlight:\n" + strengths_to_highlight)

    if cover_letter_voice:
        parts.append("Cover Letter Voice:\n" + cover_letter_voice)

    if resume_text:
        parts.append("Resume Text:\n" + resume_text)

    return "\n\n".join(parts).strip()


def generate_letter(profile_context: str, job: dict[str, str]) -> str:
    api_key = get_effective_openai_api_key()
    if not api_key:
        raise ValueError(
            "No OpenAI API key is configured. Add one in Settings → OpenAI API, or set OPENAI_API_KEY in your environment."
        )

    client = OpenAI(api_key=api_key)

    prompt = f"""
Candidate profile:
{profile_context}

Job details:
Company: {job.get('company', '')}
Title: {job.get('title', '')}
Location: {job.get('location', '')}
Role Family: {job.get('role_family', '')}
Match Rationale: {job.get('match_rationale', '')}
Application Angle: {job.get('application_angle', '')}
Cover Letter Starter: {job.get('cover_letter_starter', '')}
Compensation: {job.get('compensation_raw', '')}

Write a tailored executive-level cover letter.

Requirements:
- 4 to 6 paragraphs
- confident, modern executive tone
- no bullet points
- no em dashes
- tailored to role and company
- emphasize leadership, transformation, execution
- avoid generic phrasing
- plain text only
- sign as Hunter Samuels
""".strip()

    response = client.responses.create(
        model="gpt-5",
        input=prompt,
    )

    return response.output_text.strip()


def build_output_folder(settings: dict[str, str]) -> Path:
    folder = safe_text(settings.get("cover_letter_output_folder", ""))
    if not folder:
        folder = get_default_cover_letter_output_folder()

    path = Path(folder).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_output_filename(settings: dict[str, str], job: dict[str, str]) -> str:
    pattern = safe_text(settings.get("cover_letter_filename_pattern", ""))
    if not pattern:
        pattern = DEFAULT_SETTINGS["cover_letter_filename_pattern"]

    company = slugify_filename_part(job.get("company", ""), fallback="Company")
    title = slugify_filename_part(job.get("title", ""), fallback="Role")
    date_text = datetime.now().strftime("%Y%m%d")

    replacements = {
        "company": company,
        "title": title,
        "date": date_text,
    }

    try:
        filename = pattern.format(**replacements)
    except Exception:
        filename = DEFAULT_SETTINGS["cover_letter_filename_pattern"].format(**replacements)

    filename = safe_text(filename)
    if not filename.lower().endswith(".txt"):
        filename = f"{filename}.txt"

    filename = re.sub(r'[\\/:*?"<>|]+', "", filename)
    filename = re.sub(r"\s+", "_", filename).strip()

    return filename or f"CL_Hunter_Samuels_{company}.txt"


def save_letter_to_file(letter: str, settings: dict[str, str], job: dict[str, str]) -> Path:
    output_folder = build_output_folder(settings)
    filename = build_output_filename(settings, job)
    output_path = output_folder / filename
    output_path.write_text(letter + "\n", encoding="utf-8")
    return output_path


def generate_cover_letter_for_job_id(job_id: int) -> dict[str, str]:
    job = get_job_by_id(job_id)
    if job is None:
        raise ValueError(f"Job id {job_id} not found.")

    settings = load_settings()
    profile_context = load_profile_context_from_settings(settings)

    letter = generate_letter(profile_context, job)
    output_path = save_letter_to_file(letter, settings, job)
    record_cover_letter_artifact(job_id, str(output_path))

    return {
        "job_id": str(job_id),
        "company": safe_text(job.get("company", "")),
        "title": safe_text(job.get("title", "")),
        "output_path": str(output_path),
    }
