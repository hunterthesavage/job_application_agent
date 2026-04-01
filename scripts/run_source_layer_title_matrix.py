#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_SCRIPT = REPO_ROOT / "scripts" / "run_local_discovery_debug.py"
SUITES_ROOT = REPO_ROOT / "logs" / "discovery_debug_suites"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    current_python = Path(sys.executable)
    target_python = VENV_PYTHON
    if current_python != target_python:
        os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])


DEFAULT_TITLES = [
    "Business Analyst",
    "Project Manager",
    "Product Manager",
    "Data Analyst",
    "Software Engineer",
    "Marketing Manager",
    "Operations Manager",
    "Sales Manager",
    "Customer Success Manager",
    "HR Manager",
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _slugify(value: str) -> str:
    text = _safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "matrix"


def _report_dir_from_stdout(stdout_text: str) -> Path:
    match = re.search(r"Report directory:\s*(.+)", stdout_text)
    if not match:
        raise RuntimeError(f"Unable to find report directory in output:\n{stdout_text}")
    return Path(match.group(1).strip()).resolve()


def _extract_metric(output_text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.M)
    match = pattern.search(output_text)
    return _safe_text(match.group(1)) if match else ""


def _run_debug_report(
    *,
    title: str,
    mode: str,
    preferred_locations: str,
    remote_only: str,
    search_strategy: str,
) -> Path:
    label = f"matrix-{_slugify(title)}-{mode}"
    command = [
        str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)),
        str(DEBUG_SCRIPT),
        "--label",
        label,
        "--target-titles",
        title,
        "--preferred-locations",
        preferred_locations,
        "--remote-only",
        remote_only,
        "--search-strategy",
        search_strategy,
        "--source-layer-mode",
        mode,
        "--no-ai-title-expansion",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return _report_dir_from_stdout(completed.stdout)


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return raw


def _load_report(report_dir: Path) -> dict[str, Any]:
    summary = _load_json(report_dir / "summary.json")
    settings = _load_json(report_dir / "effective_settings.json")
    output_text = (report_dir / "output.txt").read_text(encoding="utf-8") if (report_dir / "output.txt").exists() else ""
    urls = []
    urls_file = report_dir / "urls.txt"
    if urls_file.exists():
        urls = [line.strip() for line in urls_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "report_dir": str(report_dir),
        "title": _safe_text(settings.get("target_titles", "")),
        "mode": _safe_text(summary.get("source_layer_mode", "")),
        "status": _safe_text(summary.get("status", "")),
        "url_count": int(summary.get("url_count", 0) or 0),
        "seed_url_count": int(summary.get("next_gen_seed_url_count", 0) or 0),
        "seeds_scanned": int(summary.get("next_gen_supported_seeds_scanned", 0) or 0),
        "discovery_seconds": _extract_metric(output_text, "Discovery seconds"),
        "total_pipeline_seconds": _extract_metric(output_text, "Total pipeline seconds"),
        "first_url": urls[0] if urls else "",
    }


def _combine_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        title = _safe_text(row.get("title", ""))
        entry = grouped.setdefault(title, {"title": title, "legacy": None, "next_gen": None})
        entry[str(row.get("mode", ""))] = row

    combined: list[dict[str, Any]] = []
    for title in DEFAULT_TITLES + [row["title"] for row in grouped.values() if row["title"] not in DEFAULT_TITLES]:
        if title not in grouped:
            continue
        entry = grouped[title]
        legacy = entry.get("legacy") or {}
        next_gen = entry.get("next_gen") or {}
        combined.append(
            {
                "title": title,
                "legacy_urls": int(legacy.get("url_count", 0) or 0),
                "direct_source_urls": int(next_gen.get("url_count", 0) or 0),
                "direct_source_seed_urls": int(next_gen.get("seed_url_count", 0) or 0),
                "direct_source_seeds_scanned": int(next_gen.get("seeds_scanned", 0) or 0),
                "legacy_total_seconds": _safe_text(legacy.get("total_pipeline_seconds", "")),
                "direct_source_total_seconds": _safe_text(next_gen.get("total_pipeline_seconds", "")),
                "legacy_first_url": _safe_text(legacy.get("first_url", "")),
                "direct_source_first_url": _safe_text(next_gen.get("first_url", "")),
                "legacy_report_dir": _safe_text(legacy.get("report_dir", "")),
                "direct_source_report_dir": _safe_text(next_gen.get("report_dir", "")),
            }
        )
    return combined


