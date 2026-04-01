from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from config import LATEST_PIPELINE_LOG_PATH
from services.pipeline_runtime import discover_and_ingest
from services.settings import load_settings, save_settings
from services.storage import initialize_local_storage


def _summarize_result(result: dict) -> str:
    ingest = result.get("ingest", {}) if isinstance(result.get("ingest", {}), dict) else {}
    summary = ingest.get("summary", {}) if isinstance(ingest.get("summary", {}), dict) else {}
    maintenance = result.get("maintenance", {}) if isinstance(result.get("maintenance", {}), dict) else {}

    net_new = int(summary.get("net_new_count", summary.get("inserted_count", 0)) or 0)
    rediscovered = int(summary.get("rediscovered_count", 0) or 0)
    refreshed = int(maintenance.get("refreshed_count", 0) or 0)
    rescored = int(maintenance.get("rescored_count", 0) or 0)
    return (
        f"Run complete: {net_new} net new, {rediscovered} rediscovered, "
        f"{refreshed} refreshed, {rescored} rescored."
    )


def main() -> int:
    initialize_local_storage()
    started_at = datetime.now().isoformat(timespec="seconds")
    save_settings(
        {
            "auto_run_last_started_at": started_at,
            "auto_run_last_status": "running",
        }
    )

    try:
        result = discover_and_ingest(use_ai_title_expansion=True, use_ai_scoring=True)
        output = str(result.get("output", "") or "").strip()
        LATEST_PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LATEST_PIPELINE_LOG_PATH.write_text(output, encoding="utf-8")

        finished_at = datetime.now().isoformat(timespec="seconds")
        save_settings(
            {
                "auto_run_last_finished_at": finished_at,
                "auto_run_last_status": "completed",
                "auto_run_last_summary": _summarize_result(result),
                "auto_run_last_log_path": str(LATEST_PIPELINE_LOG_PATH.resolve()),
            }
        )
        print(output)
        return 0
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        error_summary = f"{type(exc).__name__}: {exc}"
        save_settings(
            {
                "auto_run_last_finished_at": finished_at,
                "auto_run_last_status": "failed",
                "auto_run_last_summary": error_summary,
                "auto_run_last_log_path": str(LATEST_PIPELINE_LOG_PATH.resolve()),
            }
        )
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
