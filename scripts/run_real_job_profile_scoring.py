#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict
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

from services.ai_job_scoring import fit_label_from_score, recommended_action_from_score, score_accepted_job
from services.source_trust import enrich_job_payload
from src.validate_job_url import create_job_record


PROFILE_PACK = [
    {
        "id": "executive_it_leader",
        "name": "Executive IT Leader",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "executive_it_leader.txt",
    },
    {
        "id": "product_program_generalist",
        "name": "Product & Program Generalist",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "product_program_generalist.txt",
    },
    {
        "id": "business_data_analyst",
        "name": "Business & Data Analyst",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "business_data_analyst.txt",
    },
    {
        "id": "gtm_marketing_ops",
        "name": "GTM / Marketing Ops",
        "profile_path": REPO_ROOT / "scripts" / "fake_profiles" / "gtm_marketing_ops.txt",
    },
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _select_profiles(ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return [
            {**item, "profile_path": str(item["profile_path"])}
            for item in PROFILE_PACK
        ]
    wanted = {item.strip().lower() for item in ids if item.strip()}
    return [
        {**item, "profile_path": str(item["profile_path"])}
        for item in PROFILE_PACK
        if item["id"] in wanted
    ]


def _load_report_urls(report_dir: Path, *, max_urls: int) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    summary = _load_json(report_dir / "summary.json")
    settings = _load_json(report_dir / "effective_settings.json")
    urls_file = report_dir / "urls.txt"
    urls: list[str] = []
    if urls_file.exists():
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                urls.append(line)
            if len(urls) >= max_urls:
                break
    return summary, settings, urls


def _score_url_for_profiles(url: str, profiles: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        job = create_job_record(url)
        payload = enrich_job_payload(asdict(job), source_hint="real_job_profile_scoring")
    except Exception as exc:
        return {
            "url": url,
            "company": "",
            "title": "",
            "location": "",
            "error": str(exc),
            "profiles": [],
        }

    profile_scores: list[dict[str, Any]] = []
    for profile in profiles:
        profile_text = Path(profile["profile_path"]).read_text(encoding="utf-8")
        score_result = score_accepted_job(payload, profile_text)
        fit_score = int(score_result.get("fit_score", 0) or 0)
        profile_scores.append(
            {
                "profile_id": profile["id"],
                "profile_name": profile["name"],
                "status": _safe_text(score_result.get("status", "")),
                "fit_score": fit_score,
                "fit_label": _safe_text(score_result.get("fit_label", "")) or fit_label_from_score(fit_score),
                "recommended_action": _safe_text(score_result.get("recommended_action", "")) or recommended_action_from_score(fit_score),
                "match_summary": _safe_text(score_result.get("match_summary", "")),
            }
        )

    return {
        "url": url,
        "company": _safe_text(payload.get("company", "")),
        "title": _safe_text(payload.get("title", "")),
        "location": _safe_text(payload.get("location", "")),
        "profiles": profile_scores,
    }


def _aggregate_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in report["selected_profiles"]:
        matching = []
        for job in report["jobs"]:
            for item in job["profiles"]:
                if item["profile_id"] == profile["id"]:
                    matching.append(item)
        if not matching:
            continue
        apply_count = sum(1 for item in matching if item["recommended_action"] == "Apply")
        caution_count = sum(1 for item in matching if item["recommended_action"] == "Apply with Caution")
        hold_count = sum(1 for item in matching if item["recommended_action"] == "Hold")
        skip_count = sum(1 for item in matching if item["recommended_action"] == "Skip")
        avg_fit = round(sum(int(item["fit_score"]) for item in matching) / len(matching), 1)
        rows.append(
            {
                "profile_name": profile["name"],
                "avg_fit_score": avg_fit,
                "apply_count": apply_count,
                "apply_caution_count": caution_count,
                "hold_count": hold_count,
                "skip_count": skip_count,
            }
        )
    return rows


def _render_markdown(reports: list[dict[str, Any]]) -> str:
    lines = [
        "# Real Job Profile Scoring",
        "",
        "| Report | Mode | Title | URLs Scored | Profile | Avg Fit | Apply | Apply w/ Caution | Hold | Skip |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for report in reports:
        aggregate = _aggregate_report(report)
        first = True
        for row in aggregate:
            lines.append(
                f"| {report['label'] if first else ''} | "
                f"{report['mode'] if first else ''} | "
                f"{report['target_titles'] if first else ''} | "
                f"{len(report['jobs']) if first else ''} | "
                f"{row['profile_name']} | "
                f"{row['avg_fit_score']} | "
                f"{row['apply_count']} | "
                f"{row['apply_caution_count']} | "
                f"{row['hold_count']} | "
                f"{row['skip_count']} |"
            )
            first = False

    lines.append("")
    for report in reports:
        lines.append(f"## {report['label']}")
        lines.append(f"- Mode: `{report['mode']}`")
        lines.append(f"- Target titles: `{report['target_titles']}`")
        lines.append(f"- Report dir: `{report['report_dir']}`")
        lines.append("")
        for job in report["jobs"]:
            heading = f"{job['title']} | {job['company']}".strip(" |")
            lines.append(f"### {heading or job['url']}")
            lines.append(f"- URL: {job['url']}")
            lines.append(f"- Location: {job['location'] or '-'}")
            if job.get("error"):
                lines.append(f"- Error: `{job['error']}`")
                lines.append("")
                continue
            for profile in job["profiles"]:
                lines.append(
                    f"- {profile['profile_name']}: {profile['fit_score']} ({profile['recommended_action']})"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score real discovered jobs from report folders against fake profiles.")
    parser.add_argument("--report-dir", action="append", required=True, help="Discovery debug report directory.")
    parser.add_argument("--profile", action="append", default=[], help="Specific fake profile id to include.")
    parser.add_argument("--max-urls", type=int, default=2, help="Maximum URLs to score per report.")
    parser.add_argument(
        "--output-dir",
        default="logs/scoring_calibration",
        help="Directory where the combined report should be written.",
    )
    args = parser.parse_args()

    profiles = _select_profiles(args.profile)
    if not profiles:
        raise SystemExit("No fake profiles matched the requested ids.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suite_dir = Path(args.output_dir) / f"{timestamp}_real_job_profiles"
    suite_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for raw_dir in args.report_dir:
        report_dir = Path(raw_dir).resolve()
        summary, settings, urls = _load_report_urls(report_dir, max_urls=max(1, int(args.max_urls)))
        print(f"Scoring report: {report_dir.name} | mode={summary.get('source_layer_mode', '')} | urls={len(urls)}")
        jobs = []
        for index, url in enumerate(urls, start=1):
            print(f"  [{index}/{len(urls)}] {url}")
            jobs.append(_score_url_for_profiles(url, profiles))
        reports.append(
            {
                "label": _safe_text(summary.get("label", report_dir.name)),
                "mode": _safe_text(summary.get("source_layer_mode", "")),
                "target_titles": _safe_text(settings.get("target_titles", "")),
                "report_dir": str(report_dir),
                "selected_profiles": profiles,
                "jobs": jobs,
            }
        )

    markdown = _render_markdown(reports)
    (suite_dir / "report.md").write_text(markdown, encoding="utf-8")
    (suite_dir / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    with (suite_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "label",
                "mode",
                "target_titles",
                "profile_name",
                "avg_fit_score",
                "apply_count",
                "apply_caution_count",
                "hold_count",
                "skip_count",
            ],
        )
        writer.writeheader()
        for report in reports:
            for row in _aggregate_report(report):
                writer.writerow(
                    {
                        "label": report["label"],
                        "mode": report["mode"],
                        "target_titles": report["target_titles"],
                        **row,
                    }
                )

    print(f"Real job profile scoring complete. Report directory: {suite_dir}")
    print(f"Markdown summary: {suite_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
