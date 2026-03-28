from __future__ import annotations

import html
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse
from typing import Any

import requests

from config import JOB_URLS_FILE, MANUAL_URLS_FILE
from services.ai_job_scoring import (
    apply_score_to_job_payload,
    load_scoring_profile_text,
    score_accepted_job,
)
from services.ai_job_scrub import (
    apply_scrub_to_job_payload,
    scrub_accepted_job,
)
from services.ingestion import ingest_job_records, update_ingestion_run_details
from services.job_store import (
    count_jobs_for_rescoring,
    list_jobs_for_rescoring,
    update_job_scoring_fields,
)
from services.location_matching import (
    evaluate_location_filters,
    location_matches_preference,
    parse_location,
)
from services.matching_profiles import expand_title_terms
from services.search_plan import build_search_title_variants
from services.settings import load_settings
from services.source_layer_import import record_source_layer_run
from services.source_layer import get_source_layer_mode
from services.source_layer_shadow import run_shadow_endpoint_selection
from services.source_layer_status_smoke import build_source_layer_status_summary
from services.source_trust import enrich_job_payload
from services.job_qualifier import qualify_job
from services.source_layer_shadow import SHADOW_SELECTION_CAP
from src import discover_job_urls as discover_module
from src.validate_job_url import create_job_record


AUTO_ACCEPT_SCORE = 45
MAX_URLS_PER_RUN = 25  # temporary fast-test cap; set to 0 for unlimited
TRANSIENT_FETCH_RETRY_ATTEMPTS = 2
TRANSIENT_FETCH_RETRY_DELAY_SECONDS = 0.35
NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY = 3
WORKDAY_SEED_PAGE_SIZE = 20
WORKDAY_SEED_MAX_PAGES = 5
SEED_FOREIGN_REMOTE_MARKERS = {
    "argentina",
    "australia",
    "brazil",
    "canada",
    "colombia",
    "europe",
    "france",
    "germany",
    "india",
    "ireland",
    "italy",
    "japan",
    "latam",
    "latin america",
    "mexico",
    "netherlands",
    "philippines",
    "poland",
    "portugal",
    "spain",
    "united kingdom",
    "uk",
}


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _seed_search_title_variants(settings: dict[str, Any], max_variants: int = 6) -> list[str]:
    target_titles = parse_csv_setting(settings.get("target_titles", ""))
    if not target_titles:
        return []
    return build_search_title_variants(target_titles, max_variants=max_variants)


def _seed_search_title(settings: dict[str, Any]) -> str:
    variants = _seed_search_title_variants(settings, max_variants=6)
    return safe_text(variants[0] if variants else "")


def _is_transient_fetch_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ),
    )


def _is_stale_ats_posting_error(exc: Exception, job_url: str) -> bool:
    if not isinstance(exc, requests.exceptions.HTTPError):
        return False
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code != 404:
        return False

    try:
        host = (urlparse(safe_text(job_url)).netloc or "").lower()
    except Exception:
        return False

    ats_hosts = (
        "jobs.lever.co",
        "job-boards.greenhouse.io",
        "boards.greenhouse.io",
        "myworkdayjobs.com",
        "jobs.smartrecruiters.com",
        "jobs.ashbyhq.com",
    )
    return any(ats_host in host for ats_host in ats_hosts)


