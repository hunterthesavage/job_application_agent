from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from config import JOB_URLS_FILE, MANUAL_URLS_FILE
from services.ai_job_scoring import (
    apply_score_to_job_payload,
    load_resume_profile_text,
    score_accepted_job,
)
from services.ingestion import ingest_job_records
from services.location_matching import (
    evaluate_location_filters,
    location_matches_preference,
    parse_location,
)
from services.matching_profiles import expand_title_terms
from services.settings import load_settings
from services.source_trust import enrich_job_payload
from services.job_qualifier import qualify_job
from src import discover_job_urls as discover_module
from src.validate_job_url import create_job_record


AUTO_ACCEPT_SCORE = 45
MAX_URLS_PER_RUN = 25  # temporary fast-test cap; set to 0 for unlimited


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def normalize_text(value: str) -> str:
    return " ".join(
        safe_text(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .split()
    )


def parse_csv_setting(value: Any) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


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

    text = re.sub(r"\s+", " ", text).strip()
    return [text] if text else []


def tokenize(value: str) -> list[str]:
    return [token for token in normalize_text(value).split() if token]


def load_job_urls_from_file(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        return []

    urls: list[str] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    return urls


def parse_manual_urls(text_value: str) -> list[str]:
    urls: list[str] = []
    for line in str(text_value).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def token_overlap_score(source_text: str, target_text: str) -> float:
    source_tokens = set(tokenize(source_text))
    target_tokens = set(tokenize(target_text))

    if not source_tokens or not target_tokens:
        return 0.0

    overlap = source_tokens.intersection(target_tokens)
    if not overlap:
        return 0.0

    return len(overlap) / max(1, len(source_tokens))


def phrase_match_bonus(source_text: str, candidate_text: str) -> float:
    source = normalize_text(source_text)
    candidate = normalize_text(candidate_text)

    if not source or not candidate:
        return 0.0

    if source in candidate:
        return 1.0

    return 0.0


def is_probable_job_url(job_url: str) -> tuple[bool, str]:
    value = safe_text(job_url)
    if not value:
        return False, "blank_url"

    lowered = value.lower()
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    blocked_substrings = [
        "?error=",
        "?keyword=",
        "/search",
        "/jobs/search",
        "/about-us/",
        "/about/",
        "/leadership",
        "/executive-team",
        "/executive_team",
        "/team/",
        "/our-team",
        "/people/",
        "/our-people",
        "/company/",
        "/companies/",
        "/careers/",
    ]
    for marker in blocked_substrings:
        if marker in lowered:
            return False, f"blocked_pattern:{marker}"

    blocked_path_exact_or_prefixes = [
        "/leadership",
        "/team",
        "/people",
        "/about-us",
        "/about",
        "/company",
        "/companies",
        "/executives",
        "/our-team",
        "/our-people",
    ]
    for marker in blocked_path_exact_or_prefixes:
        if path == marker or path.startswith(marker + "/"):
            return False, f"blocked_path:{marker}"

    # Block obvious search/result shells and query-driven listing pages
    if any(token in query for token in ["keyword=", "location=", "search=", "query="]):
        return False, "blocked_query_listing"

    # Lever
    if "jobs.lever.co" in host:
        if "jobgether" in lowered:
            return False, "blocked_jobgether_wrapper"
        return (len(path_parts) >= 2, "lever_detail" if len(path_parts) >= 2 else "lever_board_root")

    # Greenhouse
    if "job-boards.greenhouse.io" in host or "boards.greenhouse.io" in host:
        if "jobs" in path_parts and len(path_parts) >= 2:
            return True, "greenhouse_detail"
        return False, "greenhouse_board_root"

    # Ashby
    if "jobs.ashbyhq.com" in host:
        return (len(path_parts) >= 2, "ashby_detail" if len(path_parts) >= 2 else "ashby_board_root")

    # SmartRecruiters
    if "jobs.smartrecruiters.com" in host:
        return (len(path_parts) >= 2, "smartrecruiters_detail" if len(path_parts) >= 2 else "smartrecruiters_root")

    # Workday: be stricter, must clearly be a /job/ detail page
    if "myworkdayjobs.com" in host:
        if "/job/" in path:
            return True, "workday_detail"
        return False, "workday_root"

    # For non-ATS URLs from search, reject common corporate/info pages early
    generic_non_job_hosts = [
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "x.com",
        "twitter.com",
        "youtube.com",
        "wikipedia.org",
    ]
    if any(bad_host in host for bad_host in generic_non_job_hosts):
        return False, "blocked_generic_host"

    # Soft allow fallback only when URL shape looks posting-like
    jobish_path_markers = [
        "/job/",
        "/jobs/",
        "/careers/job",
        "/open-positions/",
        "/positions/",
        "/vacancies/",
        "/opportunities/",
        "/role/",
        "/roles/",
    ]
    if any(marker in path for marker in jobish_path_markers):
        return True, "generic_jobish_path"

    return False, "unclassified_non_job"


def should_force_accept_without_location(job: Any, settings: dict[str, Any]) -> bool:
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    if preferred_locations:
        return False

    target_titles = parse_csv_setting(settings.get("target_titles", ""))
    expanded_titles = expand_title_terms(target_titles) if target_titles else []

    title = safe_text(getattr(job, "title", "")).lower()
    if not title or not expanded_titles:
        return False

    return any(term.lower() in title for term in expanded_titles)


def title_match_score(job_title: str, target_titles: list[str]) -> tuple[int, list[str]]:
    if not target_titles:
        return 25, ["no target title set"]

    best_score = 0
    best_reason = "no meaningful title match"

    for target in target_titles:
        phrase_bonus = phrase_match_bonus(target, job_title)
        overlap = token_overlap_score(target, job_title)

        score = int((phrase_bonus * 25) + (overlap * 20))

        if score > best_score:
            best_score = score
            best_reason = f"title matched '{target}'"

    return best_score, [best_reason]


def location_match_score(
    job_location: str,
    preferred_locations: list[str],
    remote_only: bool,
) -> tuple[int, list[str]]:
    parsed_job = parse_location(job_location)

    if remote_only:
        passed, reason = evaluate_location_filters(
            job_location=job_location,
            preferred_locations=preferred_locations,
            remote_only=True,
        )
        if passed:
            if parsed_job.is_remote:
                return 20, ["remote-only location matched remote role"]
            if parsed_job.is_us_scope_remote:
                return 18, ["remote-only location matched us-scope role"]
            return 15, [reason]
        return 0, [reason]

    if parsed_job.is_remote:
        return 20, ["matched remote location"]

    if parsed_job.is_us_scope_remote:
        return 18, ["matched us-scope location"]

    if not preferred_locations:
        if parsed_job.is_blank:
            return 0, ["blank job location"]
        return 20, ["no preferred location set"]

    matched, reason = location_matches_preference(job_location, preferred_locations)
    if matched:
        return 20, [reason]

    return 0, ["settings_location_gate"]


def include_keywords_score(searchable_text: str, include_keywords: list[str]) -> tuple[int, list[str]]:
    if not include_keywords:
        return 0, []

    matched = []
    searchable = normalize_text(searchable_text)

    for keyword in include_keywords:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword and normalized_keyword in searchable:
            matched.append(keyword)

    if not matched:
        return 0, [f"missing include keywords: {', '.join(include_keywords[:5])}"]

    score = min(20, 8 + (len(matched) * 4))
    return score, [f"matched include keywords: {', '.join(matched[:5])}"]


def exclude_keywords_penalty(searchable_text: str, exclude_keywords: list[str]) -> tuple[int, list[str]]:
    if not exclude_keywords:
        return 0, []

    matched = []
    searchable = normalize_text(searchable_text)

    for keyword in exclude_keywords:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword and normalized_keyword in searchable:
            matched.append(keyword)

    if not matched:
        return 0, []

    return -50, [f"matched excluded keywords: {', '.join(matched[:5])}"]


def remote_preference_score(job_location: str, remote_only: bool) -> tuple[int, list[str]]:
    parsed_job = parse_location(job_location)

    if not remote_only:
        return 0, []

    if parsed_job.is_remote:
        return 10, ["remote preference matched"]

    if parsed_job.is_us_scope_remote:
        return 8, ["remote preference matched via us-scope location"]

    return -25, ["role is not marked remote"]


def score_job_match(job, settings: dict[str, str]) -> dict[str, Any]:
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
        "breakdown": {
            "qualification_score": int(qualification.score),
        },
        "hard_reject": hard_reject,
        "location_filter_passed": location_filter_passed,
        "location_filter_reason": location_filter_reason,
        "qualification": qualification.to_dict(),
    }



def _batch_dedupe_key(payload: dict[str, Any]) -> str:
    duplicate_key = safe_text(payload.get("duplicate_key", ""))
    if duplicate_key:
        return f"dup:{normalize_text(duplicate_key)}"

    job_posting_url = safe_text(payload.get("job_posting_url", ""))
    if job_posting_url:
        return f"url:{job_posting_url.strip().lower()}"

    company = normalize_text(payload.get("company", ""))
    title = normalize_text(payload.get("title", ""))
    location = normalize_text(payload.get("location", ""))

    fallback = "|".join([part for part in [company, title, location] if part])
    return f"fallback:{fallback}" if fallback else ""


def _trust_score(value: str) -> int:
    trust = safe_text(value)
    order = {
        "ATS Confirmed": 4,
        "Career Site Confirmed": 3,
        "Web Discovered": 2,
        "Third-Party Listing": 1,
        "Unknown": 0,
        "": 0,
    }
    return order.get(trust, 0)


def _payload_quality_score(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    trust = _trust_score(payload.get("source_trust", ""))
    source_detail_len = len(safe_text(payload.get("source_detail", "")))
    url_len = len(safe_text(payload.get("job_posting_url", "")))
    title_len = len(safe_text(payload.get("title", "")))
    return (trust, source_detail_len, url_len, title_len)


def _prefer_payload(existing_payload: dict[str, Any], candidate_payload: dict[str, Any]) -> dict[str, Any]:
    if _payload_quality_score(candidate_payload) > _payload_quality_score(existing_payload):
        return candidate_payload
    return existing_payload


def _extract_url_title_hint(job_url: str) -> str:
    value = safe_text(job_url)
    if not value:
        return ""

    try:
        parsed = urlparse(value)
        host = (parsed.netloc or "").lower()
        raw_parts = [part for part in parsed.path.split("/") if part]
    except Exception:
        return ""

    if not raw_parts:
        return ""

    ignored = {
        "job", "jobs", "careers", "career", "positions", "position", "roles", "role",
        "opportunities", "opportunity", "opening", "openings", "external", "internal",
        "en-us", "en", "us", "apply", "view", "posting", "postings", "detail", "details"
    }

    def _raw_part_is_opaque(part: str) -> bool:
        compact = part.replace("-", "").replace("_", "")
        if len(compact) >= 24 and any(ch.isdigit() for ch in compact):
            return True
        hex_chars = set("0123456789abcdef")
        if len(compact) >= 24 and all(ch in hex_chars for ch in compact.lower()):
            return True
        return False

    ats_hosts = (
        "jobs.lever.co",
        "job-boards.greenhouse.io",
        "boards.greenhouse.io",
        "jobs.ashbyhq.com",
        "jobs.smartrecruiters.com",
        "myworkdayjobs.com",
    )

    candidate_parts = raw_parts[-3:]

    if any(ats_host in host for ats_host in ats_hosts):
        filtered = []
        for part in candidate_parts:
            normalized = normalize_text(part)
            if not normalized or normalized in ignored:
                continue
            filtered.append(part)
        if len(filtered) >= 2:
            filtered = filtered[1:]
        candidate_parts = filtered

    kept = []
    for part in candidate_parts:
        normalized = normalize_text(part)
        if not normalized:
            continue
        if normalized in ignored:
            continue
        if normalized.isdigit():
            continue
        if _raw_part_is_opaque(part):
            continue
        kept.append(normalized)

    if not kept:
        return ""

    hint = " ".join(kept)
    tokens = [token for token in hint.split() if token and not token.isdigit()]
    if len(tokens) < 2:
        return ""

    return hint


def _cheap_url_title_prefilter(job_url: str, settings: dict[str, Any]) -> tuple[bool, str]:
    target_titles = parse_csv_text(settings.get("target_titles", ""))
    if not target_titles:
        return True, "no target titles configured"

    hint = _extract_url_title_hint(job_url)
    if not hint:
        return True, "no reliable url title hint"

    try:
        expanded_titles = list(dict.fromkeys(expand_title_terms(target_titles)))
    except Exception:
        expanded_titles = target_titles[:]

    acronym_expansions = {
        "ceo": ["chief executive officer"],
        "cto": ["chief technology officer"],
        "cio": ["chief information officer"],
        "coo": ["chief operating officer"],
        "cfo": ["chief financial officer"],
        "cmo": ["chief marketing officer"],
        "cro": ["chief revenue officer"],
    }

    enriched_titles = []
    for title in expanded_titles:
        enriched_titles.append(title)
        normalized_title = normalize_text(title)
        if normalized_title in acronym_expansions:
            enriched_titles.extend(acronym_expansions[normalized_title])

    expanded_titles = list(dict.fromkeys(enriched_titles))

    normalized_hint = normalize_text(hint)
    hint_tokens = set(tokenize(hint))

    for target in expanded_titles:
        normalized_target = normalize_text(target)
        if not normalized_target:
            continue
        if normalized_target in normalized_hint:
            return True, f"url title hint matched '{target}'"

    target_token_pool = set()
    for target in expanded_titles:
        for token in tokenize(target):
            if len(token) >= 3:
                target_token_pool.add(token)

    overlap = hint_tokens.intersection(target_token_pool)
    if overlap:
        return True, f"url title hint token overlap: {', '.join(sorted(overlap)[:3])}"

    return False, f"url title prefilter mismatch: {hint}"


def _normalize_preparse_skip_reason(gate_reason: str) -> str:
    reason = safe_text(gate_reason).lower()
    if not reason:
        return "non_job_url"
    if reason in {"blank_url", "unclassified_non_job"}:
        return "non_job_url"
    if reason.startswith("blocked_pattern:") or reason.startswith("blocked_path:"):
        return "non_job_url"
    if reason in {
        "blocked_query_listing",
        "lever_board_root",
        "greenhouse_board_root",
        "ashby_board_root",
        "smartrecruiters_root",
        "workday_root",
        "blocked_generic_host",
        "blocked_jobgether_wrapper",
    }:
        return "non_job_url"
    return "non_job_url"


def _normalize_match_skip_reason(match: dict[str, Any]) -> str:
    qualification = match.get("qualification", {}) or {}
    reject_reason = safe_text(qualification.get("reject_reason", "")).lower()
    location_passed = bool(match.get("location_filter_passed", False))

    if not location_passed:
        return "location_mismatch"

    if "excluded keyword" in reject_reason or "matched excluded keywords" in reject_reason:
        return "excluded_keyword"

    if "title mismatch" in reject_reason:
        return "title_mismatch"

    if "location mismatch" in reject_reason or "not remote" in reject_reason:
        return "location_mismatch"

    if "missing job title" in reject_reason:
        return "parse_failed"

    return "below_threshold"



def _record_skip(
    skip_counts: Counter,
    skip_examples: dict[str, str],
    reason: str,
    detail: str = "",
) -> None:
    normalized = safe_text(reason) or "unknown_skip"
    skip_counts[normalized] += 1
    if normalized not in skip_examples and detail:
        skip_examples[normalized] = safe_text(detail)


def _append_skip_summary_lines(
    output_lines: list[str],
    skip_counts: Counter,
    skip_examples: dict[str, str],
) -> None:
    if not skip_counts:
        return

    total_skipped = sum(skip_counts.values())
    output_lines.append("")
    output_lines.append("Skip summary:")
    output_lines.append(f"Total skipped before ingest: {total_skipped}")

    for reason, count in skip_counts.most_common(8):
        example = safe_text(skip_examples.get(reason, ""))
        if example:
            output_lines.append(f"- {reason}: {count} | example: {example}")
        else:
            output_lines.append(f"- {reason}: {count}")


def _is_preparse_skip_reason(reason: str) -> bool:
    normalized = safe_text(reason)
    return normalized in {
        "non_job_url",
        "weak_url_title_match",
    }


def _is_postparse_skip_reason(reason: str) -> bool:
    normalized = safe_text(reason)
    return normalized in {
        "parse_failed",
        "processing_error",
        "title_mismatch",
        "location_mismatch",
        "excluded_keyword",
        "below_threshold",
    }


def _append_run_quality_summary_lines(
    output_lines: list[str],
    seen_urls: int,
    accepted_jobs: int,
    skip_counts: Counter,
) -> None:
    total_skipped = sum(skip_counts.values())
    preparse_skips = sum(count for reason, count in skip_counts.items() if _is_preparse_skip_reason(reason))
    postparse_skips = sum(count for reason, count in skip_counts.items() if _is_postparse_skip_reason(reason))
    duplicate_batch_skips = int(skip_counts.get("duplicate_in_batch", 0))

    def _pct(value: int, total: int) -> str:
        if total <= 0:
            return "0.0%"
        return f"{(value / total) * 100:.1f}%"

    output_lines.append("")
    output_lines.append("Run quality summary:")
    output_lines.append(f"- Seen URLs: {seen_urls}")
    output_lines.append(f"- Accepted jobs: {accepted_jobs} ({_pct(accepted_jobs, seen_urls)})")
    output_lines.append(f"- Pre-parse skips: {preparse_skips} ({_pct(preparse_skips, seen_urls)})")
    output_lines.append(f"- Post-parse skips: {postparse_skips} ({_pct(postparse_skips, seen_urls)})")
    if duplicate_batch_skips:
        output_lines.append(f"- Duplicate-in-batch skips: {duplicate_batch_skips} ({_pct(duplicate_batch_skips, seen_urls)})")

    dominant_reason = ""
    dominant_count = 0
    for reason, count in skip_counts.most_common():
        if reason == "duplicate_in_batch":
            continue
        dominant_reason = reason
        dominant_count = count
        break

    if dominant_reason:
        output_lines.append(
            f"- Dominant skip reason: {dominant_reason} ({dominant_count}, {_pct(dominant_count, max(1, total_skipped))} of skips)"
        )

    if accepted_jobs == 0 and preparse_skips > postparse_skips:
        output_lines.append(
            "- Operator read: this run underperformed mainly because discovery quality was weak before parsing."
        )
    elif accepted_jobs == 0 and postparse_skips >= preparse_skips:
        output_lines.append(
            "- Operator read: this run underperformed mainly because discovered candidates did not match fit policy after parsing."
        )
    elif accepted_jobs > 0 and dominant_reason:
        output_lines.append(
            f"- Operator read: the run produced usable jobs, but the main limiter was {dominant_reason}."
        )


def _append_discovery_drop_summary_lines(output_lines: list[str], discovery_result: dict[str, Any]) -> None:
    drop_summary = discovery_result.get("drop_summary", {}) or {}
    flattened: Counter = Counter()

    for _, bucket in drop_summary.items():
        if not isinstance(bucket, dict):
            continue
        for reason, count in bucket.items():
            flattened[safe_text(reason)] += int(count or 0)

    if not flattened:
        return

    output_lines.append("")
    output_lines.append("Discovery URL drop summary:")
    for reason, count in flattened.most_common(8):
        output_lines.append(f"- {reason}: {count}")


def _build_jobs_from_urls(urls: list[str], source_name: str, source_detail: str) -> dict[str, Any]:
    settings = load_settings()

    accepted_jobs = []
    accepted_jobs_by_key: dict[str, dict[str, Any]] = {}
    skipped_count = 0
    skipped_title_prefilter_count = 0
    skipped_duplicate_batch_count = 0
    error_count = 0
    output_lines: list[str] = []

    skip_counts: Counter = Counter()
    skip_examples: dict[str, str] = {}

    build_started_at = time.perf_counter()

    for job_url in urls:
        output_lines.append(f"Processing: {job_url}")

        current_stage = "url_gate"
        try:
            should_process, gate_reason = is_probable_job_url(job_url)
            if not should_process:
                output_lines.append(f"Skipped URL quality gate: {gate_reason} | {job_url}")
                skipped_count += 1
                _record_skip(
                    skip_counts,
                    skip_examples,
                    _normalize_preparse_skip_reason(gate_reason),
                    detail=job_url,
                )
                continue

            current_stage = "url_title_prefilter"
            title_prefilter_passed, title_prefilter_reason = _cheap_url_title_prefilter(job_url, settings)
            if not title_prefilter_passed:
                output_lines.append(f"Skipped URL title prefilter: {title_prefilter_reason} | {job_url}")
                skipped_title_prefilter_count += 1
                _record_skip(
                    skip_counts,
                    skip_examples,
                    "weak_url_title_match",
                    detail=job_url,
                )
                continue

            current_stage = "page_parse"
            job = create_job_record(job_url)
            setattr(job, "source", source_name)

            current_stage = "match_score"
            match = score_job_match(job, settings)

            if not match["should_accept"] and should_force_accept_without_location(job, settings):
                match["should_accept"] = True
                match["hard_reject"] = False
                match["location_filter_passed"] = True
                match["location_filter_reason"] = "blank-location title override"
                match["score"] = max(int(match.get("score", 0)), AUTO_ACCEPT_SCORE)
                existing_reason = safe_text(match.get("reason_text", ""))
                match["reason_text"] = (existing_reason + " | blank-location title override").strip(" |")

            if not match["should_accept"]:
                output_lines.append(
                    f"Skipped by match score ({match['score']}): {match['reason_text']}"
                )
                skipped_count += 1
                _record_skip(
                    skip_counts,
                    skip_examples,
                    _normalize_match_skip_reason(match),
                    detail=f"{safe_text(getattr(job, 'title', ''))} | {job_url}",
                )
                continue

            current_stage = "payload_enrichment"
            payload = enrich_job_payload(
                job,
                source_hint=source_name,
                source_detail_hint=source_detail,
            )

            batch_key = _batch_dedupe_key(payload)

            if batch_key:
                existing_payload = accepted_jobs_by_key.get(batch_key)
                if existing_payload is not None:
                    chosen_payload = _prefer_payload(existing_payload, payload)
                    accepted_jobs_by_key[batch_key] = chosen_payload
                    skipped_duplicate_batch_count += 1
                    output_lines.append(
                        f"Skipped duplicate in batch: "
                        f"{safe_text(payload.get('company', ''))} | "
                        f"{safe_text(payload.get('title', ''))} | "
                        f"{safe_text(payload.get('location', ''))}"
                    )
                    _record_skip(
                        skip_counts,
                        skip_examples,
                        "duplicate_in_batch",
                        detail=f"{safe_text(payload.get('title', ''))} | {safe_text(payload.get('job_posting_url', ''))}",
                    )
                    continue

                accepted_jobs_by_key[batch_key] = payload

            accepted_jobs.append(payload)
            output_lines.append(
                f"Accepted (score {match['score']}): "
                f"{safe_text(payload.get('company', ''))} | "
                f"{safe_text(payload.get('title', ''))} | "
                f"{safe_text(payload.get('location', ''))} | "
                f"{safe_text(payload.get('source_trust', 'Unknown'))}"
            )
        except Exception as exc:
            output_lines.append(f"Error: {exc}")
            error_count += 1
            if current_stage == "page_parse":
                _record_skip(skip_counts, skip_examples, "parse_failed", detail=job_url)
            else:
                _record_skip(skip_counts, skip_examples, "processing_error", detail=job_url)

    build_seconds = time.perf_counter() - build_started_at

    ai_scoring_started_at = time.perf_counter()
    ai_scored_count = 0
    ai_skipped_count = 0
    ai_error_count = 0

    resume_profile_text, resume_profile_source = load_resume_profile_text()

    if accepted_jobs:
        output_lines.append("")
        if resume_profile_text:
            output_lines.append(f"AI job scoring profile: {resume_profile_source}")
            for payload in accepted_jobs:
                score_result = score_accepted_job(payload, resume_profile_text)
                apply_score_to_job_payload(payload, score_result)

                score_status = safe_text(score_result.get("status", "")).lower()
                if score_status == "scored":
                    ai_scored_count += 1
                elif score_status == "skipped":
                    ai_skipped_count += 1
                else:
                    ai_error_count += 1
        else:
            ai_skipped_count = len(accepted_jobs)
            output_lines.append(
                "AI job scoring skipped: no resume/profile text file was found. "
                "Checked default locations plus JOB_AGENT_RESUME_PROFILE if set."
            )

    ai_scoring_seconds = time.perf_counter() - ai_scoring_started_at

    ingest_started_at = time.perf_counter()
    summary = ingest_job_records(
        job_records=accepted_jobs,
        source_name=source_name,
        source_detail=source_detail,
        run_type="validate_urls",
    )
    ingest_seconds = time.perf_counter() - ingest_started_at

    output_lines.append("")
    output_lines.append("Validation + ingestion complete.")
    output_lines.append(f"Seen URLs: {len(urls)}")
    output_lines.append(f"Accepted jobs: {len(accepted_jobs)}")
    output_lines.append(f"Skipped by scoring: {skipped_count}")
    output_lines.append(f"Skipped URL title prefilter: {skipped_title_prefilter_count}")
    output_lines.append(f"Skipped duplicate in batch: {skipped_duplicate_batch_count}")
    output_lines.append(f"Errors before ingest: {error_count}")
    output_lines.append(f"Inserted: {summary['inserted_count']}")
    output_lines.append(f"Updated: {summary['updated_count']}")
    output_lines.append(f"Skipped removed: {summary['skipped_removed_count']}")
    output_lines.append(f"AI scored accepted jobs: {ai_scored_count}")
    output_lines.append(f"AI skipped accepted jobs: {ai_skipped_count}")
    output_lines.append(f"AI scoring errors: {ai_error_count}")
    output_lines.append(f"Build/validate seconds: {build_seconds:.2f}")
    output_lines.append(f"AI scoring seconds: {ai_scoring_seconds:.2f}")
    output_lines.append(f"Ingest seconds: {ingest_seconds:.2f}")

    _append_run_quality_summary_lines(
        output_lines=output_lines,
        seen_urls=len(urls),
        accepted_jobs=len(accepted_jobs),
        skip_counts=skip_counts,
    )
    _append_skip_summary_lines(output_lines, skip_counts, skip_examples)

    source_yield_top = summary.get("source_yield_top", [])
    if source_yield_top:
        output_lines.append("")
        output_lines.append("Top sources this run:")
        for row in source_yield_top[:5]:
            output_lines.append(
                f"- {safe_text(row.get('ats_type', 'Unknown'))} | "
                f"{safe_text(row.get('source_root', 'unknown'))} | "
                f"{int(row.get('job_count', 0))} jobs"
            )

    source_dominance = summary.get("source_dominance", {})
    if source_dominance.get("flag"):
        output_lines.append("")
        output_lines.append(f"Dominance warning: {safe_text(source_dominance.get('reason', ''))}")

    output_lines.append(f"Auto-accept threshold: {AUTO_ACCEPT_SCORE}")
    if MAX_URLS_PER_RUN > 0:
        output_lines.append(f"Max URLs per run cap: {MAX_URLS_PER_RUN}")

    return {
        "status": "completed",
        "output": "\n".join(output_lines).strip(),
        "summary": summary,
        "accepted_jobs": len(accepted_jobs),
        "seen_urls": len(urls),
        "skipped_count": skipped_count,
        "skipped_title_prefilter_count": skipped_title_prefilter_count,
        "skipped_duplicate_batch_count": skipped_duplicate_batch_count,
        "error_count": error_count,
        "build_seconds": build_seconds,
        "ingest_seconds": ingest_seconds,
        "skip_summary": dict(skip_counts),
    }


def build_search_preview() -> dict[str, Any]:
    settings = load_settings()
    return {
        "plan": discover_module.build_search_plan(settings),
        "queries": discover_module.build_google_discovery_queries(settings),
    }


def discover_job_links() -> dict[str, Any]:
    settings = load_settings()
    discovery_result = discover_module.discover_urls(settings)

    discovered_urls = discovery_result.get("all_urls", [])
    discover_module.save_output_urls(JOB_URLS_FILE, discovered_urls)

    return {
        "status": "completed",
        "output": discovery_result.get("output", ""),
        "job_urls_file": str(JOB_URLS_FILE),
        "url_count": len(discovered_urls),
        "urls": discovered_urls,
        "providers": {
            "greenhouse": len(discovery_result.get("greenhouse_urls", [])),
            "lever": len(discovery_result.get("lever_urls", [])),
            "search": len(discovery_result.get("search_urls", [])),
        },
        "queries": discover_module.build_google_discovery_queries(settings),
        "plan": discover_module.build_search_plan(settings),
        "drop_summary": discovery_result.get("drop_summary", {}),
    }


def ingest_urls_from_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    urls = load_job_urls_from_file(path)

    if MAX_URLS_PER_RUN > 0:
        urls = urls[:MAX_URLS_PER_RUN]

    if not urls:
        return {
            "status": "completed",
            "output": f"No job URLs found in: {path.resolve()}",
            "summary": {
                "inserted_count": 0,
                "updated_count": 0,
                "skipped_removed_count": 0,
                "net_new_count": 0,
                "rediscovered_count": 0,
                "duplicate_in_run_count": 0,
            },
            "accepted_jobs": 0,
            "seen_urls": 0,
            "skipped_count": 0,
            "skipped_duplicate_batch_count": 0,
            "error_count": 0,
            "build_seconds": 0.0,
            "ingest_seconds": 0.0,
            "skip_summary": {},
        }

    return _build_jobs_from_urls(urls, source_name="Local Pipeline", source_detail=str(path.resolve()))


def ingest_pasted_urls(text_value: str) -> dict[str, Any]:
    urls = parse_manual_urls(text_value)
    if MAX_URLS_PER_RUN > 0:
        urls = urls[:MAX_URLS_PER_RUN]

    MANUAL_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_URLS_FILE.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    return _build_jobs_from_urls(
        urls,
        source_name="Local Pipeline",
        source_detail=str(MANUAL_URLS_FILE.resolve()),
    )


def discover_and_ingest() -> dict[str, Any]:
    total_started_at = time.perf_counter()

    discovery_started_at = time.perf_counter()
    discovery_result = discover_job_links()
    discovery_seconds = time.perf_counter() - discovery_started_at

    discovered_urls = discovery_result.get("urls", [])
    original_discovered_count = len(discovered_urls)

    if MAX_URLS_PER_RUN > 0:
        discovered_urls = discovered_urls[:MAX_URLS_PER_RUN]

    combined_output_parts = []
    if discovery_result.get("output"):
        combined_output_parts.append(discovery_result["output"])

    discovery_summary_lines = [
        f"Discovery seconds: {discovery_seconds:.2f}",
        f"Discovered URLs before cap: {original_discovered_count}",
    ]
    if MAX_URLS_PER_RUN > 0:
        discovery_summary_lines.append(
            f"URLs after cap: {len(discovered_urls)} (cap {MAX_URLS_PER_RUN})"
        )

    providers = discovery_result.get("providers", {}) or {}
    if providers:
        discovery_summary_lines.append(
            "Provider mix: "
            f"Greenhouse {int(providers.get('greenhouse', 0) or 0)}, "
            f"Lever {int(providers.get('lever', 0) or 0)}, "
            f"Search {int(providers.get('search', 0) or 0)}"
        )

    _append_discovery_drop_summary_lines(discovery_summary_lines, discovery_result)
    combined_output_parts.append("\n".join(discovery_summary_lines).strip())

    if not discovered_urls:
        combined_output_parts.append(
            "No URLs were available to ingest. Review your Settings criteria, confirm discovery dependencies are installed, or try pasted URLs."
        )
        total_seconds = time.perf_counter() - total_started_at
        combined_output_parts.append(f"Total pipeline seconds: {total_seconds:.2f}")
        return {
            "status": "completed",
            "output": "\n\n".join(combined_output_parts).strip(),
            "discovery": discovery_result,
            "ingest": {
                "status": "completed",
                "output": "No ingestion was performed because discovery returned zero URLs.",
                "summary": {
                    "inserted_count": 0,
                    "updated_count": 0,
                    "skipped_removed_count": 0,
                    "net_new_count": 0,
                    "rediscovered_count": 0,
                    "duplicate_in_run_count": 0,
                },
                "accepted_jobs": 0,
                "seen_urls": 0,
                "skipped_count": 0,
                "skipped_duplicate_batch_count": 0,
                "error_count": 0,
                "build_seconds": 0.0,
                "ingest_seconds": 0.0,
                "skip_summary": {},
            },
        }

    ingest_result = _build_jobs_from_urls(
        discovered_urls,
        source_name="Local Pipeline",
        source_detail="in_memory_discovery_result",
    )

    if ingest_result.get("output"):
        combined_output_parts.append(ingest_result["output"])

    total_seconds = time.perf_counter() - total_started_at
    combined_output_parts.append(f"Total pipeline seconds: {total_seconds:.2f}")

    return {
        "status": "completed",
        "output": "\n\n".join(combined_output_parts).strip(),
        "discovery": discovery_result,
        "ingest": ingest_result,
    }
