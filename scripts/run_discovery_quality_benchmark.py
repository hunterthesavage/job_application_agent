#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_SCRIPT = REPO_ROOT / "scripts" / "run_local_discovery_debug.py"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    current_python = Path(sys.executable)
    target_python = VENV_PYTHON
    if current_python != target_python:
        os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])


DEFAULT_CASES = [
    {"group": "it_manager_variants", "variant": "manager", "title": "IT Manager"},
    {"group": "it_manager_variants", "variant": "mgr", "title": "IT Mgr"},
    {"group": "program_manager_variants", "variant": "manager", "title": "Program Manager"},
    {"group": "program_manager_variants", "variant": "mgr", "title": "Program Mgr"},
    {"group": "it_director_variants", "variant": "director", "title": "Director of IT"},
    {"group": "it_director_variants", "variant": "dir", "title": "Dir of IT"},
    {"group": "infrastructure_director_variants", "variant": "director", "title": "Director of Infrastructure"},
    {"group": "infrastructure_director_variants", "variant": "dir", "title": "Dir of Infrastructure"},
    {"group": "vp_it_variants", "variant": "vp", "title": "VP of IT"},
    {"group": "vp_it_variants", "variant": "vice_president", "title": "Vice President of Information Technology"},
    {"group": "vp_infrastructure_variants", "variant": "vp", "title": "VP Infrastructure"},
    {"group": "vp_infrastructure_variants", "variant": "vice_president", "title": "Vice President Infrastructure"},
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _slugify(value: str) -> str:
    text = _safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "benchmark"


def _report_dir_from_stdout(stdout_text: str) -> Path:
    match = re.search(r"Report directory:\s*(.+)", stdout_text)
    if not match:
        raise RuntimeError(f"Unable to find report directory in output:\n{stdout_text}")
    return Path(match.group(1).strip()).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return raw


def _flatten_counts(raw: Any) -> Counter:
    flattened: Counter = Counter()
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    flattened[_safe_text(nested_key)] += int(nested_value or 0)
            else:
                flattened[_safe_text(key)] += int(value or 0)
    return flattened


def _run_case(
    *,
    title: str,
    label: str,
    preferred_locations: str,
    remote_only: str,
    search_strategy: str,
    source_layer_mode: str,
) -> Path:
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
        source_layer_mode,
        "--no-ai-title-expansion",
        "--validate-urls",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return _report_dir_from_stdout(completed.stdout)


def _load_row(case: dict[str, str], report_dir: Path) -> dict[str, Any]:
    summary = _load_json(report_dir / "summary.json")
    urls_file = report_dir / "urls.txt"
    urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if urls_file.exists() else []
    normalized_urls = {_safe_text(url).lower() for url in urls if _safe_text(url)}
    url_domains = sorted(
        {
            _safe_text(urlparse(url).netloc).lower()
            for url in urls
            if _safe_text(urlparse(url).netloc)
        }
    )
    skip_summary = _flatten_counts(summary.get("validation_skip_summary", {}))
    drop_summary = _flatten_counts(summary.get("drop_summary", {}))

    stale_ats = int(skip_summary.get("stale_ats_posting", 0) or 0)
    parse_failed = int(skip_summary.get("parse_failed", 0) or 0)
    blocked_domains = int(drop_summary.get("blocked_domain", 0) or 0)
    weak_title_match = int(skip_summary.get("weak_url_title_match", 0) or 0)
    duplicate_batch = int(summary.get("validation_skipped_duplicate_batch_count", 0) or 0)
    accepted_jobs = int(summary.get("accepted_jobs", 0) or 0)
    seen_urls = int(summary.get("seen_urls", 0) or 0)

    return {
        "group": _safe_text(case.get("group")),
        "variant": _safe_text(case.get("variant")),
        "title": _safe_text(case.get("title")),
        "report_dir": str(report_dir),
        "url_count": int(summary.get("url_count", 0) or 0),
        "seen_urls": seen_urls,
        "accepted_jobs": accepted_jobs,
        "acceptance_rate": round((accepted_jobs / seen_urls) * 100, 1) if seen_urls else 0.0,
        "seed_url_count": int(summary.get("next_gen_seed_url_count", 0) or 0),
        "seeds_scanned": int(summary.get("next_gen_supported_seeds_scanned", 0) or 0),
        "selected_ats_families": _safe_text(summary.get("selected_ats_families", "")),
        "stale_ats_posting_count": stale_ats,
        "parse_failed_count": parse_failed,
        "broken_url_count": stale_ats + parse_failed,
        "blocked_domain_drop_count": blocked_domains,
        "weak_title_match_count": weak_title_match,
        "duplicate_batch_skip_count": duplicate_batch,
        "validation_error_count": int(summary.get("validation_error_count", 0) or 0),
        "unique_domain_count": len(url_domains),
        "url_domains": url_domains,
        "normalized_urls": sorted(normalized_urls),
    }


def _summarize_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_safe_text(row.get("group")), []).append(row)

    summaries: list[dict[str, Any]] = []
    for group_name, group_rows in grouped.items():
        ordered_rows = sorted(group_rows, key=lambda row: _safe_text(row.get("variant")))
        url_sets = [set(row.get("normalized_urls", [])) for row in ordered_rows]
        accepted_values = [int(row.get("accepted_jobs", 0) or 0) for row in ordered_rows]
        broken_values = [int(row.get("broken_url_count", 0) or 0) for row in ordered_rows]
        if url_sets:
            shared_urls = set.intersection(*url_sets) if len(url_sets) > 1 else set(url_sets[0])
            union_urls = set().union(*url_sets)
        else:
            shared_urls = set()
            union_urls = set()
        summaries.append(
            {
                "group": group_name,
                "variants": [row.get("variant", "") for row in ordered_rows],
                "titles": [row.get("title", "") for row in ordered_rows],
                "shared_url_count": len(shared_urls),
                "union_url_count": len(union_urls),
                "overlap_rate": round((len(shared_urls) / len(union_urls)) * 100, 1) if union_urls else 0.0,
                "accepted_gap": (max(accepted_values) - min(accepted_values)) if accepted_values else 0,
                "broken_gap": (max(broken_values) - min(broken_values)) if broken_values else 0,
            }
        )
    return sorted(summaries, key=lambda row: _safe_text(row.get("group")))