def _normalize_job_posting_url(job_url: str) -> str:
    value = safe_text(job_url)
    if not value:
        return ""

    try:
        parsed = urlparse(value)
    except Exception:
        return value

    host = (parsed.netloc or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    normalized_path = parsed.path or "/"

    if "jobs.lever.co" in host and path_parts and path_parts[-1].lower() == "apply":
        normalized_path = "/" + "/".join(path_parts[:-1])
        return urlunparse(parsed._replace(path=normalized_path, params="", query="", fragment=""))

    if "jobs.ashbyhq.com" in host and path_parts and path_parts[-1].lower() == "application":
        normalized_path = "/" + "/".join(path_parts[:-1])
        return urlunparse(parsed._replace(path=normalized_path, params="", query="", fragment=""))

    ats_hosts = (
        "jobs.lever.co",
        "job-boards.greenhouse.io",
        "boards.greenhouse.io",
        "jobs.ashbyhq.com",
        "jobs.smartrecruiters.com",
        "myworkdayjobs.com",
    )
    if any(ats_host in host for ats_host in ats_hosts):
        normalized_path = normalized_path.rstrip("/") or "/"
        return urlunparse(parsed._replace(path=normalized_path, params="", query="", fragment=""))

    return value


def _normalize_job_posting_urls(urls: list[str]) -> list[str]:
    normalized_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = _normalize_job_posting_url(url)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_urls.append(normalized)
    return normalized_urls


def _create_job_record_with_retry(job_url: str):
    normalized_job_url = _normalize_job_posting_url(job_url)
    last_exc: Exception | None = None
    for attempt in range(1, TRANSIENT_FETCH_RETRY_ATTEMPTS + 1):
        try:
            return create_job_record(normalized_job_url)
        except Exception as exc:
            last_exc = exc
            if attempt >= TRANSIENT_FETCH_RETRY_ATTEMPTS or not _is_transient_fetch_error(exc):
                raise
            time.sleep(TRANSIENT_FETCH_RETRY_DELAY_SECONDS)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Job record creation failed without an exception.")


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


LEADERSHIP_LEVEL_GROUPS: dict[str, set[str]] = {
    "chief": {"chief", "ceo", "cto", "cio", "cfo", "coo", "cmo", "cro", "president"},
    "vice_president": {"vice", "president", "vp", "avp", "svp", "evp"},
    "director": {"director", "head"},
    "manager": {"manager", "supervisor"},
    "lead": {"lead", "principal"},
}

FUNCTION_LANE_GROUPS: dict[str, set[str]] = {
    "technology": {
        "technology",
        "it",
        "information",
        "engineering",
        "software",
        "systems",
        "infrastructure",
        "security",
        "cybersecurity",
        "cyber",
        "architecture",
        "platform",
        "application",
        "applications",
        "data",
        "analytics",
        "digital",
        "product",
        "technical",
    },
    "finance": {"finance", "financial", "accounting", "treasury", "audit", "controller"},
    "operations": {
        "operations",
        "operational",
        "manufacturing",
        "supply",
        "procurement",
        "logistics",
        "construction",
        "plant",
        "facilities",
        "warehouse",
    },
    "sales": {"sales", "revenue", "commercial", "growth", "business-development"},
    "marketing": {"marketing", "brand", "communications", "content"},
    "people": {"people", "hr", "human", "talent", "recruiting", "acquisition"},
    "legal": {"legal", "compliance", "privacy", "regulatory", "counsel"},
}


def _detect_leadership_levels(text: str) -> set[str]:
    normalized = normalize_text(text)
    tokens = set(tokenize(text))
    levels: set[str] = set()

    for level, markers in LEADERSHIP_LEVEL_GROUPS.items():
        if level == "vice_president":
            if (
                "vice president" in normalized
                or any(marker in tokens for marker in {"vp", "avp", "svp", "evp"})
            ):
                levels.add(level)
            continue
        if level == "chief":
            if "chief" in tokens or any(marker in tokens for marker in {"ceo", "cto", "cio", "cfo", "coo", "cmo", "cro"}):
                levels.add(level)
            continue
        if any(marker in tokens for marker in markers):
            levels.add(level)

    return levels


def _detect_function_lanes(text: str) -> set[str]:
    tokens = set(tokenize(text))
    lanes: set[str] = set()
    for lane, markers in FUNCTION_LANE_GROUPS.items():
        if tokens.intersection(markers):
            lanes.add(lane)
    return lanes


def _hint_matches_target_signature(hint: str, targets: list[str]) -> bool:
    hint_levels = _detect_leadership_levels(hint)
    hint_lanes = _detect_function_lanes(hint)
    if not hint_levels and not hint_lanes:
        return True

    target_levels: set[str] = set()
    target_lanes: set[str] = set()
    for target in targets:
        target_levels.update(_detect_leadership_levels(target))
        target_lanes.update(_detect_function_lanes(target))

    if target_levels and hint_levels and not target_levels.intersection(hint_levels):
        return False

    # Only gate by function lane when both sides express a lane.
    if target_lanes and hint_lanes and not target_lanes.intersection(hint_lanes):
        return False

    return True


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

    if "/careers/" in lowered:
        return False, "blocked_pattern:/careers/"

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
        decoded = unquote(part)
        normalized = normalize_text(decoded)
        readable_tokens = [token for token in normalized.split() if token.isalpha()]
        if len(readable_tokens) >= 3 and any(len(token) >= 4 for token in readable_tokens):
            return False

        compact = decoded.replace("-", "").replace("_", "").replace("%", "")
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
        normalized = normalize_text(unquote(part))
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
        if not _hint_matches_target_signature(hint, expanded_titles):
            return False, f"url title signature mismatch: {hint}"
        return True, f"url title hint token overlap: {', '.join(sorted(overlap)[:3])}"

    if not _hint_matches_target_signature(hint, expanded_titles):
        return False, f"url title signature mismatch: {hint}"

    return False, f"url title prefilter mismatch: {hint}"


def _cheap_seed_location_prefilter_from_hint(hint_source: str, settings: dict[str, Any]) -> tuple[bool, str]:
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    remote_only = safe_text(settings.get("remote_only", "false")).lower() == "true"

    if not preferred_locations and not remote_only:
        return True, "no preferred locations configured"

    normalized_hint = normalize_text(hint_source)
    if not normalized_hint:
        return True, "no reliable url location hint"

    if remote_only and "remote" in normalized_hint:
        foreign_markers = [
            marker
            for marker in SEED_FOREIGN_REMOTE_MARKERS
            if marker in normalized_hint
        ]
        if foreign_markers:
            return False, f"url location prefilter foreign remote mismatch: {hint_source}"

    if "remote" in normalized_hint:
        return True, "url location hint matched remote"

    if remote_only:
        return False, "url location prefilter mismatch: remote_only"

    ignored_tokens = {"metro", "area", "city", "state", "county", "region", "office", "location"}
    for location in preferred_locations:
        normalized_location = normalize_text(location)
        if normalized_location and normalized_location in normalized_hint:
            return True, f"url location hint matched '{location}'"

        location_tokens = {
            token
            for token in tokenize(location)
            if len(token) >= 4 and token not in ignored_tokens
        }
        if location_tokens and location_tokens.intersection(set(tokenize(normalized_hint))):
            return True, f"url location hint token overlap: {', '.join(sorted(location_tokens)[:2])}"

    return False, f"url location prefilter mismatch: {hint_source}"


def _cheap_seed_location_prefilter(job_url: str, settings: dict[str, Any]) -> tuple[bool, str]:
    try:
        parsed = urlparse(safe_text(job_url))
        hint_source = " ".join(part for part in [parsed.path, parsed.query] if safe_text(part))
    except Exception:
        hint_source = safe_text(job_url)
    return _cheap_seed_location_prefilter_from_hint(hint_source, settings)


def _cheap_seed_title_prefilter_from_hint(hint: str, settings: dict[str, Any]) -> tuple[bool, str]:
    target_titles = _seed_search_title_variants(settings, max_variants=6)
    if not target_titles:
        return True, "no target titles configured"

    if not hint:
        return True, "no reliable url title hint"

    normalized_hint = normalize_text(hint)
    hint_tokens = {
        token
        for token in tokenize(hint)
        if len(token) >= 3
    }
    if not hint_tokens:
        return True, "url title hint too sparse for seed filtering"

    if not _hint_matches_target_signature(hint, target_titles):
        return False, f"seed title signature mismatch: {hint}"

    best_overlap = 0.0
    best_target = ""
    best_phrase = 0.0

    for target in target_titles:
        overlap = token_overlap_score(target, hint)
        phrase = phrase_match_bonus(target, hint)
        if phrase > best_phrase or (phrase == best_phrase and overlap > best_overlap):
            best_overlap = overlap
            best_phrase = phrase
            best_target = target

    if best_phrase >= 1.0:
        return True, f"seed title phrase matched '{best_target}'"

    if best_overlap >= 0.34:
        return True, f"seed title overlap matched '{best_target}' ({best_overlap:.2f})"

    target_lanes: set[str] = set()
    target_levels: set[str] = set()
    for target in target_titles:
        target_lanes.update(_detect_function_lanes(target))
        target_levels.update(_detect_leadership_levels(target))

    hint_lanes = _detect_function_lanes(hint)
    hint_levels = _detect_leadership_levels(hint)

    if target_levels and hint_levels and target_levels.intersection(hint_levels):
        if target_lanes and hint_lanes and target_lanes.intersection(hint_lanes):
            return True, f"seed leadership/function lane matched: {hint}"

    return False, f"seed title prefilter mismatch: {hint}"


def _cheap_seed_title_prefilter(job_url: str, settings: dict[str, Any]) -> tuple[bool, str]:
    hint = _extract_url_title_hint(job_url)
    return _cheap_seed_title_prefilter_from_hint(hint, settings)


def _filter_next_gen_seed_urls(
    urls: list[str],
    settings: dict[str, Any],
    *,
    apply_location_filter: bool,
    per_company_cap: int = NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY,
) -> tuple[list[str], int, int]:
    kept: list[str] = []
    title_skips = 0
    location_skips = 0

    for url in urls:
        title_ok, _ = _cheap_seed_title_prefilter(url, settings)
        if not title_ok:
            title_skips += 1
            continue

        if apply_location_filter:
            location_ok, _ = _cheap_seed_location_prefilter(url, settings)
            if not location_ok:
                location_skips += 1
                continue

        kept.append(url)
        if per_company_cap > 0 and len(kept) >= per_company_cap:
            break

    return list(dict.fromkeys(kept)), title_skips, location_skips


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


def _build_jobs_from_urls(
    urls: list[str],
    source_name: str,
    source_detail: str,
    *,
    use_ai_scoring: bool = True,
    seeded_job_urls: list[str] | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    normalized_urls = _normalize_job_posting_urls(urls)
    seeded_job_url_set = {
        safe_text(_normalize_job_posting_url(url)).strip().lower()
        for url in (seeded_job_urls or [])
        if safe_text(_normalize_job_posting_url(url))
    }

    accepted_jobs = []
    accepted_jobs_by_key: dict[str, dict[str, Any]] = {}
    skipped_count = 0
    skipped_title_prefilter_count = 0
    skipped_duplicate_batch_count = 0
    error_count = 0
    first_error_message = ""
    output_lines: list[str] = []

    skip_counts: Counter = Counter()
    skip_examples: dict[str, str] = {}

    build_started_at = time.perf_counter()

    for job_url in normalized_urls:
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
            job = _create_job_record_with_retry(job_url)
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
            if current_stage == "page_parse" and _is_stale_ats_posting_error(exc, job_url):
                output_lines.append(f"Skipped unavailable ATS posting: {job_url} | HTTP 404")
                skipped_count += 1
                _record_skip(skip_counts, skip_examples, "stale_ats_posting", detail=job_url)
                continue
            error_line = f"Error: {exc}"
            output_lines.append(error_line)
            error_count += 1
            if not first_error_message:
                first_error_message = error_line
            if current_stage == "page_parse":
                _record_skip(skip_counts, skip_examples, "parse_failed", detail=job_url)
            else:
                _record_skip(skip_counts, skip_examples, "processing_error", detail=job_url)

    build_seconds = time.perf_counter() - build_started_at

    ai_scoring_started_at = time.perf_counter()
    ai_scored_count = 0
    ai_skipped_count = 0
    ai_error_count = 0

    if accepted_jobs:
        output_lines.append("")
        if use_ai_scoring:
            resume_profile_text, resume_profile_source = load_scoring_profile_text()
            if resume_profile_text:
                output_lines.append("AI job scoring: enabled")
                output_lines.append(f"AI job scoring profile: {resume_profile_source}")
                for payload in accepted_jobs:
                    score_result = score_accepted_job(payload, resume_profile_text)
                    apply_score_to_job_payload(payload, score_result)
                    scrub_result = scrub_accepted_job(payload, resume_profile_text)
                    apply_scrub_to_job_payload(payload, scrub_result)

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
                    "AI job scoring skipped: no saved Profile Context or fallback profile text was found. "
                    "Add content in Settings -> Profile Context, or use profile_context.txt / JOB_AGENT_RESUME_PROFILE as fallback."
                )
        else:
            ai_skipped_count = len(accepted_jobs)
            output_lines.append("AI job scoring: disabled for this run")
            output_lines.append("AI scrub: disabled because AI job scoring is disabled for this run")

    ai_scoring_seconds = time.perf_counter() - ai_scoring_started_at

    seeded_accepted_payloads = [
        payload
        for payload in accepted_jobs
        if safe_text(payload.get("job_posting_url", "")).strip().lower() in seeded_job_url_set
    ]
    seeded_accepted_companies = list(
        dict.fromkeys(
            safe_text(payload.get("company", "")) or "(unknown company)"
            for payload in seeded_accepted_payloads
        )
    )[:5]
    seeded_accepted_jobs = len(seeded_accepted_payloads)
    legacy_accepted_jobs = max(len(accepted_jobs) - seeded_accepted_jobs, 0)

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
    output_lines.append(f"Seen URLs: {len(normalized_urls)}")
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

    if seeded_job_url_set:
        output_lines.append("")
        output_lines.append("Next-gen contribution summary:")
        output_lines.append(f"- Seeded URLs discovered: {len(seeded_job_url_set)}")
        output_lines.append(f"- Seeded URLs accepted: {seeded_accepted_jobs}")
        output_lines.append(f"- Legacy URLs accepted: {legacy_accepted_jobs}")
        output_lines.append(
            f"- Seeded accepted companies: {', '.join(seeded_accepted_companies) if seeded_accepted_companies else 'none'}"
        )

    _append_run_quality_summary_lines(
        output_lines=output_lines,
        seen_urls=len(normalized_urls),
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
        "seen_urls": len(normalized_urls),
        "skipped_count": skipped_count,
        "skipped_title_prefilter_count": skipped_title_prefilter_count,
        "skipped_duplicate_batch_count": skipped_duplicate_batch_count,
        "error_count": error_count,
        "first_error_message": first_error_message,
        "build_seconds": build_seconds,
        "ingest_seconds": ingest_seconds,
        "skip_summary": dict(skip_counts),
        "seeded_url_count": len(seeded_job_url_set),
        "seeded_accepted_jobs": seeded_accepted_jobs,
        "legacy_accepted_jobs": legacy_accepted_jobs,
        "seeded_accepted_companies": seeded_accepted_companies,
    }


def _refresh_payload_with_live_page_data(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    job_url = safe_text(payload.get("job_posting_url", ""))
    if not job_url:
        return payload, False

    refreshed_job = _create_job_record_with_retry(job_url)

    refreshed_payload = dict(payload)
    refreshed_payload["company"] = safe_text(getattr(refreshed_job, "company", payload.get("company", "")))
    refreshed_payload["title"] = safe_text(getattr(refreshed_job, "title", payload.get("title", "")))
    refreshed_payload["normalized_title"] = safe_text(
        getattr(refreshed_job, "normalized_title", payload.get("normalized_title", ""))
    )
    refreshed_payload["role_family"] = safe_text(getattr(refreshed_job, "role_family", payload.get("role_family", "")))
    refreshed_payload["description_text"] = safe_text(getattr(refreshed_job, "description_text", ""))
    refreshed_payload["job_posting_url"] = safe_text(getattr(refreshed_job, "job_posting_url", job_url)) or job_url
    refreshed_payload["location"] = safe_text(getattr(refreshed_job, "location", payload.get("location", "")))
    refreshed_payload["remote_type"] = safe_text(getattr(refreshed_job, "remote_type", payload.get("remote_type", "")))
    refreshed_payload["dallas_dfw_match"] = safe_text(
        getattr(refreshed_job, "dallas_dfw_match", payload.get("dallas_dfw_match", ""))
    )
    refreshed_payload["compensation_raw"] = safe_text(
        getattr(refreshed_job, "compensation_raw", payload.get("compensation_raw", ""))
    )
    refreshed_payload["validation_status"] = safe_text(getattr(refreshed_job, "validation_status", payload.get("validation_status", "")))
    refreshed_payload["validation_confidence"] = safe_text(
        getattr(refreshed_job, "validation_confidence", payload.get("validation_confidence", ""))
    )
    refreshed_payload["compensation_status"] = safe_text(
        getattr(refreshed_job, "compensation_status", payload.get("compensation_status", ""))
    )

    refresh_notes = list(payload.get("_refresh_notes", []))
    field_specs = [
        ("company", "Company"),
        ("title", "Title"),
        ("location", "Location"),
        ("compensation_raw", "Compensation"),
    ]
    for payload_key, label in field_specs:
        old_value = safe_text(payload.get(payload_key, ""))
        new_value = safe_text(refreshed_payload.get(payload_key, ""))
        if not new_value or new_value == old_value:
            continue
        refresh_notes.append(f"Live page refresh updated {label}: {old_value or 'blank'} -> {new_value}")
    if refresh_notes:
        refreshed_payload["_refresh_notes"] = refresh_notes

    return refreshed_payload, True


def build_search_preview() -> dict[str, Any]:
    settings = load_settings()
    return {
        "plan": discover_module.build_search_plan(settings),
        "queries": discover_module.build_google_discovery_queries(settings),
    }


def _format_source_layer_run_snapshot(
    *,
    source_layer_mode: str,
    discovery_result: dict[str, Any],
    ingest_result: dict[str, Any],
) -> str:
    status_summary = build_source_layer_status_summary()
    shadow_status = status_summary.get("shadow", {}) if isinstance(status_summary, dict) else {}
    shadow_result = (
        discovery_result.get("shadow_result", {})
        if isinstance(discovery_result, dict)
        else {}
    )
    if not isinstance(shadow_result, dict) or not shadow_result:
        shadow_result = run_shadow_endpoint_selection()
    ats_counts = shadow_result.get("selected_ats_counts", {}) if isinstance(shadow_result, dict) else {}
    top_ats = ", ".join(
        f"{vendor} {count}"
        for vendor, count in sorted(
            ((str(vendor), int(count)) for vendor, count in dict(ats_counts).items()),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
    )
    selected_companies = ", ".join(
        str(name)
        for name in (shadow_result.get("selected_company_names", []) if isinstance(shadow_result, dict) else [])
    )

    providers = discovery_result.get("providers", {}) if isinstance(discovery_result, dict) else {}
    provider_mix = (
        f"Greenhouse {int(providers.get('greenhouse', 0) or 0)}, "
        f"Lever {int(providers.get('lever', 0) or 0)}, "
        f"Search {int(providers.get('search', 0) or 0)}"
    )

    return "\n".join(
        [
            "Source Layer Run Snapshot:",
            f"- Mode: {source_layer_mode}",
            f"- Discovered URLs: {len(discovery_result.get('urls', []) or [])}",
            f"- Accepted jobs: {int(ingest_result.get('accepted_jobs', 0) or 0)}",
            f"- Shadow companies: {int(shadow_status.get('company_count', 0) or 0)}",
            f"- Shadow active endpoints: {int(shadow_status.get('active_endpoint_count', 0) or 0)}",
            f"- Shadow approved endpoints: {int(shadow_status.get('approved_endpoint_count', 0) or 0)}",
            f"- Shadow selected endpoints: {int(shadow_result.get('selected_endpoint_count', 0) or 0)}",
            f"- Next-gen supported seeds scanned: {int(discovery_result.get('next_gen_supported_seeds_scanned', 0) or 0)}",
            f"- Next-gen unsupported seeds skipped: {int(discovery_result.get('next_gen_unsupported_seeds_skipped', 0) or 0)}",
            f"- Next-gen seeded URLs: {len(discovery_result.get('next_gen_seed_urls', []) or [])}",
            f"- Next-gen seeded accepted jobs: {int(ingest_result.get('seeded_accepted_jobs', 0) or 0)}",
            f"- Provider mix: {provider_mix}",
            f"- Top shadow ATS families: {top_ats or 'none yet'}",
            f"- Top shadow companies: {selected_companies or 'none yet'}",
        ]
    )


def _record_pipeline_source_layer_run(
    *,
    source_layer_mode: str,
    discovery_result: dict[str, Any],
    ingest_result: dict[str, Any],
) -> None:
    providers = discovery_result.get("providers", {}) if isinstance(discovery_result, dict) else {}
    shadow_result = (
        discovery_result.get("shadow_result", {})
        if isinstance(discovery_result, dict)
        else {}
    )
    notes = (
        "Pipeline discovery run. "
        f"Provider mix: greenhouse {int(providers.get('greenhouse', 0) or 0)}, "
        f"lever {int(providers.get('lever', 0) or 0)}, "
        f"search {int(providers.get('search', 0) or 0)}."
    )
    selected_companies = ", ".join(
        str(name)
        for name in (shadow_result.get("selected_company_names", []) if isinstance(shadow_result, dict) else [])
    )
    if selected_companies:
        notes += f" Shadow companies: {selected_companies}."
    supported_seeds_scanned = int(discovery_result.get("next_gen_supported_seeds_scanned", 0) or 0)
    unsupported_seeds_skipped = int(discovery_result.get("next_gen_unsupported_seeds_skipped", 0) or 0)
    if supported_seeds_scanned or unsupported_seeds_skipped:
        notes += (
            f" Next-gen supported seeds scanned: {supported_seeds_scanned}."
            f" Next-gen unsupported seeds skipped: {unsupported_seeds_skipped}."
        )
    seeded_urls = len(discovery_result.get("next_gen_seed_urls", []) or [])
    if seeded_urls:
        notes += f" Next-gen seeded URLs: {seeded_urls}."
    seeded_accepted_jobs = int(ingest_result.get("seeded_accepted_jobs", 0) or 0)
    if seeded_accepted_jobs:
        notes += f" Next-gen seeded accepted jobs: {seeded_accepted_jobs}."
    seeded_accepted_companies = ", ".join(
        str(name)
        for name in (ingest_result.get("seeded_accepted_companies", []) or [])
    )
    if seeded_accepted_companies:
        notes += f" Seeded accepted companies: {seeded_accepted_companies}."
    seed_failures = discovery_result.get("next_gen_seed_failures", []) or []
    if isinstance(seed_failures, list) and seed_failures:
        notes += f" Next-gen seed failures: {' | '.join(str(item) for item in seed_failures[:3])}."
    first_error_message = safe_text(ingest_result.get("first_error_message", ""))
    if first_error_message:
        notes += f" First pipeline error: {first_error_message}."
    record_source_layer_run(
        mode=source_layer_mode,
        imported_records=0,
        selected_endpoints=int(shadow_result.get("selected_endpoint_count", 0) or 0),
        discovered_urls=len(discovery_result.get("urls", []) or []),
        accepted_jobs=int(ingest_result.get("accepted_jobs", 0) or 0),
        errors=int(ingest_result.get("error_count", 0) or 0),
        notes=notes,
    )


def _discover_urls_from_next_gen_seeds(
    *,
    settings: dict[str, Any],
    shadow_result: dict[str, Any],
) -> tuple[list[str], list[str], int, int, list[str]]:
    selected_candidates = shadow_result.get("selected_candidates", []) if isinstance(shadow_result, dict) else []
    if not isinstance(selected_candidates, list):
        return [], ["- Next-gen seed discovery: no selected candidates available."], 0, 0, []

    discovered: list[str] = []
    log_lines: list[str] = []
    scanned_count = 0
    unsupported_count = 0
    failure_lines: list[str] = []

    for candidate in selected_candidates:
        if not isinstance(candidate, dict):
            continue
        endpoint_url = safe_text(candidate.get("endpoint_url", ""))
        ats_vendor = safe_text(candidate.get("ats_vendor", "")).lower()
        company_name = safe_text(candidate.get("company_name", "")) or "(unknown company)"
        if not endpoint_url:
            continue

        if ats_vendor == "greenhouse":
            scanned_count += 1
            log_lines.append(f"Checking next-gen Greenhouse seed: {company_name} | {endpoint_url}")
            try:
                urls = discover_module.discover_greenhouse_jobs(endpoint_url, settings)
                discovered.extend(urls)
                log_lines.append(f"Next-gen Greenhouse URLs found: {len(urls)}")
            except Exception as exc:
                failure = f"Next-gen Greenhouse seed failed: {company_name} | {exc}"
                log_lines.append(failure)
                failure_lines.append(failure)
        elif ats_vendor == "lever":
            scanned_count += 1
            log_lines.append(f"Checking next-gen Lever seed: {company_name} | {endpoint_url}")
            try:
                urls = discover_module.discover_lever_jobs(endpoint_url, settings)
                discovered.extend(urls)
                log_lines.append(f"Next-gen Lever URLs found: {len(urls)}")
            except Exception as exc:
                failure = f"Next-gen Lever seed failed: {company_name} | {exc}"
                log_lines.append(failure)
                failure_lines.append(failure)
        elif ats_vendor == "workday":
            scanned_count += 1
            log_lines.append(f"Checking next-gen Workday seed: {company_name} | {endpoint_url}")
            try:
                urls = _discover_workday_jobs(endpoint_url, settings)
                filtered_urls, title_skips, location_skips = _filter_next_gen_seed_urls(
                    urls,
                    settings,
                    apply_location_filter=True,
                )
                discovered.extend(filtered_urls)
                log_lines.append(
                    "Next-gen Workday URLs found: "
                    f"{len(urls)} | kept: {len(filtered_urls)} "
                    f"(title skips: {title_skips}, location skips: {location_skips}, "
                    f"company cap: {NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY})"
                )
            except Exception as exc:
                failure = f"Next-gen Workday seed failed: {company_name} | {exc}"
                log_lines.append(failure)
                failure_lines.append(failure)
        elif ats_vendor == "sap successfactors":
            if not _supports_successfactors_seed_endpoint(endpoint_url):
                unsupported_count += 1
                continue
            scanned_count += 1
            log_lines.append(f"Checking next-gen SuccessFactors seed: {company_name} | {endpoint_url}")
            try:
                urls = _discover_successfactors_jobs(endpoint_url, settings)
                filtered_urls, title_skips, location_skips = _filter_next_gen_seed_urls(
                    urls,
                    settings,
                    apply_location_filter=True,
                )
                discovered.extend(filtered_urls)
                log_lines.append(
                    "Next-gen SuccessFactors URLs found: "
                    f"{len(urls)} | kept: {len(filtered_urls)} "
                    f"(title skips: {title_skips}, location skips: {location_skips}, "
                    f"company cap: {NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY})"
                )
            except Exception as exc:
                failure = f"Next-gen SuccessFactors seed failed: {company_name} | {exc}"
                log_lines.append(failure)
                failure_lines.append(failure)
        elif ats_vendor == "icims":
            scanned_count += 1
            log_lines.append(f"Checking next-gen iCIMS seed: {company_name} | {endpoint_url}")
            try:
                urls = _discover_icims_jobs(endpoint_url, settings)
                filtered_urls, title_skips, location_skips = _filter_next_gen_seed_urls(
                    urls,
                    settings,
                    apply_location_filter=True,
                )
                discovered.extend(filtered_urls)
                log_lines.append(
                    "Next-gen iCIMS URLs found: "
                    f"{len(urls)} | kept: {len(filtered_urls)} "
                    f"(title skips: {title_skips}, location skips: {location_skips}, "
                    f"company cap: {NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY})"
                )
            except Exception as exc:
                failure = f"Next-gen iCIMS seed failed: {company_name} | {exc}"
                log_lines.append(failure)
                failure_lines.append(failure)
        elif ats_vendor == "taleo / oracle recruiting":
            if not _supports_taleo_oracle_seed_endpoint(endpoint_url):
                unsupported_count += 1
                continue
            scanned_count += 1
            log_lines.append(f"Checking next-gen Taleo seed: {company_name} | {endpoint_url}")
            try:
                urls = _discover_taleo_jobs(endpoint_url, settings)
                kept_urls = urls[:NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY]
                discovered.extend(kept_urls)
                log_lines.append(
                    "Next-gen Taleo URLs found: "
                    f"{len(urls)} | kept: {len(kept_urls)} "
                    f"(company cap: {NEXT_GEN_MAX_SEEDED_URLS_PER_COMPANY})"
                )
            except Exception as exc:
                failure = f"Next-gen Taleo seed failed: {company_name} | {exc}"
                log_lines.append(failure)
                failure_lines.append(failure)
        else:
            unsupported_count += 1

    discovered = list(dict.fromkeys(discovered))
    if scanned_count or unsupported_count:
        log_lines.insert(
            0,
            "Next-gen seed discovery summary:"
            f" scanned {scanned_count} supported seed(s), skipped {unsupported_count} unsupported seed(s).",
        )
    else:
        log_lines.append("- Next-gen seed discovery: no supported seed endpoints were available.")

    return discovered, log_lines, scanned_count, unsupported_count, failure_lines


def _extract_workday_metadata(page_text: str) -> tuple[str, str]:
    tenant_match = re.search(r'tenant:\s*"([^"]+)"', page_text)
    site_match = re.search(r'siteId:\s*"([^"]+)"', page_text)
    tenant = safe_text(tenant_match.group(1) if tenant_match else "")
    site_id = safe_text(site_match.group(1) if site_match else "")
    return tenant, site_id


def _workday_board_prefix(endpoint_url: str) -> str:
    parsed = urlparse(safe_text(endpoint_url))
    path = safe_text(parsed.path)
    if not path or path == "/":
        return ""

    cleaned = path.rstrip("/")
    for suffix in ("/login", "/search-results"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break

    cleaned = cleaned.rstrip("/")
    if not cleaned:
        return ""
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


def _build_workday_detail_url(endpoint_url: str, external_path: str) -> str:
    parsed = urlparse(safe_text(endpoint_url))
    base_url = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    path = safe_text(external_path)
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    normalized_external = path if path.startswith("/") else f"/{path}"
    board_prefix = _workday_board_prefix(endpoint_url)
    if board_prefix:
        return f"{base_url}{board_prefix}{normalized_external}"
    return f"{base_url}{normalized_external}"


def _workday_seed_payloads(settings: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seed_title = _seed_search_title(settings)
    if seed_title:
        payloads.append(
            {
                "limit": WORKDAY_SEED_PAGE_SIZE,
                "offset": 0,
                "searchText": seed_title,
            }
        )

    payloads.append(
        {
            "limit": WORKDAY_SEED_PAGE_SIZE,
            "offset": 0,
        }
    )
    return payloads


def _discover_workday_jobs(endpoint_url: str, settings: dict[str, Any]) -> list[str]:
    endpoint = safe_text(endpoint_url)
    if not endpoint:
        return []

    parsed = urlparse(endpoint)
    base_url = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    headers = {"User-Agent": "Mozilla/5.0"}

    page_response = requests.get(endpoint, timeout=20, headers=headers)
    page_response.raise_for_status()
    tenant, site_id = _extract_workday_metadata(page_response.text)
    if not tenant or not site_id:
        return []

    jobs_url = f"{base_url}/wday/cxs/{tenant}/{site_id}/jobs"
    discovered: list[str] = []
    seen_payload_keys: set[tuple[tuple[str, str], ...]] = set()
    payloads = _workday_seed_payloads(settings)
    for base_payload in payloads:
        payload_key = tuple(sorted((str(key), safe_text(value)) for key, value in base_payload.items()))
        if payload_key in seen_payload_keys:
            continue
        seen_payload_keys.add(payload_key)

        query_urls_before = len(discovered)
        total = 0
        for page_index in range(WORKDAY_SEED_MAX_PAGES):
            payload = dict(base_payload)
            payload["offset"] = page_index * WORKDAY_SEED_PAGE_SIZE
            payload["limit"] = WORKDAY_SEED_PAGE_SIZE

            jobs_response = requests.post(jobs_url, json=payload, timeout=20, headers=headers)
            jobs_response.raise_for_status()

            body = jobs_response.json()
            if not isinstance(body, dict):
                break

            postings = body.get("jobPostings", [])
            if not isinstance(postings, list) or not postings:
                break

            total = int(body.get("total", 0) or 0)

            for posting in postings:
                if not isinstance(posting, dict):
                    continue
                posting_title = safe_text(posting.get("title", ""))
                title_ok, _ = _cheap_seed_title_prefilter_from_hint(posting_title, settings)
                if not title_ok:
                    continue

                posting_location = safe_text(posting.get("locationsText", ""))
                location_ok, _ = _cheap_seed_location_prefilter_from_hint(posting_location, settings)
                if not location_ok:
                    continue

                external_path = safe_text(posting.get("externalPath", ""))
                if not external_path:
                    continue

                detail_url = _build_workday_detail_url(endpoint_url, external_path)
                if detail_url:
                    discovered.append(detail_url)

            if total and payload["offset"] + len(postings) >= total:
                break
            if not total and len(postings) < WORKDAY_SEED_PAGE_SIZE:
                break

        if len(discovered) > query_urls_before:
            break

    return list(dict.fromkeys(discovered))


def _supports_successfactors_seed_endpoint(endpoint_url: str) -> bool:
    endpoint = safe_text(endpoint_url)
    if not endpoint:
        return False

    try:
        parsed = urlparse(endpoint)
    except Exception:
        return False

    host = (parsed.netloc or "").lower()
    generic_hosts = ("successfactors.com", "sapsf.com", "ondemand.com")
    return not any(marker in host for marker in generic_hosts)


def _build_successfactors_search_url(endpoint_url: str, settings: dict[str, Any]) -> str:
    endpoint = safe_text(endpoint_url)
    if not _supports_successfactors_seed_endpoint(endpoint):
        return ""

    title = _seed_search_title(settings)

    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    remote_only = safe_text(settings.get("remote_only", "false")).lower() == "true"
    location_value = "" if remote_only else safe_text(preferred_locations[0] if preferred_locations else "")

    parsed = urlparse(endpoint)
    base_url = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    query_params: dict[str, str] = {}
    if title:
        query_params["q"] = title
    if location_value:
        query_params["locationsearch"] = location_value
    query = urlencode(query_params)
    if query:
        return f"{base_url}/search/?{query}"
    return f"{base_url}/search/"


def _supports_taleo_oracle_seed_endpoint(endpoint_url: str) -> bool:
    endpoint = safe_text(endpoint_url)
    if not endpoint:
        return False

    try:
        parsed = urlparse(endpoint)
    except Exception:
        return False

    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if "taleo.net" not in host or "/careersection/" not in path:
        return False
    return path.endswith("/jobsearch.ftl") or path.endswith("/mysearches.ftl")


def _build_taleo_search_url(endpoint_url: str, settings: dict[str, Any]) -> str:
    endpoint = safe_text(endpoint_url)
    if not _supports_taleo_oracle_seed_endpoint(endpoint):
        return ""

    title = _seed_search_title(settings)
    if not title:
        return ""

    parsed = urlparse(endpoint)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["keyword"] = title
    return urlunparse(parsed._replace(query=urlencode(query)))


def _matches_taleo_seed_title(title: str, settings: dict[str, Any]) -> bool:
    target_titles = _seed_search_title_variants(settings, max_variants=6)
    if not target_titles:
        return True

    normalized_title = normalize_text(title)
    if not normalized_title:
        return False

    for target in target_titles:
        normalized_target = normalize_text(target)
        if normalized_target and normalized_target in normalized_title:
            return True
    return False


def _matches_taleo_seed_location(location_text: str, settings: dict[str, Any]) -> bool:
    remote_only = safe_text(settings.get("remote_only", "false")).lower() == "true"
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    normalized_location = normalize_text(location_text)

    if remote_only:
        return "remote" in normalized_location

    if "remote" in normalized_location:
        return True

    if not preferred_locations:
        return True

    for location in preferred_locations:
        normalized_preferred = normalize_text(location)
        if normalized_preferred and normalized_preferred in normalized_location:
            return True
    return False


def _discover_taleo_jobs(endpoint_url: str, settings: dict[str, Any]) -> list[str]:
    search_url = _build_taleo_search_url(endpoint_url, settings)
    if not search_url:
        return []

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, timeout=20, headers=headers)
    response.raise_for_status()

    pattern = re.compile(
        r'(\d{5,})!\|!([^!]{3,}?)!\|!\1!\|!\2!\|!\1!\|!\1!\|!\1!\|!\1!\|!\1!\|!([^!]+)!\|!false!\|!!\|!!\|!!\|!!\|!([^!]+)!\|!([^!]+)!\|!(\d+)!\|!Apply!\|!',
        re.S,
    )

    discovered: list[str] = []
    for match in pattern.finditer(response.text):
        job_id = safe_text(match.group(1))
        title = html.unescape(safe_text(match.group(2)))
        location_text = html.unescape(safe_text(match.group(3)))

        if not job_id or not _matches_taleo_seed_title(title, settings):
            continue
        if not _matches_taleo_seed_location(location_text, settings):
            continue

        discovered.append(urljoin(endpoint_url, f"jobdetail.ftl?job={job_id}"))

    return list(dict.fromkeys(discovered))


def _extract_icims_search_action(page_text: str) -> str:
    match = re.search(r'action="([^"]+/jobs/search[^"]*)"', page_text, re.I)
    if not match:
        return ""
    return html.unescape(safe_text(match.group(1)))


def _extract_icims_job_links(page_text: str, base_url: str) -> list[str]:
    hits = re.findall(
        r'href="((?:https?://[^"]+)?/jobs/\d+(?:/[^"]*)?/job(?:\?[^"]*)?)"',
        page_text,
        re.I,
    )
    discovered = [urljoin(base_url, html.unescape(href)) for href in hits]
    return list(dict.fromkeys(discovered))


def _extract_generic_job_links(page_text: str, base_url: str) -> list[str]:
    hits = re.findall(r'href="((?:https?://[^"]+)?/job/[^"]+)"', page_text, re.I)
    discovered = [urljoin(base_url, html.unescape(href)) for href in hits]
    return list(dict.fromkeys(discovered))


def _extract_talentbrew_search_url(page_text: str, page_url: str) -> str:
    base_match = re.search(r"<base\s+href=\"([^\"]+)\"", page_text, re.I)
    base_url = safe_text(base_match.group(1) if base_match else "") or page_url
    href_matches = re.findall(r'href="([^"]*search-jobs[^"]*)"', page_text, re.I)
    for href in href_matches:
        return urljoin(base_url, html.unescape(href))
    if re.search(r"search-jobs", page_text, re.I):
        return urljoin(base_url, "/search-jobs")
    return ""


def _match_icims_location_value(page_text: str, settings: dict[str, Any]) -> str:
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    remote_only = safe_text(settings.get("remote_only", "false")).lower() == "true"
    if remote_only:
        return ""

    desired_locations = preferred_locations
    if not desired_locations:
        return ""

    option_matches = re.findall(
        r'<option\s+value="([^"]*)"\s*[^>]*>(.*?)</option>',
        page_text,
        re.I | re.S,
    )
    if not option_matches:
        return ""

    for desired in desired_locations:
        normalized_desired = normalize_text(desired)
        if not normalized_desired:
            continue
        for value, label in option_matches:
            normalized_label = normalize_text(html.unescape(label))
            if normalized_desired in normalized_label:
                return safe_text(value)
    return ""


def _build_icims_search_url(endpoint_url: str, settings: dict[str, Any]) -> str:
    endpoint = safe_text(endpoint_url)
    if not endpoint:
        return ""

    headers = {"User-Agent": "Mozilla/5.0"}
    candidate_pages = [endpoint]
    jobs_root = urljoin(endpoint, "/jobs")
    if jobs_root not in candidate_pages:
        candidate_pages.append(jobs_root)

    action_url = ""
    page_text = ""
    for page_url in candidate_pages:
        try:
            response = requests.get(page_url, timeout=20, headers=headers)
            response.raise_for_status()
        except requests.RequestException:
            continue

        page_text = response.text
        action_url = _extract_icims_search_action(page_text)
        if action_url:
            break

    if not action_url:
        return ""

    title = _seed_search_title(settings)

    parsed = urlparse(action_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if title:
        query["searchKeyword"] = title
        query["searchRelation"] = "keyword_all"
    location_value = _match_icims_location_value(page_text, settings)
    if location_value:
        query["searchLocation"] = location_value

    return urlunparse(parsed._replace(query=urlencode(query)))


def _discover_icims_jobs(endpoint_url: str, settings: dict[str, Any]) -> list[str]:
    headers = {"User-Agent": "Mozilla/5.0"}
    if not parse_csv_setting(settings.get("target_titles", "")):
        candidate_pages = [safe_text(endpoint_url)]
        jobs_root = urljoin(endpoint_url, "/jobs")
        if jobs_root not in candidate_pages:
            candidate_pages.append(jobs_root)

        discovered: list[str] = []
        for page_url in candidate_pages:
            try:
                response = requests.get(page_url, timeout=20, headers=headers)
                response.raise_for_status()
            except requests.RequestException:
                continue
            discovered.extend(_extract_icims_job_links(response.text, page_url))
            if not discovered:
                talentbrew_search_url = _extract_talentbrew_search_url(response.text, page_url)
                if talentbrew_search_url:
                    try:
                        search_response = requests.get(
                            talentbrew_search_url,
                            timeout=20,
                            headers=headers,
                        )
                        search_response.raise_for_status()
                    except requests.RequestException:
                        pass
                    else:
                        discovered.extend(
                            _extract_generic_job_links(
                                search_response.text,
                                talentbrew_search_url,
                            )
                        )
            if discovered:
                return list(dict.fromkeys(discovered))

    search_url = _build_icims_search_url(endpoint_url, settings)
    if not search_url:
        return []

    response = requests.get(search_url, timeout=20, headers=headers)
    response.raise_for_status()

    return _extract_icims_job_links(response.text, search_url)


def _discover_successfactors_jobs(endpoint_url: str, settings: dict[str, Any]) -> list[str]:
    search_url = _build_successfactors_search_url(endpoint_url, settings)
    if not search_url:
        return []

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, timeout=20, headers=headers)
    response.raise_for_status()

    links = re.findall(r'<a[^>]+class="[^"]*jobTitle-link[^"]*"[^>]+href="([^"]+)"', response.text, re.I)
    discovered = [urljoin(search_url, href) for href in links if "/job/" in href]
    if not discovered:
        discovered = _extract_generic_job_links(response.text, search_url)
    return list(dict.fromkeys(discovered))


def discover_job_links(*, use_ai_title_expansion: bool = True) -> dict[str, Any]:
    settings = load_settings()
    source_layer_mode = get_source_layer_mode()
    source_layer_settings = {**settings, "_source_layer_mode": source_layer_mode}
    discovery_result = discover_module.discover_urls(settings, use_ai_expansion=use_ai_title_expansion)

    output_parts: list[str] = []
    if discovery_result.get("output"):
        output_parts.append(str(discovery_result.get("output", "") or ""))

    shadow_result: dict[str, Any] | None = None
    if source_layer_mode == "shadow":
        shadow_result = run_shadow_endpoint_selection(source_layer_settings)
        shadow_output = safe_text(shadow_result.get("output", ""))
        if shadow_output:
            output_parts.append(shadow_output)
    elif source_layer_mode == "next_gen":
        shadow_result = run_shadow_endpoint_selection(source_layer_settings)
        output_parts.append(
            "Next-gen source layer mode requested. "
            "Legacy discovery remains primary for this run, and supported source-layer seed URLs will be added when available."
        )
        shadow_output = safe_text(shadow_result.get("output", ""))
        if shadow_output:
            output_parts.append(shadow_output)
        seeded_urls, seed_log_lines, supported_scanned, unsupported_skipped, seed_failures = _discover_urls_from_next_gen_seeds(
            settings=settings,
            shadow_result=shadow_result,
        )
        if seed_log_lines:
            output_parts.append("\n".join(seed_log_lines).strip())
        fallback_shadow_result: dict[str, Any] | None = None
        if not seeded_urls:
            active_count = int(shadow_result.get("active_endpoint_count", 0) or 0)
            selected_count = int(shadow_result.get("selected_endpoint_count", 0) or 0)
            if active_count > selected_count >= SHADOW_SELECTION_CAP:
                output_parts.append(
                    "Next-gen seed fallback triggered. First seed batch produced no kept URLs, so the next shadow batch will be scanned."
                )
                first_batch_endpoint_urls = [
                    safe_text(candidate.get("endpoint_url", ""))
                    for candidate in (shadow_result.get("selected_candidates", []) or [])
                    if isinstance(candidate, dict) and safe_text(candidate.get("endpoint_url", ""))
                ]
                fallback_settings = {
                    **source_layer_settings,
                    "_shadow_selection_cap": SHADOW_SELECTION_CAP,
                    "_shadow_exclude_endpoint_urls": "\n".join(first_batch_endpoint_urls),
                }
                fallback_shadow_result = run_shadow_endpoint_selection(fallback_settings)
                fallback_seeded_urls, fallback_seed_log_lines, fallback_supported_scanned, fallback_unsupported_skipped, fallback_seed_failures = _discover_urls_from_next_gen_seeds(
                    settings=settings,
                    shadow_result=fallback_shadow_result,
                )
                if fallback_seed_log_lines:
                    output_parts.append("\n".join(fallback_seed_log_lines).strip())
                seeded_urls = fallback_seeded_urls
                supported_scanned += fallback_supported_scanned
                unsupported_skipped += fallback_unsupported_skipped
                seed_failures = [*seed_failures, *fallback_seed_failures]
                discovery_result["next_gen_fallback_shadow_result"] = fallback_shadow_result
        discovery_result["next_gen_supported_seeds_scanned"] = supported_scanned
        discovery_result["next_gen_unsupported_seeds_skipped"] = unsupported_skipped
        discovery_result["next_gen_seed_failures"] = seed_failures
        if seeded_urls:
            existing_urls = discovery_result.get("all_urls", []) or []
            merged_urls = _normalize_job_posting_urls(seeded_urls + existing_urls)
            discovery_result["all_urls"] = merged_urls
            discovery_result["next_gen_seed_urls"] = _normalize_job_posting_urls(seeded_urls)
            output_parts.append(
                f"Next-gen seeds added {len(discovery_result['next_gen_seed_urls'])} URL(s) ahead of legacy results for this run."
            )
        else:
            discovery_result["next_gen_seed_urls"] = []

    discovered_urls = _normalize_job_posting_urls(discovery_result.get("all_urls", []) or [])
    discovery_result["all_urls"] = discovered_urls
    discover_module.save_output_urls(JOB_URLS_FILE, discovered_urls)

    return {
        "status": "completed",
        "output": "\n\n".join(part for part in output_parts if part).strip(),
        "job_urls_file": str(JOB_URLS_FILE),
        "url_count": len(discovered_urls),
        "urls": discovered_urls,
        "providers": {
            "greenhouse": len(discovery_result.get("greenhouse_urls", [])),
            "lever": len(discovery_result.get("lever_urls", [])),
            "search": len(discovery_result.get("search_urls", [])),
        },
        "queries": discover_module.build_google_discovery_queries(
            settings,
            use_ai_expansion=use_ai_title_expansion,
        ),
        "plan": discover_module.build_search_plan(settings),
        "drop_summary": discovery_result.get("drop_summary", {}),
        "source_layer_mode": source_layer_mode,
        "shadow_result": shadow_result or {},
        "next_gen_seed_urls": discovery_result.get("next_gen_seed_urls", []),
        "next_gen_supported_seeds_scanned": int(discovery_result.get("next_gen_supported_seeds_scanned", 0) or 0),
        "next_gen_unsupported_seeds_skipped": int(discovery_result.get("next_gen_unsupported_seeds_skipped", 0) or 0),
    }


def ingest_urls_from_file(file_path: str | Path, *, use_ai_scoring: bool = True) -> dict[str, Any]:
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

    return _build_jobs_from_urls(
        urls,
        source_name="Local Pipeline",
        source_detail=str(path.resolve()),
        use_ai_scoring=use_ai_scoring,
    )


def ingest_pasted_urls(text_value: str, *, use_ai_scoring: bool = True) -> dict[str, Any]:
    urls = parse_manual_urls(text_value)
    if MAX_URLS_PER_RUN > 0:
        urls = urls[:MAX_URLS_PER_RUN]

    MANUAL_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_URLS_FILE.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    return _build_jobs_from_urls(
        urls,
        source_name="Local Pipeline",
        source_detail=str(MANUAL_URLS_FILE.resolve()),
        use_ai_scoring=use_ai_scoring,
    )


def rescore_existing_jobs(limit: int = 0, stale_days: int = 0) -> dict[str, Any]:
    started_at = time.perf_counter()
    resume_profile_text, resume_profile_source = load_scoring_profile_text()
    stale_days = int(stale_days or 0)
    stale_policy_label = "All ages" if stale_days <= 0 else f"Older than {stale_days} days"

    if not resume_profile_text:
        output = (
            "Rescore existing jobs skipped: no saved Profile Context or fallback profile text was found.\n"
            "Add content in Settings -> Profile Context, or use profile_context.txt / JOB_AGENT_RESUME_PROFILE as fallback."
        )
        return {
            "status": "completed",
            "output": output,
            "rescored_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "changed_count": 0,
            "total_considered": 0,
        }

    matching_count = count_jobs_for_rescoring(stale_days=stale_days or None)
    rows = list_jobs_for_rescoring(limit=limit or None, stale_days=stale_days or None)
    if not rows:
        output = (
            f"AI job scoring profile: {resume_profile_source}\n\n"
            f"Rescore age filter: {stale_policy_label}\n\n"
            "No existing jobs were available to rescore."
        )
        return {
            "status": "completed",
            "output": output,
            "rescored_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "changed_count": 0,
            "total_considered": 0,
        }

    rescored_count = 0
    skipped_count = 0
    error_count = 0
    changed_count = 0
    live_refresh_count = 0
    live_refresh_error_count = 0
    output_lines = [
        f"AI job scoring profile: {resume_profile_source}",
        f"Rescore limit: {'All active jobs' if not limit else limit}",
        f"Rescore age filter: {stale_policy_label}",
        f"Existing jobs matching filter: {matching_count}",
        f"Existing jobs selected for rescore: {len(rows)}",
        "",
    ]

    for row in rows:
        payload = dict(row)
        job_id = int(payload.get("id") or 0)
        title = safe_text(payload.get("title", "")) or "Unknown title"
        company = safe_text(payload.get("company", "")) or "Unknown company"

        old_values = {
            "company": payload.get("company"),
            "title": payload.get("title"),
            "location": payload.get("location"),
            "compensation_raw": payload.get("compensation_raw"),
            "fit_score": payload.get("fit_score"),
            "fit_tier": payload.get("fit_tier"),
            "ai_priority": payload.get("ai_priority"),
            "match_rationale": payload.get("match_rationale"),
            "risk_flags": payload.get("risk_flags"),
            "application_angle": payload.get("application_angle"),
        }

        try:
            try:
                payload, refreshed = _refresh_payload_with_live_page_data(payload)
                if refreshed:
                    live_refresh_count += 1
            except Exception as refresh_exc:
                live_refresh_error_count += 1
                output_lines.append(
                    f"Live page refresh skipped: {company} | {title} | {type(refresh_exc).__name__}: {refresh_exc}"
                )

            score_result = score_accepted_job(payload, resume_profile_text)
            score_status = safe_text(score_result.get("status", "")).lower()
            if score_status != "scored":
                skipped_count += 1
                output_lines.append(f"Skipped rescore: {company} | {title} | score status: {score_status or 'unknown'}")
                continue

            apply_score_to_job_payload(payload, score_result)
            scrub_result = scrub_accepted_job(payload, resume_profile_text)
            apply_scrub_to_job_payload(payload, scrub_result)
            update_job_scoring_fields(job_id, payload, include_core_fields=True)

            rescored_count += 1

            new_values = {
                "company": payload.get("company"),
                "title": payload.get("title"),
                "location": payload.get("location"),
                "compensation_raw": payload.get("compensation_raw"),
                "fit_score": payload.get("fit_score"),
                "fit_tier": payload.get("fit_tier"),
                "ai_priority": payload.get("ai_priority"),
                "match_rationale": payload.get("match_rationale"),
                "risk_flags": payload.get("risk_flags"),
                "application_angle": payload.get("application_angle"),
            }
            if old_values != new_values:
                changed_count += 1

        except Exception as exc:
            error_count += 1
            output_lines.append(f"Rescore error: {company} | {title} | {type(exc).__name__}: {exc}")

    elapsed = time.perf_counter() - started_at
    output_lines.extend(
        [
            "",
            "Rescore summary:",
            f"- Existing jobs matching filter: {matching_count}",
            f"- Existing jobs considered: {len(rows)}",
            f"- Live page refreshes succeeded: {live_refresh_count}",
            f"- Live page refreshes failed: {live_refresh_error_count}",
            f"- Successfully rescored: {rescored_count}",
            f"- Changed after rescore: {changed_count}",
            f"- Skipped: {skipped_count}",
            f"- Errors: {error_count}",
            f"- Rescore seconds: {elapsed:.2f}",
        ]
    )

    return {
        "status": "completed",
        "output": "\n".join(output_lines).strip(),
        "rescored_count": rescored_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "changed_count": changed_count,
        "total_considered": len(rows),
    }


def discover_and_ingest(
    *,
    use_ai_title_expansion: bool = True,
    use_ai_scoring: bool = True,
) -> dict[str, Any]:
    total_started_at = time.perf_counter()
    source_layer_mode = get_source_layer_mode()

    discovery_started_at = time.perf_counter()
    discovery_result = discover_job_links(use_ai_title_expansion=use_ai_title_expansion)
    discovery_seconds = time.perf_counter() - discovery_started_at

    discovered_urls = discovery_result.get("urls", [])
    original_discovered_count = len(discovered_urls)

    if MAX_URLS_PER_RUN > 0:
        discovered_urls = discovered_urls[:MAX_URLS_PER_RUN]

    combined_output_parts = []
    if discovery_result.get("output"):
        combined_output_parts.append(discovery_result["output"])

    discovery_summary_lines = [
        f"Source layer mode: {source_layer_mode}",
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
        empty_ingest_result = {
            "accepted_jobs": 0,
            "error_count": 0,
        }
        _record_pipeline_source_layer_run(
            source_layer_mode=source_layer_mode,
            discovery_result=discovery_result,
            ingest_result=empty_ingest_result,
        )
        combined_output_parts.append(
            "No URLs were available to ingest. Review your Settings criteria, confirm discovery dependencies are installed, or try pasted URLs."
        )
        combined_output_parts.append(
            _format_source_layer_run_snapshot(
                source_layer_mode=source_layer_mode,
                discovery_result=discovery_result,
                ingest_result=empty_ingest_result,
            )
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
        use_ai_scoring=use_ai_scoring,
        seeded_job_urls=discovery_result.get("next_gen_seed_urls", []),
    )

    if ingest_result.get("output"):
        combined_output_parts.append(ingest_result["output"])

    _record_pipeline_source_layer_run(
        source_layer_mode=source_layer_mode,
        discovery_result=discovery_result,
        ingest_result=ingest_result,
    )

    combined_output_parts.append(
        _format_source_layer_run_snapshot(
            source_layer_mode=source_layer_mode,
            discovery_result=discovery_result,
            ingest_result=ingest_result,
        )
    )

    total_seconds = time.perf_counter() - total_started_at
    summary = ingest_result.get("summary", {}) if isinstance(ingest_result.get("summary", {}), dict) else {}
    run_id = int(summary.get("run_id", 0) or 0)
    if run_id:
        update_ingestion_run_details(
            run_id,
            {
                "pipeline_total_seconds": round(total_seconds, 2),
            },
        )
    combined_output_parts.append(f"Total pipeline seconds: {total_seconds:.2f}")

    return {
        "status": "completed",
        "output": "\n\n".join(combined_output_parts).strip(),
        "discovery": discovery_result,
        "ingest": ingest_result,
    }
