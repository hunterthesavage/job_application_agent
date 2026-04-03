from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from services.location_matching import location_matches_preference, parse_location
from services.search_plan import build_search_title_variants, parse_title_entries, resolve_include_remote


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
        .replace("&", " and ")
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


def _tokens(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if token}


def _contains_any(normalized_text: str, phrases: list[str]) -> bool:
    return any(normalize_text(phrase) in normalized_text for phrase in phrases if normalize_text(phrase))


TECH_FUNCTION_TERMS = [
    "technology",
    "information technology",
    "it",
    "digital",
    "platform",
    "infrastructure",
    "enterprise systems",
    "enterprise applications",
    "architecture",
    "engineering",
    "security",
    "cybersecurity",
    "data",
    "ai",
    "artificial intelligence",
    "machine learning",
    "cloud",
    "applications",
    "systems",
    "technical",
]

ADJACENT_TECH_TERMS = [
    "technology and data",
    "technology & data",
    "technology and engineering",
    "technology & engineering",
    "technology and architecture",
    "technology & architecture",
    "enterprise technology",
    "business technology",
    "platform engineering",
]

WRONG_FUNCTION_TERMS = [
    "sales",
    "marketing",
    "revenue",
    "customer success",
    "finance",
    "financial",
    "legal",
    "hr",
    "human resources",
    "people",
    "talent",
    "operations",
    "clinical",
    "medicare",
    "aca marketplace",
    "commercial",
    "partnerships",
    "growth",
]


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


def _title_overlap_score(job_title: str, target_titles: list[str]) -> tuple[int, list[str]]:
    normalized_job = normalize_text(job_title)
    reasons: list[str] = []

    if not normalized_job:
        return 0, ["missing job title"]

    if not target_titles:
        return 20, ["no target titles provided"]

    job_tokens = _tokens(job_title)
    best_score = 0
    best_reason = "no strong title overlap"

    for target in target_titles:
        normalized_target = normalize_text(target)
        if not normalized_target:
            continue

        target_tokens = _tokens(target)

        if normalized_target in normalized_job:
            return 55, [f"title contains target '{target}'"]

        overlap = len(job_tokens.intersection(target_tokens))
        if overlap >= 3:
            score = 42
            reason = f"strong token overlap with '{target}'"
        elif overlap == 2:
            score = 32
            reason = f"good token overlap with '{target}'"
        elif overlap == 1:
            score = 16
            reason = f"light token overlap with '{target}'"
        else:
            score = 0
            reason = f"no token overlap with '{target}'"

        if score > best_score:
            best_score = score
            best_reason = reason

    reasons.append(best_reason)
    return best_score, reasons


def _function_lane_score(job_title: str, target_titles: list[str]) -> tuple[int, list[str], str]:
    normalized_title = normalize_text(job_title)
    reasons: list[str] = []
    reject_reason = ""

    target_text = " ".join(target_titles)
    normalized_target_text = normalize_text(target_text)

    target_has_tech_signal = _contains_any(normalized_target_text, TECH_FUNCTION_TERMS)
    job_has_tech_signal = _contains_any(normalized_title, TECH_FUNCTION_TERMS)
    job_has_adjacent_tech_signal = _contains_any(normalized_title, ADJACENT_TECH_TERMS)
    job_has_wrong_function = _contains_any(normalized_title, WRONG_FUNCTION_TERMS)

    if target_has_tech_signal:
        if job_has_wrong_function and not job_has_tech_signal and not job_has_adjacent_tech_signal:
            reject_reason = "wrong function"
            reasons.append("title appears to be in a different executive function")
            return -35, reasons, reject_reason

        if job_has_tech_signal:
            reasons.append("strong technology-lane signal")
            return 25, reasons, reject_reason

        if job_has_adjacent_tech_signal:
            reasons.append("adjacent technology-lane signal")
            return 18, reasons, reject_reason

        reasons.append("limited technology-lane signal")
        return -10, reasons, reject_reason

    if job_has_wrong_function:
        reasons.append("different executive function detected")
        return -15, reasons, ""

    return 0, reasons, ""


