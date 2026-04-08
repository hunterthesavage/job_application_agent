#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = REPO_ROOT / "logs" / "discovery_debug"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    current_python = Path(sys.executable)
    target_python = VENV_PYTHON
    if current_python != target_python:
        os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services import pipeline_runtime as runtime
from services.settings import load_settings


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _slugify(value: str) -> str:
    text = _safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "discovery-debug"


def _load_json_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return raw


def _apply_cli_overrides(settings: dict[str, str], args: argparse.Namespace) -> dict[str, str]:
    effective = dict(settings)

    if args.target_titles is not None:
        effective["target_titles"] = args.target_titles
    if args.preferred_locations is not None:
        effective["preferred_locations"] = args.preferred_locations
    if args.remote_only is not None:
        effective["remote_only"] = args.remote_only
    if args.search_strategy is not None:
        effective["search_strategy"] = args.search_strategy
    if args.include_keywords is not None:
        effective["include_keywords"] = args.include_keywords
    if args.exclude_keywords is not None:
        effective["exclude_keywords"] = args.exclude_keywords
    if args.minimum_compensation is not None:
        effective["minimum_compensation"] = args.minimum_compensation
    if args.source_layer_mode is not None:
        effective["source_layer_mode"] = args.source_layer_mode

    return {key: _safe_text(value) for key, value in effective.items()}


def _build_label(args: argparse.Namespace, settings: dict[str, str]) -> str:
    if args.label:
        return args.label
    target_titles = _safe_text(settings.get("target_titles", ""))
    remote_only = _safe_text(settings.get("remote_only", "false")).lower() == "true"
    suffix = "remote" if remote_only else "local"
    return f"{target_titles or 'discovery'}-{suffix}"


@contextmanager
def _temporary_runtime_settings(
    effective_settings: dict[str, str],
    *,
    source_layer_mode: str,
) -> Iterator[None]:
    original_load_settings = runtime.load_settings
    original_get_source_layer_mode = runtime.get_source_layer_mode
    original_save_output_urls = runtime.discover_module.save_output_urls

    runtime.load_settings = lambda: dict(effective_settings)
    runtime.get_source_layer_mode = lambda: source_layer_mode
    runtime.discover_module.save_output_urls = lambda file_path, urls: None
    try:
        yield
    finally:
        runtime.load_settings = original_load_settings
        runtime.get_source_layer_mode = original_get_source_layer_mode
        runtime.discover_module.save_output_urls = original_save_output_urls


