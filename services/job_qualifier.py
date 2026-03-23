from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(value: str) -> str:
    return " ".join(
        safe_text(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .split()
    )


def parse_csv_text(value: str) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def parse_preferred_locations(value: str) -> list[str]:
    text = safe_text(value)
    if not text:
        return []

    if "\n" in text:
        return [part.strip() for part in text.splitlines() if part.strip()]

    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]

    return [text] if text else []


@dataclass
class QualificationResult:
    score: int
    fit_tier: str
    should_accept: bool
    confidence: str
    reject_reason: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _title_overlap_score(job_title: str, target_titles: list[str]) -> tuple[int, str]:
    normalized_job = normalize_text(job_title)
    if not normalized_job:
        return 0, "missing job title"

    if not target_titles:
        return 20, "no target titles provided"

    best = 0
    best_reason = "no strong title overlap"

    for title in target_titles:
        normalized_target = normalize_text(title)
        if not normalized_target:
            continue

        if normalized_target in normalized_job:
            return 45, f"title contains target '{title}'"

        job_tokens = set(normalized_job.split())
        target_tokens = set(normalized_target.split())
        overlap = len(job_tokens.intersection(target_tokens))

        if overlap > best:
            best = overlap
            best_reason = f"title token overlap with '{title}'"

    if best >= 2:
        return 30, best_reason
    if best == 1:
        return 15, best_reason
    return 0, best_reason


def _location_score(job_location: str, preferred_locations: list[str], remote_only: bool) -> tuple[int, str]:
    normalized_location = normalize_text(job_location)

    if remote_only:
        if "remote" in normalized_location:
            return 25, "remote-only preference matched"
        if not normalized_location:
            return 5, "location missing"
        return -20, "not remote"

    if not preferred_locations:
        if "remote" in normalized_location:
            return 15, "remote accepted"
        return 10, "no preferred locations provided"

    for pref in preferred_locations:
        normalized_pref = normalize_text(pref)
        if normalized_pref and normalized_pref in normalized_location:
            return 25, f"location matched '{pref}'"

    if "remote" in normalized_location:
        return 12, "remote accepted as fallback"

    return -10, "location mismatch"


def _keyword_score(searchable_text: str, include_keywords: list[str], exclude_keywords: list[str]) -> tuple[int, list[str], str]:
    normalized = normalize_text(searchable_text)
    score = 0
    reasons: list[str] = []
    reject_reason = ""

    matched_includes = []
    for keyword in include_keywords:
        norm = normalize_text(keyword)
        if norm and norm in normalized:
            matched_includes.append(keyword)

    matched_excludes = []
    for keyword in exclude_keywords:
        norm = normalize_text(keyword)
        if norm and norm in normalized:
            matched_excludes.append(keyword)

    if matched_includes:
        score += min(20, 8 + (len(matched_includes) * 4))
        reasons.append(f"matched include keywords: {', '.join(matched_includes[:4])}")

    if matched_excludes:
        score -= 35
        reject_reason = f"matched excluded keywords: {', '.join(matched_excludes[:4])}"
        reasons.append(reject_reason)

    return score, reasons, reject_reason


def qualify_job(
    job_title: str,
    company: str,
    location: str,
    job_text: str,
    settings: dict[str, Any],
) -> QualificationResult:
    target_titles = parse_csv_text(settings.get("target_titles", ""))
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    include_keywords = parse_csv_text(settings.get("include_keywords", ""))
    exclude_keywords = parse_csv_text(settings.get("exclude_keywords", ""))
    remote_only = safe_text(settings.get("remote_only", "false")).lower() == "true"

    searchable = " ".join([job_title, company, location, job_text])

    title_score, title_reason = _title_overlap_score(job_title, target_titles)
    location_score, location_reason = _location_score(location, preferred_locations, remote_only)
    keyword_score, keyword_reasons, keyword_reject_reason = _keyword_score(
        searchable_text=searchable,
        include_keywords=include_keywords,
        exclude_keywords=exclude_keywords,
    )

    total = max(0, min(100, title_score + location_score + keyword_score))

    reject_reason = keyword_reject_reason
    if not reject_reason and title_score == 0 and target_titles:
        reject_reason = "title mismatch"
    if not reject_reason and location_score < 0:
        reject_reason = location_reason

    if total >= 70:
        fit_tier = "Strong"
        confidence = "High"
    elif total >= 50:
        fit_tier = "Review"
        confidence = "Medium"
    else:
        fit_tier = "Low"
        confidence = "Low"

    should_accept = total >= 50 and not reject_reason

    rationale_parts = [title_reason, location_reason]
    rationale_parts.extend(keyword_reasons)

    return QualificationResult(
        score=total,
        fit_tier=fit_tier,
        should_accept=should_accept,
        confidence=confidence,
        reject_reason=reject_reason,
        rationale="; ".join([part for part in rationale_parts if part]),
    )