def _overall_summary(rows: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    total_urls = sum(int(row.get("url_count", 0) or 0) for row in rows)
    total_seen = sum(int(row.get("seen_urls", 0) or 0) for row in rows)
    total_accepted = sum(int(row.get("accepted_jobs", 0) or 0) for row in rows)
    total_broken = sum(int(row.get("broken_url_count", 0) or 0) for row in rows)
    total_blocked = sum(int(row.get("blocked_domain_drop_count", 0) or 0) for row in rows)
    total_weak_match = sum(int(row.get("weak_title_match_count", 0) or 0) for row in rows)
    variant_sensitive_groups = [
        group
        for group in groups
        if float(group.get("overlap_rate", 0.0) or 0.0) < 50.0
        or int(group.get("accepted_gap", 0) or 0) > 2
        or int(group.get("broken_gap", 0) or 0) > 1
    ]
    return {
        "case_count": len(rows),
        "group_count": len(groups),
        "total_urls": total_urls,
        "total_seen_urls": total_seen,
        "total_accepted_jobs": total_accepted,
        "overall_acceptance_rate": round((total_accepted / total_seen) * 100, 1) if total_seen else 0.0,
        "total_broken_urls": total_broken,
        "total_blocked_domain_drops": total_blocked,
        "total_weak_title_matches": total_weak_match,
        "variant_sensitive_group_count": len(variant_sensitive_groups),
        "variant_sensitive_groups": [group.get("group", "") for group in variant_sensitive_groups],
    }


def _render_markdown(
    rows: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    overall: dict[str, Any],
    *,
    preferred_locations: str,
    remote_only: str,
    search_strategy: str,
    source_layer_mode: str,
) -> str:
    lines = [
        "# Discovery Quality Benchmark",
        "",
        f"- Source layer mode: `{source_layer_mode}`",
        f"- Preferred locations: `{preferred_locations or '-'}`",
        f"- Remote only: `{remote_only}`",
        f"- Search strategy: `{search_strategy}`",
        f"- Benchmark cases: `{int(overall.get('case_count', 0) or 0)}` across `{int(overall.get('group_count', 0) or 0)}` title-variant groups",
        f"- Total discovered URLs: `{int(overall.get('total_urls', 0) or 0)}`",
        f"- Total accepted jobs: `{int(overall.get('total_accepted_jobs', 0) or 0)}`",
        f"- Overall acceptance rate: `{float(overall.get('overall_acceptance_rate', 0.0) or 0.0):.1f}%`",
        f"- Broken URLs during validation: `{int(overall.get('total_broken_urls', 0) or 0)}`",
        f"- Blocked-domain discovery drops: `{int(overall.get('total_blocked_domain_drops', 0) or 0)}`",
        f"- Weak URL title-match skips: `{int(overall.get('total_weak_title_matches', 0) or 0)}`",
        f"- Variant-sensitive groups: `{', '.join(overall.get('variant_sensitive_groups', []) or ['none'])}`",
        "",
        "| Group | Variant | Title | URLs | Accepted | Acceptance % | Broken | Blocked | Weak Title | Dupes | Domains |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['group']} | {row['variant']} | {row['title']} | "
            f"{row['url_count']} | {row['accepted_jobs']} | {row['acceptance_rate']:.1f} | "
            f"{row['broken_url_count']} | {row['blocked_domain_drop_count']} | "
            f"{row['weak_title_match_count']} | {row['duplicate_batch_skip_count']} | "
            f"{row['unique_domain_count']} |"
        )

    lines.extend(
        [
            "",
            "## Variant Group Comparison",
            "",
            "| Group | Variants | Shared URLs | Union URLs | Overlap % | Accepted Gap | Broken Gap |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for group in groups:
        lines.append(
            f"| {group['group']} | {', '.join(group['variants'])} | "
            f"{group['shared_url_count']} | {group['union_url_count']} | "
            f"{group['overlap_rate']:.1f} | {group['accepted_gap']} | {group['broken_gap']} |"
        )

    lines.append("")
    for row in rows:
        lines.append(f"## {row['title']}")
        lines.append(f"- Report dir: `{row['report_dir']}`")
        lines.append(f"- URL domains: {', '.join(row['url_domains']) if row['url_domains'] else '-'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a discovery quality benchmark across title variants.")
    parser.add_argument("--preferred-locations", default="Remote", help="Preferred locations override.")
    parser.add_argument("--remote-only", choices=("true", "false"), default="true", help="Remote-only setting.")
    parser.add_argument(
        "--search-strategy",
        choices=("balanced", "broad_recall"),
        default="broad_recall",
        help="Search strategy override.",
    )
    parser.add_argument(
        "--source-layer-mode",
        choices=("legacy", "shadow", "next_gen"),
        default="next_gen",
        help="Source layer mode for benchmark runs.",
    )
    parser.add_argument("--write-json", type=Path, help="Optional JSON output path.")
    parser.add_argument("--write-csv", type=Path, help="Optional CSV output path.")
    parser.add_argument("--write-markdown", type=Path, help="Optional markdown output path.")
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for case in DEFAULT_CASES:
        label = f"benchmark-{_slugify(case['title'])}-{args.source_layer_mode}"
        report_dir = _run_case(
            title=case["title"],
            label=label,
            preferred_locations=args.preferred_locations,
            remote_only=args.remote_only,
            search_strategy=args.search_strategy,
            source_layer_mode=args.source_layer_mode,
        )
        rows.append(_load_row(case, report_dir))

    groups = _summarize_groups(rows)
    overall = _overall_summary(rows, groups)
    payload = {
        "overall": overall,
        "groups": groups,
        "rows": rows,
    }
    markdown = _render_markdown(
        rows,
        groups,
        overall,
        preferred_locations=args.preferred_locations,
        remote_only=args.remote_only,
        search_strategy=args.search_strategy,
        source_layer_mode=args.source_layer_mode,
    )

    if args.write_json:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.write_markdown:
        args.write_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.write_markdown.write_text(markdown, encoding="utf-8")
    if args.write_csv:
        args.write_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.write_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "group",
                    "variant",
                    "title",
                    "url_count",
                    "seen_urls",
                    "accepted_jobs",
                    "acceptance_rate",
                    "broken_url_count",
                    "blocked_domain_drop_count",
                    "weak_title_match_count",
                    "duplicate_batch_skip_count",
                    "validation_error_count",
                    "unique_domain_count",
                    "report_dir",
                ],
            )
            writer.writeheader()
            writer.writerows(
                {
                    key: row[key]
                    for key in writer.fieldnames
                }
                for row in rows
            )

    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