def _render_markdown(
    rows: list[dict[str, Any]],
    *,
    preferred_locations: str,
    remote_only: str,
    search_strategy: str,
) -> str:
    lines = [
        "# Source Layer Title Matrix",
        "",
        f"- Preferred locations: `{preferred_locations or '-'}`",
        f"- Remote only: `{remote_only}`",
        f"- Search strategy: `{search_strategy}`",
        "",
        "| Title | Legacy URLs | Direct-source URLs | Seed URLs | Seeds Scanned | Legacy Seconds | Direct-source Seconds |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['title']} | "
            f"{row['legacy_urls']} | "
            f"{row['direct_source_urls']} | "
            f"{row['direct_source_seed_urls']} | "
            f"{row['direct_source_seeds_scanned']} | "
            f"{row['legacy_total_seconds'] or '-'} | "
            f"{row['direct_source_total_seconds'] or '-'} |"
        )

    lines.append("")
    for row in rows:
        lines.append(f"## {row['title']}")
        lines.append(f"- Legacy report: `{row['legacy_report_dir'] or '-'}`")
        lines.append(f"- Direct-source report: `{row['direct_source_report_dir'] or '-'}`")
        lines.append(f"- Legacy first URL: {row['legacy_first_url'] or '-'}")
        lines.append(f"- Direct-source first URL: {row['direct_source_first_url'] or '-'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a legacy vs direct-source title comparison matrix.")
    parser.add_argument("--title", action="append", default=[], help="Specific title to include. Can be repeated.")
    parser.add_argument("--preferred-locations", default="Remote", help="Preferred locations override.")
    parser.add_argument("--remote-only", choices=("true", "false"), default="true", help="Remote-only setting.")
    parser.add_argument(
        "--search-strategy",
        choices=("balanced", "broad_recall"),
        default="broad_recall",
        help="Search strategy override.",
    )
    args = parser.parse_args()

    titles = args.title or list(DEFAULT_TITLES)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suite_dir = SUITES_ROOT / f"{timestamp}_source_layer_title_matrix"
    suite_dir.mkdir(parents=True, exist_ok=True)

    raw_rows: list[dict[str, Any]] = []
    for title in titles:
        for mode in ("legacy", "next_gen"):
            report_dir = _run_debug_report(
                title=title,
                mode=mode,
                preferred_locations=args.preferred_locations,
                remote_only=args.remote_only,
                search_strategy=args.search_strategy,
            )
            raw_rows.append(_load_report(report_dir))

    combined_rows = _combine_rows(raw_rows)
    markdown = _render_markdown(
        combined_rows,
        preferred_locations=args.preferred_locations,
        remote_only=args.remote_only,
        search_strategy=args.search_strategy,
    )

    (suite_dir / "matrix.json").write_text(json.dumps(combined_rows, indent=2) + "\n", encoding="utf-8")
    (suite_dir / "matrix.md").write_text(markdown, encoding="utf-8")
    with (suite_dir / "matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "title",
                "legacy_urls",
                "direct_source_urls",
                "direct_source_seed_urls",
                "direct_source_seeds_scanned",
                "legacy_total_seconds",
                "direct_source_total_seconds",
                "legacy_first_url",
                "direct_source_first_url",
                "legacy_report_dir",
                "direct_source_report_dir",
            ],
        )
        writer.writeheader()
        writer.writerows(combined_rows)

    print(f"Source layer title matrix complete. Suite directory: {suite_dir}")
    print(f"Markdown summary: {suite_dir / 'matrix.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
