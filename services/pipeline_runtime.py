from __future__ import annotations

from pathlib import Path
from typing import Any

from config import JOB_URLS_FILE, MANUAL_URLS_FILE
from services.ingestion import ingest_job_records
from services.matching_profiles import expand_location_terms, expand_title_terms, normalize_text
from services.settings import load_settings
from src import discover_job_urls as discover_module
from src.validate_job_url import create_job_record


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


def text_contains_any_phrase(text: str, phrases: list[str]) -> bool:
    base = normalize_text(text)
    if not base:
        return False
    return any(phrase in base for phrase in phrases if phrase)


def include_keywords_match(searchable_text: str, include_keywords: list[str]) -> bool:
    if not include_keywords:
        return True

    normalized_keywords = [normalize_text(keyword) for keyword in include_keywords if normalize_text(keyword)]
    if not normalized_keywords:
        return True

    return text_contains_any_phrase(searchable_text, normalized_keywords)


def passes_settings_filters(job, settings: dict[str, str]) -> tuple[bool, str]:
    title = safe_text(getattr(job, "title", ""))
    company = safe_text(getattr(job, "company", ""))
    location = safe_text(getattr(job, "location", ""))
    compensation_raw = safe_text(getattr(job, "compensation_raw", ""))

    searchable = " ".join([title, company, location, compensation_raw])
    normalized_title = normalize_text(title)
    normalized_location = normalize_text(location)
    normalized_searchable = normalize_text(searchable)

    target_titles = parse_csv_text(settings.get("target_titles", ""))
    preferred_locations = parse_csv_text(settings.get("preferred_locations", ""))
    include_keywords = parse_csv_text(settings.get("include_keywords", ""))
    exclude_keywords = parse_csv_text(settings.get("exclude_keywords", ""))
    remote_only = safe_text(settings.get("remote_only", "true")).lower() == "true"

    expanded_title_terms = expand_title_terms(target_titles)
    expanded_location_terms = expand_location_terms(preferred_locations)
    normalized_exclude_keywords = [normalize_text(keyword) for keyword in exclude_keywords if normalize_text(keyword)]

    if expanded_title_terms and not text_contains_any_phrase(normalized_title, expanded_title_terms):
        return False, f"title did not match target titles: {', '.join(target_titles[:5])}"

    if expanded_location_terms and not text_contains_any_phrase(normalized_location, expanded_location_terms):
        if not (remote_only and "remote" in normalized_location):
            return False, f"location did not match preferred locations: {', '.join(preferred_locations[:5])}"

    if remote_only and "remote" not in normalized_location:
        return False, "role is not marked remote"

    if not include_keywords_match(normalized_searchable, include_keywords):
        return False, f"did not include required keywords: {', '.join(include_keywords[:5])}"

    if normalized_exclude_keywords and any(keyword in normalized_searchable for keyword in normalized_exclude_keywords):
        return False, f"matched excluded keywords: {', '.join(exclude_keywords[:5])}"

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
                f"Accepted: {safe_text(getattr(job, 'company', ''))} | {safe_text(getattr(job, 'title', ''))} | {safe_text(getattr(job, 'location', ''))}"
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


def build_search_preview() -> dict[str, Any]:
    settings = load_settings()
    return {
        "plan": discover_module.build_search_plan(settings),
        "queries": discover_module.build_google_discovery_queries(settings),
    }


def discover_job_links() -> dict[str, Any]:
    settings = load_settings()
    discovery_result = discover_module.discover_urls(settings)

    discovered_urls = discovery_result.get("all_urls", [])
    discover_module.save_output_urls(JOB_URLS_FILE, discovered_urls)

    return {
        "status": "completed",
        "output": discovery_result.get("output", ""),
        "job_urls_file": str(JOB_URLS_FILE),
        "url_count": len(discovered_urls),
        "urls": discovered_urls,
        "providers": {
            "greenhouse": len(discovery_result.get("greenhouse_urls", [])),
            "lever": len(discovery_result.get("lever_urls", [])),
            "search": len(discovery_result.get("search_urls", [])),
        },
        "queries": discover_module.build_google_discovery_queries(settings),
        "plan": discover_module.build_search_plan(settings),
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
            "No URLs were available to ingest. Review your Settings criteria, confirm discovery dependencies are installed, or try pasted URLs."
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
        source_detail="in_memory_discovery_result",
    )

    if ingest_result.get("output"):
        combined_output_parts.append(ingest_result["output"])

    return {
        "status": "completed",
        "output": "\n\n".join(combined_output_parts).strip(),
        "discovery": discovery_result,
        "ingest": ingest_result,
    }
