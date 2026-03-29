from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

from services.search_plan import build_search_plan as build_structured_search_plan
from services.url_resolution import (
    choose_best_discovery_url_with_reason,
    is_discovery_only_host,
    is_likely_job_detail_url,
    is_preferred_job_host,
    resolve_candidate_url,
    resolve_discovery_url_via_page,
)


GREENHOUSE_BOARD_FILE = "greenhouse_boards.txt"
LEVER_BOARD_FILE = "lever_boards.txt"
OUTPUT_FILE = "job_urls.txt"
RUNTIME_SETTINGS_FILE = "runtime_settings.json"

MAX_GREENHOUSE_URLS = 5
MAX_LEVER_URLS = 30
MAX_SEARCH_URLS = 15

MAX_GREENHOUSE_BOARDS_TO_SCAN = 10
MAX_LEVER_BOARDS_TO_SCAN = 15
SKIP_JOBGETHER_IN_FAST_MODE = True
MAX_SEARCH_REJECTION_SAMPLES_PER_TIER = 5

ALLOWED_JOB_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "smartrecruiters.com",
]

DEFAULT_GOOGLE_DISCOVERY_QUERIES = [
    '("VP" OR "Vice President" OR "Head of" OR "Chief") ("Technology" OR "IT" OR "Information" OR "Digital" OR "Engineering" OR "Platform") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com OR site:smartrecruiters.com)',
    '("Head of AI" OR "VP AI" OR "Chief AI Officer" OR "AI Strategy" OR "Applied AI") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com)',
    '("Chief Information Officer" OR "CIO" OR "Chief Technology Officer" OR "CTO") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:smartrecruiters.com)',
    '("VP" OR "Head of") ("Platform" OR "Infrastructure" OR "Enterprise Systems" OR "Enterprise Applications" OR "Cloud") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com)',
    '("VP" OR "Head of") ("Data" OR "Analytics" OR "Machine Learning") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com)',
    '("VP" OR "Head of" OR "Chief Digital Officer") ("Transformation" OR "Digital" OR "Technology Strategy") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com)',
    '("VP" OR "Chief" OR "Head of") ("Technology" OR "Engineering" OR "IT") ("remote" OR "United States") (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com)',
]

SENIORITY_TERMS = [
    "vp",
    "vice president",
    "svp",
    "senior vice president",
    "head of",
    "chief",
    "cto",
    "cio",
    "coo",
]

STATE_ABBREVIATIONS = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}

COUNTRY_ALIASES = {
    "us": "United States",
    "u.s.": "United States",
    "usa": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "england": "United Kingdom",
}

PROVINCE_ABBREVIATIONS = {
    "alberta": "ab",
    "british columbia": "bc",
    "manitoba": "mb",
    "new brunswick": "nb",
    "newfoundland and labrador": "nl",
    "nova scotia": "ns",
    "ontario": "on",
    "prince edward island": "pe",
    "quebec": "qc",
    "saskatchewan": "sk",
    "northwest territories": "nt",
    "nunavut": "nu",
    "yukon": "yt",
}


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(value: str) -> str:
    return " ".join(safe_text(value).lower().replace("/", " ").replace("-", " ").split())


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


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for item in items:
        value = safe_text(item)
        if not value:
            continue

        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        ordered.append(value)

    return ordered


def filter_keyword_terms(keyword_terms: list[str], title_terms: list[str]) -> list[str]:
    filtered: list[str] = []

    title_tokens: set[str] = set()
    normalized_titles = [normalize_text(title) for title in title_terms]
    for normalized_title in normalized_titles:
        for token in normalized_title.split():
            if token:
                title_tokens.add(token)

    for keyword in keyword_terms:
        value = safe_text(keyword)
        normalized_keyword = normalize_text(value)
        if not normalized_keyword:
            continue

        if normalized_keyword in title_tokens:
            continue

        if any(normalized_keyword == normalized_title for normalized_title in normalized_titles):
            continue

        filtered.append(value)

    return dedupe_preserve_order(filtered)


