#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_SCRIPT = REPO_ROOT / "scripts" / "run_local_discovery_debug.py"
COMPARE_SCRIPT = REPO_ROOT / "scripts" / "compare_discovery_debug_reports.py"
BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "run_discovery_quality_benchmark.py"
COMPARE_BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "compare_discovery_quality_benchmarks.py"
PROFILES_ROOT = REPO_ROOT / "scripts" / "debug_profiles"
SUITES_ROOT = REPO_ROOT / "logs" / "discovery_debug_suites"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    current_python = Path(sys.executable)
    target_python = VENV_PYTHON
    if current_python != target_python:
        os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])


def _default_profiles() -> list[Path]:
    return [
        PROFILES_ROOT / "vp_it_remote_next_gen.json",
        PROFILES_ROOT / "vice_president_information_technology_remote_next_gen.json",
        PROFILES_ROOT / "vp_infrastructure_remote_next_gen.json",
    ]


def _report_dir_from_stdout(stdout_text: str) -> str:
    match = re.search(r"Report directory:\s*(.+)", stdout_text)
    if not match:
        raise RuntimeError(f"Unable to find report directory in output:\n{stdout_text}")
    return match.group(1).strip()


def _run_profile(profile_path: Path, *, dry_run: bool) -> tuple[str, str]:
    label = profile_path.stem
    command = [
        str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)),
        str(DEBUG_SCRIPT),
        "--profile",
        str(profile_path),
        "--label",
        label,
        "--no-ai-title-expansion",
    ]
    if dry_run:
        command.append("--dry-run")

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return label, _report_dir_from_stdout(completed.stdout)


def _previous_suite_with_benchmark(current_suite_dir: Path) -> Path | None:
    if not SUITES_ROOT.exists():
        return None
    candidates = sorted(
        (
            path
            for path in SUITES_ROOT.iterdir()
            if path.is_dir()
            and path != current_suite_dir
            and (path / "quality_benchmark.json").exists()
        ),
        key=lambda path: path.name,
    )
    if not candidates:
        return None
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a discovery debug profile suite and compare the outputs.")
    parser.add_argument("--profile", action="append", default=[], help="Specific profile path to include.")
    parser.add_argument("--dry-run", action="store_true", help="Run the suite in dry-run mode.")
    args = parser.parse_args()

    profiles = [Path(path).resolve() for path in args.profile] if args.profile else _default_profiles()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suite_dir = SUITES_ROOT / f"{timestamp}_discovery_debug_suite"
    suite_dir.mkdir(parents=True, exist_ok=True)

    report_dirs: list[str] = []
    labels: list[str] = []
    for profile in profiles:
        label, report_dir = _run_profile(profile, dry_run=bool(args.dry_run))
        labels.append(label)
        report_dirs.append(report_dir)

    compare_command = [
        str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)),
        str(COMPARE_SCRIPT),
        *[arg for report_dir in report_dirs for arg in ("--report-dir", report_dir)],
        "--write-markdown",
        str(suite_dir / "comparison.md"),
    ]
    completed = subprocess.run(
        compare_command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    benchmark_command = [
        str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)),
        str(BENCHMARK_SCRIPT),
        "--source-layer-mode",
        "next_gen",
        "--write-json",
        str(suite_dir / "quality_benchmark.json"),
        "--write-csv",
        str(suite_dir / "quality_benchmark.csv"),
        "--write-markdown",
        str(suite_dir / "quality_benchmark.md"),
    ]
    benchmark_completed = subprocess.run(
        benchmark_command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    previous_benchmark_suite = _previous_suite_with_benchmark(suite_dir)
    benchmark_comparison_path = ""
    benchmark_comparison_stdout = ""
    if previous_benchmark_suite is not None:
        benchmark_comparison_path = str(suite_dir / "quality_benchmark_comparison.md")
        compare_benchmark_command = [
            str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)),
            str(COMPARE_BENCHMARK_SCRIPT),
            "--baseline-json",
            str(previous_benchmark_suite / "quality_benchmark.json"),
            "--current-json",
            str(suite_dir / "quality_benchmark.json"),
            "--write-markdown",
            benchmark_comparison_path,
        ]
        benchmark_compare_completed = subprocess.run(
            compare_benchmark_command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        benchmark_comparison_stdout = benchmark_compare_completed.stdout

    metadata = {
        "labels": labels,
        "profiles": [str(path) for path in profiles],
        "report_dirs": report_dirs,
        "dry_run": bool(args.dry_run),
        "comparison_markdown": str(suite_dir / "comparison.md"),
        "quality_benchmark_json": str(suite_dir / "quality_benchmark.json"),
        "quality_benchmark_csv": str(suite_dir / "quality_benchmark.csv"),
        "quality_benchmark_markdown": str(suite_dir / "quality_benchmark.md"),
        "previous_quality_benchmark_suite": str(previous_benchmark_suite) if previous_benchmark_suite is not None else "",
        "quality_benchmark_comparison_markdown": benchmark_comparison_path,
    }
    (suite_dir / "suite.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (suite_dir / "comparison_stdout.md").write_text(completed.stdout, encoding="utf-8")
    (suite_dir / "quality_benchmark_stdout.md").write_text(benchmark_completed.stdout, encoding="utf-8")
    if benchmark_comparison_stdout:
        (suite_dir / "quality_benchmark_comparison_stdout.md").write_text(benchmark_comparison_stdout, encoding="utf-8")

    print(f"Discovery debug suite complete. Suite directory: {suite_dir}")
    print(f"Comparison report: {suite_dir / 'comparison.md'}")
    print(f"Quality benchmark report: {suite_dir / 'quality_benchmark.md'}")
    if benchmark_comparison_path:
        print(f"Quality benchmark comparison: {benchmark_comparison_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