def _build_report_summary(
    result: dict[str, Any],
    *,
    label: str,
    source_layer_mode: str,
    use_ai_title_expansion: bool,
    report_dir: Path,
    validation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validation_result if isinstance(validation_result, dict) else {}
    return {
        "label": label,
        "source_layer_mode": source_layer_mode,
        "use_ai_title_expansion": use_ai_title_expansion,
        "status": result.get("status", ""),
        "url_count": int(result.get("url_count", 0) or 0),
        "provider_counts": result.get("providers", {}),
        "next_gen_seed_url_count": len(result.get("next_gen_seed_urls", []) or []),
        "next_gen_supported_seeds_scanned": int(result.get("next_gen_supported_seeds_scanned", 0) or 0),
        "next_gen_unsupported_seeds_skipped": int(result.get("next_gen_unsupported_seeds_skipped", 0) or 0),
        "drop_summary": result.get("drop_summary", {}),
        "accepted_jobs": int(validation.get("accepted_jobs", 0) or 0),
        "seen_urls": int(validation.get("seen_urls", 0) or 0),
        "validation_skipped_count": int(validation.get("skipped_count", 0) or 0),
        "validation_skipped_title_prefilter_count": int(validation.get("skipped_title_prefilter_count", 0) or 0),
        "validation_skipped_duplicate_batch_count": int(validation.get("skipped_duplicate_batch_count", 0) or 0),
        "validation_error_count": int(validation.get("error_count", 0) or 0),
        "validation_seeded_accepted_jobs": int(validation.get("seeded_accepted_jobs", 0) or 0),
        "validation_legacy_accepted_jobs": int(validation.get("legacy_accepted_jobs", 0) or 0),
        "validation_skip_summary": validation.get("skip_summary", {}),
        "validation_build_seconds": float(validation.get("build_seconds", 0.0) or 0.0),
        "validation_ingest_seconds": float(validation.get("ingest_seconds", 0.0) or 0.0),
        "report_dir": str(report_dir),
    }


def _write_report_files(
    report_dir: Path,
    *,
    effective_settings: dict[str, str],
    result: dict[str, Any] | None,
    summary: dict[str, Any],
    validation_result: dict[str, Any] | None = None,
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "effective_settings.json").write_text(
        json.dumps(effective_settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (report_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if result is None:
        return

    (report_dir / "output.txt").write_text(str(result.get("output", "") or ""), encoding="utf-8")
    (report_dir / "urls.txt").write_text(
        "\n".join(result.get("urls", []) or []) + ("\n" if result.get("urls") else ""),
        encoding="utf-8",
    )
    (report_dir / "queries.txt").write_text(
        "\n".join(result.get("queries", []) or []) + ("\n" if result.get("queries") else ""),
        encoding="utf-8",
    )
    (report_dir / "plan.txt").write_text(
        "\n".join(result.get("plan", []) or []) + ("\n" if result.get("plan") else ""),
        encoding="utf-8",
    )
    if validation_result is not None:
        (report_dir / "validation_output.txt").write_text(
            str(validation_result.get("output", "") or ""),
            encoding="utf-8",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local discovery with temporary settings overrides and save a debug report.",
    )
    parser.add_argument("--profile", type=Path, help="Optional JSON settings overlay.")
    parser.add_argument("--label", help="Optional label for the report folder.")
    parser.add_argument("--target-titles", help="Override target_titles.")
    parser.add_argument("--preferred-locations", help="Override preferred_locations.")
    parser.add_argument("--remote-only", choices=("true", "false"), help="Override remote_only.")
    parser.add_argument("--search-strategy", choices=("balanced", "broad_recall"), help="Override search_strategy.")
    parser.add_argument("--include-keywords", help="Override include_keywords.")
    parser.add_argument("--exclude-keywords", help="Override exclude_keywords.")
    parser.add_argument("--minimum-compensation", help="Override minimum_compensation.")
    parser.add_argument("--source-layer-mode", choices=("legacy", "shadow", "next_gen"), help="Override source_layer_mode.")
    parser.add_argument("--dry-run", action="store_true", help="Write the effective settings report without executing discovery.")
    parser.add_argument(
        "--ai-title-expansion",
        dest="use_ai_title_expansion",
        action="store_true",
        default=False,
        help="Enable AI title expansion during discovery.",
    )
    parser.add_argument(
        "--no-ai-title-expansion",
        dest="use_ai_title_expansion",
        action="store_false",
        help="Disable AI title expansion during discovery.",
    )
    parser.add_argument(
        "--validate-urls",
        action="store_true",
        help="Run validation on discovered URLs and persist quality metrics in the report summary.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    base_settings = load_settings()
    if args.profile:
        profile_data = _load_json_file(args.profile)
        base_settings.update({key: _safe_text(value) for key, value in profile_data.items()})

    effective_settings = _apply_cli_overrides(base_settings, args)
    source_layer_mode = _safe_text(
        args.source_layer_mode or effective_settings.get("source_layer_mode", "legacy")
    ).lower() or "legacy"

    label = _build_label(args, effective_settings)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = REPORTS_ROOT / f"{timestamp}_{_slugify(label)}"

    if args.dry_run:
        summary = {
            "label": label,
            "source_layer_mode": source_layer_mode,
            "use_ai_title_expansion": bool(args.use_ai_title_expansion),
            "status": "dry_run",
            "report_dir": str(report_dir),
        }
        _write_report_files(
            report_dir,
            effective_settings=effective_settings,
            result=None,
            summary=summary,
            validation_result=None,
        )
        print(f"Dry run complete. Report directory: {report_dir}")
        return 0

    with _temporary_runtime_settings(effective_settings, source_layer_mode=source_layer_mode):
        result = runtime.discover_job_links(
            use_ai_title_expansion=bool(args.use_ai_title_expansion)
        )
        validation_result: dict[str, Any] | None = None
        if args.validate_urls:
            validation_result = runtime._build_jobs_from_urls(
                result.get("urls", []) or [],
                source_name="Local Pipeline",
                source_detail="discovery_debug_validation",
                use_ai_scoring=False,
                seeded_job_urls=result.get("next_gen_seed_urls", []) or [],
            )

    summary = _build_report_summary(
        result,
        label=label,
        source_layer_mode=source_layer_mode,
        use_ai_title_expansion=bool(args.use_ai_title_expansion),
        report_dir=report_dir,
        validation_result=validation_result,
    )
    _write_report_files(
        report_dir,
        effective_settings=effective_settings,
        result=result,
        summary=summary,
        validation_result=validation_result,
    )

    print(f"Discovery debug run complete. Report directory: {report_dir}")
    print(
        "Summary: "
        f"status={summary['status']} "
        f"url_count={summary['url_count']} "
        f"next_gen_seed_url_count={summary['next_gen_seed_url_count']} "
        f"supported_seeds_scanned={summary['next_gen_supported_seeds_scanned']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
