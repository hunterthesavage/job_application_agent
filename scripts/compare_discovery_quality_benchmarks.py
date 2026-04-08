#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
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


def _index_rows(rows: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
    return {
        _safe_text(row.get(key_name)): row
        for row in rows
        if _safe_text(row.get(key_name))
    }


def _delta(current: Any, baseline: Any) -> float:
    return float(current or 0) - float(baseline or 0)


def _render_markdown(
    baseline_payload: dict[str, Any],
    current_payload: dict[str, Any],
) -> str:
    baseline_overall = baseline_payload.get("overall", {}) if isinstance(baseline_payload.get("overall", {}), dict) else {}
    current_overall = current_payload.get("overall", {}) if isinstance(current_payload.get("overall", {}), dict) else {}
    baseline_rows = _index_rows(list(baseline_payload.get("rows", []) or []), "title")
    current_rows = _index_rows(list(current_payload.get("rows", []) or []), "title")
    baseline_groups = _index_rows(list(baseline_payload.get("groups", []) or []), "group")
    current_groups = _index_rows(list(current_payload.get("groups", []) or []), "group")

    lines = [
        "# Discovery Quality Benchmark Comparison",
        "",
        f"- Total discovered URLs: {int(current_overall.get('total_urls', 0) or 0)} ({_delta(current_overall.get('total_urls', 0), baseline_overall.get('total_urls', 0)):+.0f})",
        f"- Total accepted jobs: {int(current_overall.get('total_accepted_jobs', 0) or 0)} ({_delta(current_overall.get('total_accepted_jobs', 0), baseline_overall.get('total_accepted_jobs', 0)):+.0f})",
        f"- Overall acceptance rate: {float(current_overall.get('overall_acceptance_rate', 0.0) or 0.0):.1f}% ({_delta(current_overall.get('overall_acceptance_rate', 0.0), baseline_overall.get('overall_acceptance_rate', 0.0)):+.1f})",
        f"- Broken URLs: {int(current_overall.get('total_broken_urls', 0) or 0)} ({_delta(current_overall.get('total_broken_urls', 0), baseline_overall.get('total_broken_urls', 0)):+.0f})",
        f"- Blocked-domain drops: {int(current_overall.get('total_blocked_domain_drops', 0) or 0)} ({_delta(current_overall.get('total_blocked_domain_drops', 0), baseline_overall.get('total_blocked_domain_drops', 0)):+.0f})",
        f"- Weak title matches: {int(current_overall.get('total_weak_title_matches', 0) or 0)} ({_delta(current_overall.get('total_weak_title_matches', 0), baseline_overall.get('total_weak_title_matches', 0)):+.0f})",
        "",
        "| Title | URLs Delta | Accepted Delta | Broken Delta | Blocked Delta | Weak Title Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for title in sorted(current_rows):
        current = current_rows[title]
        baseline = baseline_rows.get(title, {})
        lines.append(
            f"| {title} | "
            f"{_delta(current.get('url_count', 0), baseline.get('url_count', 0)):+.0f} | "
            f"{_delta(current.get('accepted_jobs', 0), baseline.get('accepted_jobs', 0)):+.0f} | "
            f"{_delta(current.get('broken_url_count', 0), baseline.get('broken_url_count', 0)):+.0f} | "
            f"{_delta(current.get('blocked_domain_drop_count', 0), baseline.get('blocked_domain_drop_count', 0)):+.0f} | "
            f"{_delta(current.get('weak_title_match_count', 0), baseline.get('weak_title_match_count', 0)):+.0f} |"
        )

    lines.extend(
        [
            "",
            "## Variant Group Delta",
            "",
            "| Group | Overlap Delta | Accepted Gap Delta | Broken Gap Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for group_name in sorted(current_groups):
        current = current_groups[group_name]
        baseline = baseline_groups.get(group_name, {})
        lines.append(
            f"| {group_name} | "
            f"{_delta(current.get('overlap_rate', 0.0), baseline.get('overlap_rate', 0.0)):+.1f} | "
            f"{_delta(current.get('accepted_gap', 0), baseline.get('accepted_gap', 0)):+.0f} | "
            f"{_delta(current.get('broken_gap', 0), baseline.get('broken_gap', 0)):+.0f} |"
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two discovery quality benchmark JSON reports.")
    parser.add_argument("--baseline-json", type=Path, required=True, help="Baseline benchmark JSON.")
    parser.add_argument("--current-json", type=Path, required=True, help="Current benchmark JSON.")
    parser.add_argument("--write-markdown", type=Path, help="Optional markdown output path.")
    args = parser.parse_args()

    baseline_payload = _load_json(args.baseline_json.resolve())
    current_payload = _load_json(args.current_json.resolve())
    markdown = _render_markdown(baseline_payload, current_payload)

    if args.write_markdown:
        args.write_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.write_markdown.write_text(markdown, encoding="utf-8")

    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