def load_runtime_settings() -> dict[str, str]:
    path = Path(RUNTIME_SETTINGS_FILE)

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): safe_text(v) for k, v in data.items()}
    except Exception:
        return {}

    return {}


def load_board_urls(file_path: str) -> list[str]:
    urls = []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except FileNotFoundError:
        pass

    return urls


def title_has_target_seniority(title: str) -> bool:
    lowered = title.lower()
    return any(term in lowered for term in SENIORITY_TERMS)


def title_matches_settings(title: str, settings: dict[str, str]) -> bool:
    target_titles = parse_csv_text(settings.get("target_titles", ""))
    if not target_titles:
        return title_has_target_seniority(title)

    lowered = title.lower()
    return any(term.lower() in lowered for term in target_titles)



def expand_search_title_terms(
    settings: dict[str, str],
    use_ai_expansion: bool = False,
    log_lines: list[str] | None = None,
) -> list[str]:
    """
    Discovery-search-specific expansion.

    Rules:
    - Preserve the user's entered titles as the base truth.
    - Use AI only to broaden discovery query coverage.
    - Do not call AI during passive preview/render flows.
    - Fall back to the raw user titles if AI is unavailable or fails.
    """
    target_titles = parse_csv_text(settings.get("target_titles", ""))
    base_titles = dedupe_preserve_order(target_titles)

    if not base_titles:
        return []

    if not use_ai_expansion:
        return base_titles

    if suggest_titles_with_openai is None:
        if log_lines is not None:
            log_lines.append("AI title expansion unavailable: import failed.")
        return base_titles

    profile_summary = safe_text(settings.get("profile_summary", ""))
    resume_text = safe_text(settings.get("resume_text", ""))
    include_keywords = safe_text(settings.get("include_keywords", ""))

    result = suggest_titles_with_openai(
        current_titles=", ".join(base_titles),
        profile_summary=profile_summary,
        resume_text=resume_text,
        include_keywords=include_keywords,
    )

    if not result.get("ok"):
        if log_lines is not None:
            log_lines.append(f"AI title expansion not used: {safe_text(result.get('error', 'Unknown error'))}")
        return base_titles

    suggested_titles = [
        safe_text(title)
        for title in result.get("titles", [])
        if safe_text(title)
    ]

    limited_suggested_titles = suggested_titles[:4]
    combined = dedupe_preserve_order(base_titles + limited_suggested_titles)[:6]

    if log_lines is not None:
        added_count = max(0, len(combined) - len(base_titles))
        model = safe_text(result.get("model", ""))
        notes = safe_text(result.get("notes", ""))
        log_lines.append(
            f"AI title expansion applied: base {len(base_titles)} | added {added_count} | total {len(combined)}"
            + (f" | model {model}" if model else "")
        )
        if notes:
            log_lines.append(f"AI title expansion notes: {notes}")

    return combined



def _normalize_location_part(value: str) -> str:
    return " ".join(
        safe_text(value)
        .replace(",", " ")
        .replace(".", " ")
        .split()
    ).strip()