def _location_score(
    job_location: str,
    preferred_locations: list[str],
    remote_only: bool,
    include_remote: bool,
) -> tuple[int, list[str], str]:
    reasons: list[str] = []
    reject_reason = ""
    parsed_location = parse_location(job_location)

    if remote_only:
        if parsed_location.is_remote or parsed_location.is_us_scope_remote:
            reasons.append("remote-only preference matched")
            return 22, reasons, reject_reason
        if parsed_location.is_blank:
            reasons.append("location missing")
            return 5, reasons, reject_reason
        reject_reason = "not remote"
        reasons.append("role is not remote")
        return -20, reasons, reject_reason

    if not preferred_locations:
        if parsed_location.is_remote or parsed_location.is_us_scope_remote:
            if include_remote:
                reasons.append("remote accepted")
                return 12, reasons, reject_reason
            reject_reason = "location mismatch"
            reasons.append("location mismatch")
            return -8, reasons, reject_reason
        reasons.append("no preferred locations provided")
        return 8, reasons, reject_reason

    matched, reason = location_matches_preference(job_location, preferred_locations)
    if matched:
        reasons.append(reason)
        return 20, reasons, reject_reason

    if include_remote and (parsed_location.is_remote or parsed_location.is_us_scope_remote):
        reasons.append("remote accepted as fallback")
        return 10, reasons, reject_reason

    reject_reason = "location mismatch"
    reasons.append("location mismatch")
    return -8, reasons, reject_reason


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
        score += min(18, 8 + (len(matched_includes) * 3))
        reasons.append(f"matched include keywords: {', '.join(matched_includes[:4])}")

    if matched_excludes:
        score -= 40
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
    target_titles = parse_title_entries(settings.get("target_titles", ""))
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    include_keywords = parse_csv_text(settings.get("include_keywords", ""))
    exclude_keywords = parse_csv_text(settings.get("exclude_keywords", ""))
    remote_only = safe_text(settings.get("remote_only", "false")).lower() == "true"
    include_remote = resolve_include_remote(settings)
    title_variants = build_search_title_variants(target_titles, max_variants=6) if target_titles else []
    scoring_titles = title_variants or target_titles

    searchable = " ".join([job_title, company, location, job_text])

    title_score, title_reasons = _title_overlap_score(job_title, scoring_titles)
    function_score, function_reasons, function_reject_reason = _function_lane_score(job_title, scoring_titles)
    location_score, location_reasons, location_reject_reason = _location_score(
        location,
        preferred_locations,
        remote_only,
        include_remote,
    )
    keyword_score, keyword_reasons, keyword_reject_reason = _keyword_score(
        searchable_text=searchable,
        include_keywords=include_keywords,
        exclude_keywords=exclude_keywords,
    )

    total = max(0, min(100, title_score + function_score + location_score + keyword_score))

    reject_reason = ""
    for candidate in [keyword_reject_reason, function_reject_reason, location_reject_reason]:
        if safe_text(candidate):
            reject_reason = safe_text(candidate)
            break

    if not reject_reason and title_score == 0 and target_titles:
        reject_reason = "title mismatch"

    if total >= 75:
        fit_tier = "Strong"
        confidence = "High"
    elif total >= 50:
        fit_tier = "Review"
        confidence = "Medium"
    else:
        fit_tier = "Low"
        confidence = "Low"

    should_accept = total >= 50 and not reject_reason

    rationale_parts = []
    rationale_parts.extend(title_reasons)
    rationale_parts.extend(function_reasons)
    rationale_parts.extend(location_reasons)
    rationale_parts.extend(keyword_reasons)

    return QualificationResult(
        score=total,
        fit_tier=fit_tier,
        should_accept=should_accept,
        confidence=confidence,
        reject_reason=reject_reason,
        rationale="; ".join([part for part in rationale_parts if part]),
    )
