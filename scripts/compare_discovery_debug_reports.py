#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = REPO_ROOT / "logs" / "discovery_debug"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    current_python = Path(sys.executable)
    target_python = VENV_PYTHON
    if current_python != target_python:
        os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return raw


def _extract_metric(output_text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.M)
    match = pattern.search(output_text)
    return _safe_text(match.group(1)) if match else ""


def _latest_report_dir_for_label(label: str) -> Path | None:
    prefix = f"_{label}"
    candidates = [
        path for path in REPORTS_ROOT.iterdir()
        if path.is_dir() and path.name.endswith(prefix)
    ] if REPORTS_ROOT.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.name)


def _load_report(report_dir: Path) -> dict[str, Any]:
    summary = _load_json(report_dir / "summary.json")
    settings = _load_json(report_dir / "effective_settings.json")
    output_text = (report_dir / "output.txt").read_text(encoding="utf-8") if (report_dir / "output.txt").exists() else ""
    return {
        "report_dir": str(report_dir),
        "label": _safe_text(summary.get("label", report_dir.name)),
        "target_titles": _safe_text(settings.get("target_titles", "")),
        "status": _safe_text(summary.get("status", "")),
        "url_count": int(summary.get("url_count", 0) or 0),
        "next_gen_seed_url_count": int(summary.get("next_gen_seed_url_count", 0) or 0),
        "next_gen_supported_seeds_scanned": int(summary.get("next_gen_supported_seeds_scanned", 0) or 0),
        "provider_counts": summary.get("provider_counts", {}),
        "selected_ats_families": _extract_metric(output_text, "- Selected ATS families"),
        "selected_companies": _extract_metric(output_text, "- Selected companies"),
        "top_shadow_ats_families": _extract_metric(output_text, "- Top shadow ATS families"),
        "discovery_seconds": _extract_metric(output_text, "Discovery seconds"),
        "total_pipeline_seconds": _extract_metric(output_text, "Total pipeline seconds"),
    }


def _render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Discovery Debug Comparison",
        "",
        "| Label | Target Titles | URLs | Seed URLs | Seeds Scanned | Selected ATS Families | Total Pipeline Seconds |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['label']} | "
            f"{row['target_titles'] or '-'} | "
            f"{row['url_count']} | "
            f"{row['next_gen_seed_url_count']} | "
            f"{row['next_gen_supported_seeds_scanned']} | "
            f"{row['selected_ats_families'] or '-'} | "
            f"{row['total_pipeline_seconds'] or '-'} |"
        )

    lines.append("")
    for row in rows:
        lines.append(f"## {row['label']}")
        lines.append(f"- Report dir: `{row['report_dir']}`")
        lines.append(f"- Target titles: `{row['target_titles'] or '-'}`")
        lines.append(f"- Status: `{row['status'] or '-'}`")
        lines.append(f"- Selected companies: {row['selected_companies'] or '-'}")
        lines.append(f"- Top shadow ATS families: {row['top_shadow_ats_families'] or '-'}")
        lines.append(f"- Discovery seconds: {row['discovery_seconds'] or '-'}")
        lines.append(f"- Total pipeline seconds: {row['total_pipeline_seconds'] or '-'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare discovery debug report folders.")
    parser.add_argument("--report-dir", action="append", default=[], help="Specific report directory to include.")
    parser.add_argument("--latest-label", action="append", default=[], help="Use the latest report directory for this label.")
    parser.add_argument("--write-markdown", type=Path, help="Optional markdown output path.")
    args = parser.parse_args()

    report_dirs: list[Path] = [Path(path).resolve() for path in args.report_dir]
    for label in args.latest_label:
        latest_dir = _latest_report_dir_for_label(_safe_text(label))
        if latest_dir is None:
            raise SystemExit(f"No report directories found for label: {label}")
        report_dirs.append(latest_dir.resolve())

    deduped_dirs: list[Path] = []
    seen: set[str] = set()
    for path in report_dirs:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped_dirs.append(path)

    if not deduped_dirs:
        raise SystemExit("No report directories were provided.")

    rows = [_load_report(path) for path in deduped_dirs]
    markdown = _render_markdown(rows)

    if args.write_markdown:
        args.write_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.write_markdown.write_text(markdown, encoding="utf-8")

    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
