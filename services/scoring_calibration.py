from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from services.ai_job_scoring import DEFAULT_MODEL, score_accepted_job
from services.job_qualifier import parse_preferred_locations, qualify_job
from services.location_matching import evaluate_location_filters


LABEL_RANKS = {"no": 0, "maybe": 1, "yes": 2}


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_expected_label(value: Any) -> str:
    text = safe_text(value).lower()
    if text in {"yes", "strong", "apply"}:
        return "yes"
    if text in {"maybe", "review", "hold"}:
        return "maybe"
    if text in {"no", "skip", "reject"}:
        return "no"
    return "maybe"


def qualifier_label_from_match(match: dict[str, Any]) -> str:
    qualification = match.get("qualification", {}) or {}
    score = int(qualification.get("score", 0) or 0)
    if not match.get("should_accept", False):
        return "no"
    if score >= 75:
        return "yes"
    return "maybe"


def ai_label_from_score_result(score_result: dict[str, Any]) -> str:
    fit_score = int(score_result.get("fit_score", 0) or 0)
    if fit_score >= 80:
        return "yes"
    if fit_score >= 60:
        return "maybe"
    return "no"


def label_distance(left: str, right: str) -> int:
    return abs(LABEL_RANKS[normalize_expected_label(left)] - LABEL_RANKS[normalize_expected_label(right)])


def load_calibration_cases(file_path: str | Path) -> list[dict[str, Any]]:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("Calibration JSON files must contain a top-level list.")
        return [case for case in payload if isinstance(case, dict)]

    cases: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            cases.append(parsed)
    return cases


def _case_settings(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_titles": safe_text(case.get("target_titles", "")),
        "preferred_locations": safe_text(case.get("preferred_locations", "")),
        "include_keywords": safe_text(case.get("include_keywords", "")),
        "exclude_keywords": safe_text(case.get("exclude_keywords", "")),
        "remote_only": str(case.get("remote_only", "false")).lower(),
    }


def _case_payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "company": safe_text(case.get("company", "")),
        "title": safe_text(case.get("title", "")),
        "location": safe_text(case.get("location", "")),
        "job_url": safe_text(case.get("job_posting_url", "")),
        "job_posting_url": safe_text(case.get("job_posting_url", "")),
        "description_text": safe_text(case.get("description_text", "")),
        "job_description": safe_text(case.get("description_text", "")),
        "page_text": safe_text(case.get("description_text", "")),
    }


def score_job_match(job: Any, settings: dict[str, Any]) -> dict[str, Any]:
    title = safe_text(getattr(job, "title", ""))
    company = safe_text(getattr(job, "company", ""))
    location = safe_text(getattr(job, "location", ""))
    compensation_raw = safe_text(getattr(job, "compensation_raw", ""))
    existing_rationale = safe_text(getattr(job, "match_rationale", ""))

    qualification_text = " ".join(
        [
            title,
            company,
            location,
            compensation_raw,
            existing_rationale,
        ]
    ).strip()

    qualification = qualify_job(
        job_title=title,
        company=company,
        location=location,
        job_text=qualification_text,
        settings=settings,
    )

    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    remote_only = safe_text(settings.get("remote_only", "true")).lower() == "true"

    location_filter_passed, location_filter_reason = evaluate_location_filters(
        job_location=location,
        preferred_locations=preferred_locations,
        remote_only=remote_only,
    )

    hard_reject = not location_filter_passed
    should_accept = bool(qualification.should_accept) and not hard_reject

    reason_parts = []
    if safe_text(qualification.rationale):
        reason_parts.append(safe_text(qualification.rationale))
    if safe_text(qualification.reject_reason):
        reason_parts.append(f"qualifier reject: {safe_text(qualification.reject_reason)}")
    if hard_reject and location_filter_reason:
        reason_parts.append(f"hard reject: {location_filter_reason}")

    return {
        "score": int(qualification.score),
        "should_accept": should_accept,
        "reason_text": "; ".join([part for part in reason_parts if part]),
        "qualification": qualification.to_dict(),
        "hard_reject": hard_reject,
        "location_filter_passed": location_filter_passed,
        "location_filter_reason": location_filter_reason,
    }


