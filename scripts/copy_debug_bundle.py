from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import DATABASE_PATH, LATEST_PIPELINE_LOG_PATH
from services.db import db_connection
from services.ingestion import get_recent_ingestion_runs, get_source_registry_summary
from services.settings import load_settings


def safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def print_section(title: str) -> None:
    print(f"\n===== {title} =====")


def main() -> None:
    print_section("DATABASE")
    print(f"DATABASE_PATH: {DATABASE_PATH}")

    with db_connection() as conn:
        jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        removed = conn.execute("SELECT COUNT(*) FROM removed_jobs").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
        print(f"jobs_count: {jobs}")
        print(f"removed_jobs_count: {removed}")
        print(f"ingestion_runs_count: {runs}")

    print_section("CURRENT SETTINGS")
    settings = load_settings()
    keys_to_show = [
        "target_titles",
        "preferred_locations",
        "include_keywords",
        "exclude_keywords",
        "remote_only",
        "default_min_fit_score",
        "default_jobs_per_page",
        "default_new_roles_sort",
    ]
    for key in keys_to_show:
        print(f"{key}: {safe_text(settings.get(key, ''))}")

    print_section("LATEST INGESTION RUN")
    runs = get_recent_ingestion_runs(limit=1)
    if not runs:
        print("No ingestion runs found.")
    else:
        run = runs[0]
        print(f"run_id: {run.get('id')}")
        print(f"run_type: {run.get('run_type')}")
        print(f"source_name: {run.get('source_name')}")
        print(f"source_detail: {run.get('source_detail')}")
        print(f"started_at: {run.get('started_at')}")
        print(f"completed_at: {run.get('completed_at')}")
        print(f"status: {run.get('status')}")
        print(f"total_seen: {run.get('total_seen')}")
        print(f"inserted_count: {run.get('inserted_count')}")
        print(f"updated_count: {run.get('updated_count')}")
        print(f"skipped_removed_count: {run.get('skipped_removed_count')}")
        print(f"skipped_invalid_count: {run.get('skipped_invalid_count')}")
        print(f"error_count: {run.get('error_count')}")

        details = run.get("details", {}) or {}
        print("\n--- details_json ---")
        print(json.dumps(details, indent=2, sort_keys=True))

    print_section("SOURCE REGISTRY SUMMARY")
    try:
        summary = get_source_registry_summary()
        print(json.dumps(summary, indent=2, sort_keys=True))
    except Exception as exc:
        print(f"Could not load source registry summary: {exc}")

    print_section("LATEST PIPELINE LOG")
    if Path(LATEST_PIPELINE_LOG_PATH).exists():
        try:
            print(Path(LATEST_PIPELINE_LOG_PATH).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Could not read latest pipeline log: {exc}")
    else:
        print(f"No pipeline log found yet at: {LATEST_PIPELINE_LOG_PATH}")


if __name__ == "__main__":
    main()
