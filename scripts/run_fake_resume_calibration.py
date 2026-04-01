#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    current_python = Path(sys.executable)
    target_python = VENV_PYTHON
    if current_python != target_python:
        os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.ai_job_scoring import DEFAULT_MODEL
from services.scoring_calibration import (
    evaluate_calibration_cases,
    load_calibration_cases,
    render_calibration_report,
)


PROFILE_PACK = [
    {
        "id": "executive_it_leader",
        "name": "Executive IT Leader",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "executive_it_leader.txt",
        "cases_path": REPO_ROOT / "scripts" / "calibration_sets" / "fake_resume_executive_it_leader.jsonl",
    },
    {
        "id": "product_program_generalist",
        "name": "Product & Program Generalist",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "product_program_generalist.txt",
        "cases_path": REPO_ROOT / "scripts" / "calibration_sets" / "fake_resume_product_program_generalist.jsonl",
    },
    {
        "id": "business_data_analyst",
        "name": "Business & Data Analyst",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "business_data_analyst.txt",
        "cases_path": REPO_ROOT / "scripts" / "calibration_sets" / "fake_resume_business_data_analyst.jsonl",
    },
    {
        "id": "gtm_marketing_ops",
        "name": "GTM / Marketing Ops",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "gtm_marketing_ops.txt",
        "cases_path": REPO_ROOT / "scripts" / "calibration_sets" / "fake_resume_gtm_marketing_ops.jsonl",
    },
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _select_profiles(ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return list(PROFILE_PACK)
    wanted = {item.strip().lower() for item in ids if item.strip()}
    return [item for item in PROFILE_PACK if item["id"] in wanted]


def _profile_report_row(profile: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    qualifier = report.get("qualifier_summary", {}) or {}
    ai = report.get("ai_summary", {}) or {}
    return {
        "profile_id": profile["id"],
        "profile_name": profile["name"],
        "cases": int(report.get("total_cases", 0) or 0),
        "qualifier_exact": int(qualifier.get("exact_matches", 0) or 0),
        "qualifier_adjacent": int(qualifier.get("adjacent_matches", 0) or 0),
        "qualifier_far": int(qualifier.get("far_misses", 0) or 0),
        "ai_exact": int(ai.get("exact_matches", 0) or 0),
        "ai_adjacent": int(ai.get("adjacent_matches", 0) or 0),
        "ai_far": int(ai.get("far_misses", 0) or 0),
        "ai_skipped": int(ai.get("skipped_or_unscored", 0) or 0),
    }


def _render_summary(rows: list[dict[str, Any]], *, use_ai_scoring: bool, model: str) -> str:
    lines = [
        "# Fake Resume Calibration Summary",
        "",
        f"- AI scoring enabled: {'yes' if use_ai_scoring else 'no'}",
    ]
    if use_ai_scoring:
        lines.append(f"- Model: {model}")
    lines.extend(
        [
            "",
            "| Profile | Cases | Qualifier Exact | Qualifier Adjacent | Qualifier Far | AI Exact | AI Adjacent | AI Far | AI Skipped |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['profile_name']} | {row['cases']} | {row['qualifier_exact']} | {row['qualifier_adjacent']} | {row['qualifier_far']} | "
            f"{row['ai_exact']} | {row['ai_adjacent']} | {row['ai_far']} | {row['ai_skipped']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI scoring calibration against a fake resume/profile pack.")
    parser.add_argument("--profile", action="append", default=[], help="Specific fake profile id to include.")
    parser.add_argument("--use-ai-scoring", action="store_true", help="Run the AI scorer with each fake profile.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use when AI scoring is enabled.")
    parser.add_argument(
        "--output-dir",
        default="logs/scoring_calibration",
        help="Directory where fake resume calibration reports should be written.",
    )
    args = parser.parse_args()

    selected_profiles = _select_profiles(args.profile)
    if not selected_profiles:
        raise SystemExit("No fake profiles matched the requested ids.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suite_dir = Path(args.output_dir) / f"{timestamp}_fake_resume_profiles"
    suite_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    for profile in selected_profiles:
        profile_text = profile["profile_path"].read_text(encoding="utf-8")
        cases = load_calibration_cases(profile["cases_path"])
        report = evaluate_calibration_cases(
            cases,
            resume_profile_text=profile_text,
            use_ai_scoring=bool(args.use_ai_scoring),
            model=args.model,
        )
        report["profile_id"] = profile["id"]
        report["profile_name"] = profile["name"]
        report["profile_path"] = str(profile["profile_path"])
        report["cases_path"] = str(profile["cases_path"])

        profile_dir = suite_dir / profile["id"]
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (profile_dir / "report.md").write_text(render_calibration_report(report), encoding="utf-8")
        summary_rows.append(_profile_report_row(profile, report))

    (suite_dir / "summary.json").write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")
    (suite_dir / "summary.md").write_text(
        _render_summary(summary_rows, use_ai_scoring=bool(args.use_ai_scoring), model=args.model),
        encoding="utf-8",
    )
    with (suite_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "profile_id",
                "profile_name",
                "cases",
                "qualifier_exact",
                "qualifier_adjacent",
                "qualifier_far",
                "ai_exact",
                "ai_adjacent",
                "ai_far",
                "ai_skipped",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Fake resume calibration complete. Report directory: {suite_dir}")
    print(
        "Summary: "
        f"profiles={len(summary_rows)} "
        f"ai_enabled={'yes' if args.use_ai_scoring else 'no'} "
        f"model={args.model if args.use_ai_scoring else '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