def _canonical_country(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    if normalized in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[normalized]
    if normalized in {"united states", "united kingdom", "canada"}:
        return " ".join(word.capitalize() for word in normalized.split())
    return ""


def _canonical_region(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""

    if normalized in STATE_ABBREVIATIONS:
        return STATE_ABBREVIATIONS[normalized].upper()

    if normalized in STATE_ABBREVIATIONS.values():
        return normalized.upper()

    if normalized in PROVINCE_ABBREVIATIONS:
        return PROVINCE_ABBREVIATIONS[normalized].upper()

    if normalized in PROVINCE_ABBREVIATIONS.values():
        return normalized.upper()

    return ""


def _split_location_parts(value: str) -> list[str]:
    raw = safe_text(value)
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def expand_location_query_terms(preferred_locations: list[str], remote_only: bool) -> list[str]:
    if not preferred_locations:
        return ["remote"] if remote_only else ["remote", "United States"]

    expanded: list[str] = []

    for raw_location in preferred_locations:
        location = safe_text(raw_location)
        if not location:
            continue

        parts = _split_location_parts(location)
        normalized_full = _normalize_location_part(location)

        expanded.append(location)

        if normalized_full and normalized_full.lower() != location.lower():
            expanded.append(normalized_full)

        if parts:
            city_like = parts[0]
            region_like = parts[1] if len(parts) >= 2 else ""
            country_like = parts[2] if len(parts) >= 3 else ""

            if city_like:
                expanded.append(city_like)

            canonical_region = _canonical_region(region_like)
            if city_like and canonical_region:
                expanded.append(f"{city_like} {canonical_region}")

            canonical_country = _canonical_country(country_like or region_like)
            if city_like and canonical_country:
                expanded.append(f"{city_like} {canonical_country}")

            if canonical_country:
                expanded.append(canonical_country)

            # Only add a standalone region term when the location itself is region-only.
            if canonical_region and not city_like:
                expanded.append(canonical_region)

        if remote_only:
            expanded.append("remote")
        else:
            expanded.append("remote")
            expanded.append("United States")

    return dedupe_preserve_order([safe_text(x) for x in expanded if safe_text(x)])


def build_google_discovery_queries(
    settings: dict[str, str],
    use_ai_expansion: bool = False,
    log_lines: list[str] | None = None,
) -> list[str]:
    plan = build_structured_search_plan(
        settings=settings,
        use_ai_expansion=use_ai_expansion,
    )

    if log_lines is not None:
        for note in plan.notes:
            if safe_text(note):
                log_lines.append(safe_text(note))

    return plan.queries[:12]



def build_search_plan(settings: dict[str, str]) -> list[str]:
    plan = build_structured_search_plan(
        settings=settings,
        use_ai_expansion=False,
    )

    plan_lines: list[str] = []

    if plan.base_titles:
        plan_lines.append(f"Base titles: {', '.join(plan.base_titles[:8])}")
    else:
        plan_lines.append("Base titles: none provided")

    if plan.expanded_titles:
        plan_lines.append(f"Expanded titles: {', '.join(plan.expanded_titles[:8])}")
    else:
        plan_lines.append("Expanded titles: none")

    if plan.preferred_locations:
        plan_lines.append(f"Locations: {' | '.join(plan.preferred_locations[:6])}")
    else:
        plan_lines.append(f"Locations: {'remote only' if plan.remote_only else 'no location preference'}")

    if plan.include_keywords:
        plan_lines.append(f"Include keywords: {', '.join(plan.include_keywords[:6])}")

    plan_lines.append(f"Remote only: {'true' if plan.remote_only else 'false'}")
    plan_lines.append(
        f"Search strategy: {'Broad Recall' if plan.search_strategy == 'broad_recall' else 'Balanced'}"
    )
    plan_lines.append(f"Generated queries: {len(plan.queries)}")

    return plan_lines



def discover_greenhouse_jobs(board_url: str, settings: dict[str, str]) -> list[str]:
    response = requests.get(
        board_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        title = a_tag.get_text(" ", strip=True)

        if not href or not title:
            continue

        full_url = urljoin(board_url, href)

        if "/jobs/" not in full_url:
            continue

        if not title_matches_settings(title, settings):
            continue

        links.append(full_url)

    return list(dict.fromkeys(links))


def discover_lever_jobs(board_url: str, settings: dict[str, str]) -> list[str]:
    response = requests.get(
        board_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        title = a_tag.get_text(" ", strip=True)

        if not href or not title:
            continue

        full_url = urljoin(board_url, href)

        if not title_matches_settings(title, settings):
            continue

        if "/jobs/" in full_url:
            links.append(full_url)
            continue

        board_slug = board_url.replace("https://jobs.lever.co/", "").strip("/")
        if board_slug and f"jobs.lever.co/{board_slug}/" in full_url:
            links.append(full_url)

    return list(dict.fromkeys(links))


def is_allowed_job_url(url: str) -> bool:
    lowered = url.lower()
    return any(domain in lowered for domain in ALLOWED_JOB_DOMAINS)


def classify_job_url(url: str) -> tuple[bool, str]:
    value = safe_text(url)
    if not value:
        return False, "blank_url"

    lowered = value.lower()
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = parsed.path or ""
    path_parts = [part for part in path.split("/") if part]

    blocked_substrings = [
        "?error=",
        "?keyword=",
        "/search",
        "/jobs/search",
    ]
    for marker in blocked_substrings:
        if marker in lowered:
            return False, f"blocked_pattern:{marker}"

    if not is_allowed_job_url(value):
        return False, "blocked_domain"

    if "jobs.lever.co" in host:
        return (len(path_parts) >= 2, "lever_detail" if len(path_parts) >= 2 else "lever_board_root")

    if "job-boards.greenhouse.io" in host:
        if "jobs" in path_parts and len(path_parts) >= 2:
            return True, "greenhouse_detail"
        return False, "greenhouse_board_root"

    if "boards.greenhouse.io" in host:
        if "jobs" in path_parts and len(path_parts) >= 2:
            return True, "greenhouse_detail"
        return False, "greenhouse_board_root"

    if "jobs.ashbyhq.com" in host:
        return (len(path_parts) >= 2, "ashby_detail" if len(path_parts) >= 2 else "ashby_board_root")

    if "jobs.smartrecruiters.com" in host:
        return (len(path_parts) >= 2, "smartrecruiters_detail" if len(path_parts) >= 2 else "smartrecruiters_root")

    if "myworkdayjobs.com" in host:
        return ("/job/" in path.lower(), "workday_detail" if "/job/" in path.lower() else "workday_root")

    return True, "unclassified"


def filter_discovered_urls(urls: list[str], source_name: str, log_lines: list[str] | None = None) -> tuple[list[str], dict[str, int]]:
    kept: list[str] = []
    drop_counts: dict[str, int] = {}

    for url in urls:
        keep, reason = classify_job_url(url)
        if keep:
            kept.append(url)
        else:
            drop_counts[reason] = drop_counts.get(reason, 0) + 1
            if log_lines is not None:
                log_lines.append(f"Dropped {source_name} URL: {reason} | {url}")

    return list(dict.fromkeys(kept)), drop_counts


def extract_result_url(result: dict) -> str:
    for key in ["href", "url", "link"]:
        value = result.get(key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _format_search_result_candidates(candidate_urls: list[str], limit: int = 3) -> str:
    cleaned = [safe_text(url) for url in candidate_urls if safe_text(url)]
    if not cleaned:
        return ""
    return " | ".join(cleaned[:limit])


def _log_search_result_rejection(
    *,
    tier_name: str,
    reason: str,
    raw_url: str,
    candidate_urls: list[str],
    log_lines: list[str] | None,
    rejection_counts: dict[str, int],
    rejection_samples_logged: list[int],
) -> None:
    rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    if log_lines is None:
        return

    if rejection_samples_logged[0] >= MAX_SEARCH_REJECTION_SAMPLES_PER_TIER:
        return

    parts = [f"Rejected search result [{tier_name}]: {reason}"]

    raw_value = safe_text(raw_url)
    if raw_value:
        parts.append(f"raw={raw_value}")

    candidates_text = _format_search_result_candidates(candidate_urls)
    if candidates_text:
        parts.append(f"candidates={candidates_text}")

    log_lines.append(" | ".join(parts))
    rejection_samples_logged[0] += 1


def _is_empty_search_result_error(exc: Exception) -> bool:
    message = safe_text(exc).lower()
    if not message:
        return False
    return "no results found" in message


def discover_google_style_urls(
    settings: dict[str, str],
    log_lines: list[str] | None = None,
    use_ai_expansion: bool = True,
) -> list[str]:
    if DDGS is None:
        if log_lines is not None:
            log_lines.append("DDGS package not installed, skipping Google-style discovery.")
        return []

    discovered: list[str] = []
    plan = build_structured_search_plan(settings=settings, use_ai_expansion=use_ai_expansion)

    if log_lines is not None:
        for note in plan.notes:
            if safe_text(note):
                log_lines.append(safe_text(note))

    query_tiers = plan.query_tiers or []
    if not query_tiers:
        if log_lines is not None:
            log_lines.append("No search query tiers available.")
        return []

    tier_max_results = {
        "ats_grouped": 40,
        "ats_strict": 30,
        "ats_loose": 30,
        "career_web": 20,
        "job_board_discovery": 20,
    }

    total_search_results = 0
    consecutive_search_failures = 0
    web_discovery_disabled = False

    with DDGS() as ddgs:
        for tier in query_tiers:
            tier_name = safe_text(tier.get("name", "unknown"))
            tier_label = safe_text(tier.get("label", tier_name))
            queries = tier.get("queries", []) or []
            max_results = int(tier_max_results.get(tier_name, 30))

            if web_discovery_disabled:
                if log_lines is not None:
                    log_lines.append(f"Skipping search tier [{tier_name}] because web discovery is unavailable for this run.")
                continue

            if log_lines is not None:
                log_lines.append(f"Search tier: {tier_label} | queries: {len(queries)}")

            tier_result_count = 0
            tier_url_count_before = len(discovered)
            tier_rejection_counts: dict[str, int] = {}
            tier_rejection_samples_logged = [0]

            for query in queries:
                if web_discovery_disabled:
                    break

                if log_lines is not None:
                    log_lines.append(f"Searching query [{tier_name}]: {query}")

                try:
                    results = list(ddgs.text(query, max_results=max_results))
                    result_count = len(results)
                    total_search_results += result_count
                    tier_result_count += result_count
                    consecutive_search_failures = 0

                    if log_lines is not None:
                        log_lines.append(f"Search results returned [{tier_name}]: {result_count}")

                    if result_count == 0:
                        continue

                    for result in results:
                        candidate_urls = []

                        primary_url = extract_result_url(result)
                        if primary_url:
                            candidate_urls.append(primary_url)

                        for key in ["href", "url", "link"]:
                            value = result.get(key) if isinstance(result, dict) else None
                            if value:
                                candidate_urls.append(str(value))

                        best_url, selection_reason = choose_best_discovery_url_with_reason(candidate_urls)
                        if not best_url:
                            _log_search_result_rejection(
                                tier_name=tier_name,
                                reason=selection_reason,
                                raw_url=primary_url,
                                candidate_urls=candidate_urls,
                                log_lines=log_lines,
                                rejection_counts=tier_rejection_counts,
                                rejection_samples_logged=tier_rejection_samples_logged,
                            )
                            continue

                        resolved_url, resolution_reason = resolve_candidate_url(best_url)
                        if not resolved_url:
                            _log_search_result_rejection(
                                tier_name=tier_name,
                                reason=f"resolution_{resolution_reason}",
                                raw_url=primary_url or best_url,
                                candidate_urls=candidate_urls,
                                log_lines=log_lines,
                                rejection_counts=tier_rejection_counts,
                                rejection_samples_logged=tier_rejection_samples_logged,
                            )
                            continue

                        final_url = resolved_url
                        final_reason = resolution_reason

                        if is_discovery_only_host(resolved_url):
                            if not is_likely_job_detail_url(resolved_url):
                                tier_rejection_counts["discovery_non_detail"] = (
                                    tier_rejection_counts.get("discovery_non_detail", 0) + 1
                                )
                                if log_lines is not None:
                                    log_lines.append(f"Rejected gateway URL [{tier_name}]: {resolved_url} | non-detail discovery page")
                                continue

                            upgraded_url, upgrade_reason = resolve_discovery_url_via_page(resolved_url)
                            if upgraded_url and is_preferred_job_host(upgraded_url):
                                final_url = upgraded_url
                                final_reason = f"{resolution_reason}|{upgrade_reason}"
                            else:
                                tier_rejection_counts[f"gateway_{upgrade_reason}"] = (
                                    tier_rejection_counts.get(f"gateway_{upgrade_reason}", 0) + 1
                                )
                                if log_lines is not None:
                                    log_lines.append(
                                        f"Rejected gateway URL [{tier_name}]: {resolved_url} | {upgrade_reason} | no canonical employer/ATS URL"
                                    )
                                continue

                        if log_lines is not None and final_reason != "direct":
                            log_lines.append(f"Resolved candidate URL [{tier_name}]: {final_reason} -> {final_url}")

                        discovered.append(final_url)

                except Exception as exc:
                    if _is_empty_search_result_error(exc):
                        if log_lines is not None:
                            log_lines.append(f"Search results returned [{tier_name}]: 0")
                        consecutive_search_failures = 0
                        continue

                    consecutive_search_failures += 1
                    if log_lines is not None:
                        log_lines.append(f"Search failed [{tier_name}] for query '{query}': {exc}")

                    if consecutive_search_failures >= 3:
                        web_discovery_disabled = True
                        if log_lines is not None:
                            log_lines.append(
                                "Web discovery unavailable, using ATS boards only for the rest of this run."
                            )

            tier_unique_after = len(list(dict.fromkeys(discovered)))
            tier_new_urls = max(0, tier_unique_after - tier_url_count_before)

            if log_lines is not None:
                log_lines.append(f"Tier result count [{tier_name}]: {tier_result_count}")
                log_lines.append(f"Tier unique URLs added [{tier_name}]: {tier_new_urls}")
                if tier_rejection_counts:
                    rejection_summary = ", ".join(
                        f"{reason}={count}"
                        for reason, count in sorted(
                            tier_rejection_counts.items(),
                            key=lambda item: (-item[1], item[0]),
                        )
                    )
                    log_lines.append(f"Tier rejected search results [{tier_name}]: {rejection_summary}")

    discovered = list(dict.fromkeys(discovered))

    if log_lines is not None:
        log_lines.append(f"Total search results seen: {total_search_results}")
        log_lines.append(f"Total unique search URLs kept before filtering: {len(discovered)}")

    return discovered


def save_output_urls(file_path: str | Path, urls: list[str]) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for url in urls:
            file.write(url + "\n")


def discover_urls(settings: dict[str, str] | None = None, use_ai_expansion: bool = True) -> dict:
    resolved_settings = settings or load_runtime_settings()

    log_lines: list[str] = []
    log_lines.append("Discovery plan:")
    for line in build_search_plan(resolved_settings):
        log_lines.append(f"- {line}")
    log_lines.append(f"AI title expansion: {'enabled' if use_ai_expansion else 'disabled'}")

    all_greenhouse_board_urls = load_board_urls(GREENHOUSE_BOARD_FILE)
    all_lever_board_urls = load_board_urls(LEVER_BOARD_FILE)

    greenhouse_board_urls = all_greenhouse_board_urls[:MAX_GREENHOUSE_BOARDS_TO_SCAN] if MAX_GREENHOUSE_BOARDS_TO_SCAN > 0 else all_greenhouse_board_urls

    lever_board_urls_raw = all_lever_board_urls[:MAX_LEVER_BOARDS_TO_SCAN] if MAX_LEVER_BOARDS_TO_SCAN > 0 else all_lever_board_urls

    lever_board_urls = []
    skipped_jobgether_boards = 0
    for board_url in lever_board_urls_raw:
        if SKIP_JOBGETHER_IN_FAST_MODE and "jobs.lever.co/jobgether" in board_url.lower():
            skipped_jobgether_boards += 1
            continue
        lever_board_urls.append(board_url)

    log_lines.append(
        f"Greenhouse boards available: {len(all_greenhouse_board_urls)} | scanning: {len(greenhouse_board_urls)} | skipped by cap: {max(0, len(all_greenhouse_board_urls) - len(greenhouse_board_urls))}"
    )
    log_lines.append(
        f"Lever boards available: {len(all_lever_board_urls)} | scanning candidate set: {len(lever_board_urls_raw)} | scanning after skips: {len(lever_board_urls)} | skipped by cap: {max(0, len(all_lever_board_urls) - len(lever_board_urls_raw))} | skipped jobgether: {skipped_jobgether_boards}"
    )

    greenhouse_discovered = []
    lever_discovered = []
    search_discovered = []

    for board_url in greenhouse_board_urls:
        log_lines.append(f"Checking Greenhouse board: {board_url}")
        try:
            urls = discover_greenhouse_jobs(board_url, resolved_settings)
            greenhouse_discovered.extend(urls)
            log_lines.append(f"Greenhouse URLs found: {len(urls)}")
        except Exception as exc:
            log_lines.append(f"Greenhouse board failed: {exc}")

    for board_url in lever_board_urls:
        log_lines.append(f"Checking Lever board: {board_url}")
        try:
            urls = discover_lever_jobs(board_url, resolved_settings)
            lever_discovered.extend(urls)
            log_lines.append(f"Lever URLs found: {len(urls)}")
        except Exception as exc:
            log_lines.append(f"Lever board failed: {exc}")

    search_discovered = discover_google_style_urls(
        resolved_settings,
        log_lines=log_lines,
        use_ai_expansion=use_ai_expansion,
    )

    greenhouse_discovered = list(dict.fromkeys(greenhouse_discovered))
    lever_discovered = list(dict.fromkeys(lever_discovered))
    search_discovered = list(dict.fromkeys(search_discovered))

    greenhouse_discovered, greenhouse_drop_counts = filter_discovered_urls(
        greenhouse_discovered,
        "Greenhouse",
        log_lines=log_lines,
    )
    lever_discovered, lever_drop_counts = filter_discovered_urls(
        lever_discovered,
        "Lever",
        log_lines=log_lines,
    )
    search_discovered, search_drop_counts = filter_discovered_urls(
        search_discovered,
        "Search",
        log_lines=log_lines,
    )

    greenhouse_before_cap = len(greenhouse_discovered)
    lever_before_cap = len(lever_discovered)
    search_before_cap = len(search_discovered)

    if MAX_GREENHOUSE_URLS > 0:
        greenhouse_discovered = greenhouse_discovered[:MAX_GREENHOUSE_URLS]
    if MAX_LEVER_URLS > 0:
        lever_discovered = lever_discovered[:MAX_LEVER_URLS]
    if MAX_SEARCH_URLS > 0:
        search_discovered = search_discovered[:MAX_SEARCH_URLS]

    all_urls = list(dict.fromkeys(greenhouse_discovered + lever_discovered + search_discovered))

    drop_summary = {
        "greenhouse": greenhouse_drop_counts,
        "lever": lever_drop_counts,
        "search": search_drop_counts,
    }

    log_lines.append("")
    log_lines.append(f"Greenhouse kept before cap: {greenhouse_before_cap}")
    log_lines.append(f"Lever kept before cap: {lever_before_cap}")
    log_lines.append(f"Search kept before cap: {search_before_cap}")
    log_lines.append(f"Greenhouse kept after cap: {len(greenhouse_discovered)}")
    log_lines.append(f"Lever kept after cap: {len(lever_discovered)}")
    log_lines.append(f"Search kept after cap: {len(search_discovered)}")
    log_lines.append(f"Total kept after source caps: {len(all_urls)}")
    log_lines.append(
        f"Source caps: greenhouse={MAX_GREENHOUSE_URLS}, lever={MAX_LEVER_URLS}, search={MAX_SEARCH_URLS}"
    )

    return {
        "greenhouse_urls": greenhouse_discovered,
        "lever_urls": lever_discovered,
        "search_urls": search_discovered,
        "all_urls": all_urls,
        "output": "\n".join(log_lines).strip(),
        "drop_summary": drop_summary,
    }


if __name__ == "__main__":
    settings = load_runtime_settings()
    result = discover_urls(settings)
    save_output_urls(OUTPUT_FILE, result.get("all_urls", []))
    print(result.get("output", ""))
