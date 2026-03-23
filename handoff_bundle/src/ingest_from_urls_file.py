import sys

from config import JOB_URLS_FILE
from src.validate_job_url_sqlite import load_job_urls_from_file
from services.ingestion import ingest_job_records
from src.validate_job_url import create_job_record
from services.settings import load_settings


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def text_contains_any(text: str, patterns: list[str]) -> bool:
    base = safe_text(text).lower()
    if not base:
        return False
    return any(pattern.lower() in base for pattern in patterns)


def parse_csv_text(value: str) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def passes_settings_filters(job, settings: dict[str, str]) -> bool:
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
        return False

    if preferred_locations and not text_contains_any(location, preferred_locations):
        if not (remote_only and "remote" in location.lower()):
            return False

    if remote_only and "remote" not in location.lower():
        return False

    if exclude_keywords and any(keyword.lower() in searchable for keyword in exclude_keywords):
        return False

    return True


def main() -> None:
    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        file_path = str(JOB_URLS_FILE)

    settings = load_settings()
    urls = load_job_urls_from_file(file_path)
    jobs = []

    for url in urls:
        try:
            job = create_job_record(url)
            setattr(job, "source", "Local Pipeline")
            if passes_settings_filters(job, settings):
                jobs.append(job)
        except Exception as exc:
            print(f"Failed on {url}: {exc}")

    summary = ingest_job_records(
        job_records=jobs,
        source_name="job_urls_file",
        source_detail=file_path,
        run_type="ingest_url_file",
    )

    print("Ingest complete.")
    print(summary)


if __name__ == "__main__":
    main()