def evaluate_calibration_cases(
    cases: list[dict[str, Any]],
    *,
    resume_profile_text: str = "",
    use_ai_scoring: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    qualifier_exact = 0
    qualifier_adjacent = 0
    ai_exact = 0
    ai_adjacent = 0
    ai_skipped = 0

    for index, case in enumerate(cases, start=1):
        expected_label = normalize_expected_label(case.get("expected_label", "maybe"))
        settings = _case_settings(case)
        payload = _case_payload(case)
        job = SimpleNamespace(
            title=payload["title"],
            company=payload["company"],
            location=payload["location"],
            compensation_raw=safe_text(case.get("compensation_raw", "")),
            match_rationale="",
        )

        match = score_job_match(job, settings)
        qualifier_label = qualifier_label_from_match(match)
        qualifier_distance = label_distance(expected_label, qualifier_label)
        if qualifier_distance == 0:
            qualifier_exact += 1
        elif qualifier_distance == 1:
            qualifier_adjacent += 1

        ai_result: dict[str, Any] | None = None
        ai_label = ""
        ai_distance: int | None = None
        if use_ai_scoring:
            ai_result = score_accepted_job(payload, resume_profile_text, model=model)
            ai_status = safe_text(ai_result.get("status", "")).lower()
            if ai_status == "scored":
                ai_label = ai_label_from_score_result(ai_result)
                ai_distance = label_distance(expected_label, ai_label)
                if ai_distance == 0:
                    ai_exact += 1
                elif ai_distance == 1:
                    ai_adjacent += 1
            else:
                ai_skipped += 1
        else:
            ai_skipped += 1

        results.append(
            {
                "id": safe_text(case.get("id", "")) or f"case_{index}",
                "expected_label": expected_label,
                "title": payload["title"],
                "company": payload["company"],
                "location": payload["location"],
                "notes": safe_text(case.get("notes", "")),
                "qualifier_score": int(match.get("score", 0) or 0),
                "qualifier_label": qualifier_label,
                "qualifier_distance": qualifier_distance,
                "qualifier_should_accept": bool(match.get("should_accept", False)),
                "qualifier_reason": safe_text(match.get("reason_text", "")),
                "qualifier_reject_reason": safe_text((match.get("qualification", {}) or {}).get("reject_reason", "")),
                "ai_status": safe_text((ai_result or {}).get("status", "")),
                "ai_fit_score": int((ai_result or {}).get("fit_score", 0) or 0),
                "ai_label": ai_label,
                "ai_distance": ai_distance,
                "ai_summary": safe_text((ai_result or {}).get("match_summary", "")),
            }
        )

    total = len(results)
    qualifier_far_misses = sum(1 for item in results if item["qualifier_distance"] >= 2)
    ai_far_misses = sum(1 for item in results if item["ai_distance"] is not None and item["ai_distance"] >= 2)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "total_cases": total,
        "use_ai_scoring": use_ai_scoring,
        "model": model if use_ai_scoring else "",
        "resume_profile_present": bool(resume_profile_text.strip()),
        "qualifier_summary": {
            "exact_matches": qualifier_exact,
            "adjacent_matches": qualifier_adjacent,
            "far_misses": qualifier_far_misses,
        },
        "ai_summary": {
            "exact_matches": ai_exact,
            "adjacent_matches": ai_adjacent,
            "far_misses": ai_far_misses,
            "skipped_or_unscored": ai_skipped,
        },
        "results": results,
    }


def render_calibration_report(report: dict[str, Any]) -> str:
    qualifier = report.get("qualifier_summary", {}) or {}
    ai = report.get("ai_summary", {}) or {}
    results = report.get("results", []) or []
    use_ai_scoring = bool(report.get("use_ai_scoring", False))

    lines = [
        "# Scoring Calibration Report",
        "",
        f"- Generated: {safe_text(report.get('generated_at', ''))}",
        f"- Cases: {int(report.get('total_cases', 0) or 0)}",
        f"- AI scoring enabled: {'yes' if use_ai_scoring else 'no'}",
    ]
    if use_ai_scoring:
        lines.append(f"- Model: {safe_text(report.get('model', ''))}")
        lines.append(
            f"- Resume profile present: {'yes' if report.get('resume_profile_present') else 'no'}"
        )

    lines.extend(
        [
            "",
            "## Qualifier Summary",
            "",
            f"- Exact matches: {int(qualifier.get('exact_matches', 0) or 0)}",
            f"- Adjacent matches: {int(qualifier.get('adjacent_matches', 0) or 0)}",
            f"- Far misses: {int(qualifier.get('far_misses', 0) or 0)}",
        ]
    )

    if use_ai_scoring:
        lines.extend(
            [
                "",
                "## AI Summary",
                "",
                f"- Exact matches: {int(ai.get('exact_matches', 0) or 0)}",
                f"- Adjacent matches: {int(ai.get('adjacent_matches', 0) or 0)}",
                f"- Far misses: {int(ai.get('far_misses', 0) or 0)}",
                f"- Skipped or unscored: {int(ai.get('skipped_or_unscored', 0) or 0)}",
            ]
        )

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Expected | Qualifier | AI | Title |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for item in results:
        ai_label = safe_text(item.get("ai_label", "")) or safe_text(item.get("ai_status", "")) or "-"
        lines.append(
            f"| {safe_text(item.get('id', ''))} | {safe_text(item.get('expected_label', ''))} | "
            f"{safe_text(item.get('qualifier_label', ''))} ({int(item.get('qualifier_score', 0) or 0)}) | "
            f"{ai_label} | {safe_text(item.get('title', ''))} |"
        )

    far_misses = [
        item for item in results
        if item.get("qualifier_distance", 0) >= 2
        or (item.get("ai_distance") is not None and int(item.get("ai_distance", 0) or 0) >= 2)
    ]
    if far_misses:
        lines.extend(["", "## Far Misses", ""])
        for item in far_misses:
            lines.append(
                f"- `{safe_text(item.get('id', ''))}` expected `{safe_text(item.get('expected_label', ''))}`, "
                f"qualifier `{safe_text(item.get('qualifier_label', ''))}`"
                + (
                    f", AI `{safe_text(item.get('ai_label', ''))}`"
                    if safe_text(item.get("ai_label", ""))
                    else ""
                )
                + f" :: {safe_text(item.get('title', ''))}"
            )

    return "\n".join(lines).strip() + "\n"
