from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.ai_job_scoring import DEFAULT_MODEL, load_scoring_profile_text
from services.scoring_calibration import (
    evaluate_calibration_cases,
    load_calibration_cases,
    render_calibration_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a labeled scoring calibration set.")
    parser.add_argument(
        "--cases",
        default="scripts/calibration_sets/vp_it_sample.jsonl",
        help="Path to a JSON or JSONL calibration case file.",
    )
    parser.add_argument(
        "--use-ai-scoring",
        action="store_true",
        help="Call AI scoring using the saved profile and configured OpenAI key.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model to use when --use-ai-scoring is enabled.",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/scoring_calibration",
        help="Directory where calibration reports should be written.",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases)
    cases = load_calibration_cases(cases_path)

    resume_profile_text = ""
    resume_profile_source = ""
    if args.use_ai_scoring:
        resume_profile_text, resume_profile_source = load_scoring_profile_text()

    report = evaluate_calibration_cases(
        cases,
        resume_profile_text=resume_profile_text,
        use_ai_scoring=args.use_ai_scoring,
        model=args.model,
    )
    report["cases_path"] = str(cases_path)
    report["resume_profile_source"] = resume_profile_source

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.output_dir) / f"{timestamp}_{cases_path.stem}"
    report_dir.mkdir(parents=True, exist_ok=True)

    (report_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (report_dir / "report.md").write_text(render_calibration_report(report), encoding="utf-8")

    print(f"Scoring calibration complete. Report directory: {report_dir}")
    print(
        "Summary: "
        f"cases={report['total_cases']} "
        f"qualifier_exact={report['qualifier_summary']['exact_matches']} "
        f"qualifier_far_misses={report['qualifier_summary']['far_misses']} "
        f"ai_enabled={'yes' if args.use_ai_scoring else 'no'}"
    )


if __name__ == "__main__":
    main()

