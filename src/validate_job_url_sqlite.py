import sys
from pathlib import Path

from services.ingestion import ingest_job_records
from services.settings import load_settings
from src.validate_job_url import create_job_record


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def load_job_urls_from_file(file_path: str) -> list[str]:
    urls = []
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


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


def main() -> None:
    settings = load_settings()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.validate_job_url_sqlite <job_url_1> [job_url_2] ...")
        print("  python -m src.validate_job_url_sqlite --file job_urls.txt")
        raise SystemExit(1)

    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print("Please provide a file path after --file")
            raise SystemExit(1)
        job_urls = load_job_urls_from_file(sys.argv[2])
        source_detail = str(Path(sys.argv[2]).resolve())
        source_name = "file_urls"
    else:
        job_urls = sys.argv[1:]
        source_detail = "cli_args"
        source_name = "manual_urls"

    accepted_jobs = []
    skipped_count = 0
    error_count = 0

    for job_url in job_urls:
        print(f"\nProcessing: {job_url}")

        try:
            job = create_job_record(job_url)
            setattr(job, "source", "Local Pipeline")

            passed, reason = passes_settings_filters(job, settings)
            if not passed:
                print(f"Skipped by settings filter: {reason}")
                skipped_count += 1
                continue

            accepted_jobs.append(job)
            print(f"Accepted: {safe_text(getattr(job, 'company', ''))} | {safe_text(getattr(job, 'title', ''))}")
        except Exception as exc:
            print(f"Error: {exc}")
            error_count += 1

    summary = ingest_job_records(
        job_records=accepted_jobs,
        source_name=source_name,
        source_detail=source_detail,
        run_type="validate_urls",
    )

    print("\nValidation + ingestion complete.")
    print(f"Seen URLs: {len(job_urls)}")
    print(f"Accepted jobs: {len(accepted_jobs)}")
    print(f"Skipped by settings: {skipped_count}")
    print(f"Errors before ingest: {error_count}")
    print(f"Inserted: {summary['inserted_count']}")
    print(f"Updated: {summary['updated_count']}")
    print(f"Skipped removed: {summary['skipped_removed_count']}")


if __name__ == "__main__":
    main()
