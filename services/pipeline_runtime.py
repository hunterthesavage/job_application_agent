from __future__ import annotations

import io
import os
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from config import JOB_URLS_FILE, MANUAL_URLS_FILE, PROJECT_ROOT
from services.ingestion import ingest_job_records
from services.runtime_settings import write_runtime_settings_file
from services.settings import load_settings
from src import discover_job_urls as discover_module
from src.validate_job_url import create_job_record


@contextmanager
def working_directory(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def parse_csv_text(value: str) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def text_contains_any(text: str, patterns: list[str]) -> bool:
    base = safe_text(text).lower()
    if not base:
        return False
    return any(pattern.lower() in base for pattern in patterns)


def load_job_urls_from_file(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        return []

    urls: list[str] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    return urls


def parse_manual_urls(text_value: str) -> list[str]:
    urls: list[str] = []
    for line in str(text_value).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def passes_settings_filters(job, settings: dict[str, str]) -> tuple[bool, str]:
    title = safe_text(getattr(job, "title", ""))
    location = safe_text(getattr(job, "location", ""))
    searchable = " ".join(
        [
            title,
            safe_text(getattr(job, "company", "")),
            location,
            safe_text(getattr(job, "compensation_raw", "")),
        ]
    ).lower()

    target_titles = parse_csv_text(settings.get("target_titles", ""))
    preferred_locations = parse_csv_text(settings.get("preferred_locations", ""))
    exclude_keywords = parse_csv_text(settings.get("exclude_keywords", ""))
    remote_only = safe_text(settings.get("remote_only", "true")).lower() == "true"

    if target_titles and not text_contains_any(title, target_titles):
        return False, "settings_title_gate"

    if preferred_locations and not text_contains_any(location, preferred_locations):
        if not (remote_only and "remote" in location.lower()):
            return False, "settings_location_gate"

    if remote_only and "remote" not in location.lower():
        return False, "remote_only_gate"

    if exclude_keywords and any(keyword.lower() in searchable for keyword in exclude_keywords):
        return False, "exclude_keyword_gate"

    return True, ""


def _build_jobs_from_urls(urls: list[str], source_name: str, source_detail: str) -> dict[str, Any]:
    settings = load_settings()

    accepted_jobs = []
    skipped_count = 0
    error_count = 0
    output_lines: list[str] = []

    for job_url in urls:
        output_lines.append(f"Processing: {job_url}")

        try:
            job = create_job_record(job_url)
            setattr(job, "source", source_name)

            passed, reason = passes_settings_filters(job, settings)
            if not passed:
                output_lines.append(f"Skipped by settings filter: {reason}")
                skipped_count += 1
                continue

            accepted_jobs.append(job)
            output_lines.append(
                f"Accepted: {safe_text(getattr(job, 'company', ''))} | {safe_text(getattr(job, 'title', ''))}"
            )
        except Exception as exc:
            output_lines.append(f"Error: {exc}")
            error_count += 1

    summary = ingest_job_records(
        job_records=accepted_jobs,
        source_name=source_name,
        source_detail=source_detail,
        run_type="validate_urls",
    )

    output_lines.append("")
    output_lines.append("Validation + ingestion complete.")
    output_lines.append(f"Seen URLs: {len(urls)}")
    output_lines.append(f"Accepted jobs: {len(accepted_jobs)}")
    output_lines.append(f"Skipped by settings: {skipped_count}")
    output_lines.append(f"Errors before ingest: {error_count}")
    output_lines.append(f"Inserted: {summary['inserted_count']}")
    output_lines.append(f"Updated: {summary['updated_count']}")
    output_lines.append(f"Skipped removed: {summary['skipped_removed_count']}")

    return {
        "status": "completed",
        "output": "\n".join(output_lines).strip(),
        "summary": summary,
        "accepted_jobs": len(accepted_jobs),
        "seen_urls": len(urls),
        "skipped_count": skipped_count,
        "error_count": error_count,
    }


def discover_job_links() -> dict[str, Any]:
    write_runtime_settings_file()

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    with working_directory(PROJECT_ROOT):
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            discover_module.main()

    urls = []
    if JOB_URLS_FILE.exists():
        urls = load_job_urls_from_file(JOB_URLS_FILE)

    output = stdout_buffer.getvalue().strip()
    error_output = stderr_buffer.getvalue().strip()

    if error_output:
        output = f"{output}\n{error_output}".strip()

    if not urls:
        if output:
            output = f"{output}\n\nNo job URLs were discovered."
        else:
            output = "No job URLs were discovered."

    return {
        "status": "completed",
        "output": output,
        "job_urls_file": str(JOB_URLS_FILE),
        "url_count": len(urls),
        "urls": urls,
    }


def ingest_urls_from_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    urls = load_job_urls_from_file(path)

    if not urls:
        return {
            "status": "completed",
            "output": f"No job URLs found in: {path.resolve()}",
            "summary": {
                "inserted_count": 0,
                "updated_count": 0,
                "skipped_removed_count": 0,
            },
            "accepted_jobs": 0,
            "seen_urls": 0,
            "skipped_count": 0,
            "error_count": 0,
        }

    return _build_jobs_from_urls(urls, source_name="Local Pipeline", source_detail=str(path.resolve()))


def ingest_pasted_urls(text_value: str) -> dict[str, Any]:
    urls = parse_manual_urls(text_value)
    MANUAL_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_URLS_FILE.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    return _build_jobs_from_urls(urls, source_name="Local Pipeline", source_detail=str(MANUAL_URLS_FILE.resolve()))


def discover_and_ingest() -> dict[str, Any]:
    discovery_result = discover_job_links()
    discovered_urls = discovery_result.get("urls", [])

    combined_output_parts = []
    if discovery_result.get("output"):
        combined_output_parts.append(discovery_result["output"])

    if not discovered_urls:
        combined_output_parts.append(
            "No URLs were available to ingest. Review your Settings criteria or try a broader search."
        )
        return {
            "status": "completed",
            "output": "\n\n".join(combined_output_parts).strip(),
            "discovery": discovery_result,
            "ingest": {
                "status": "completed",
                "output": "No ingestion was performed because discovery returned zero URLs.",
                "summary": {
                    "inserted_count": 0,
                    "updated_count": 0,
                    "skipped_removed_count": 0,
                },
                "accepted_jobs": 0,
                "seen_urls": 0,
                "skipped_count": 0,
                "error_count": 0,
            },
        }

    ingest_result = _build_jobs_from_urls(
        discovered_urls,
        source_name="Local Pipeline",
        source_detail=str(JOB_URLS_FILE.resolve()),
    )

    if ingest_result.get("output"):
        combined_output_parts.append(ingest_result["output"])

    return {
        "status": "completed",
        "output": "\n\n".join(combined_output_parts).strip(),
        "discovery": discovery_result,
        "ingest": ingest_result,
    }
