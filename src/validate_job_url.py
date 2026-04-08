from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from services.db import db_connection
from services.ingestion import ingest_job_records
from services.search_plan import parse_preferred_locations, parse_title_entries, resolve_include_remote
from services.source_trust import enrich_job_payload
from src.models import JobRecord, now_string


RUNTIME_SETTINGS_FILE = "runtime_settings.json"

DFW_KEYWORDS = {
    "dallas",
    "fort worth",
    "plano",
    "irving",
    "richardson",
    "frisco",
    "addison",
    "arlington",
    "southlake",
    "dfw",
}

US_STATE_CODES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia",
    "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt",
    "va", "wa", "wv", "wi", "wy", "dc",
}


def get_existing_duplicate_keys() -> set[str]:
    keys: set[str] = set()

    with db_connection() as conn:
        for table_name in ("jobs", "removed_jobs"):
            rows = conn.execute(
                f"""
                SELECT duplicate_key
                FROM {table_name}
                WHERE TRIM(COALESCE(duplicate_key, '')) <> ''
                """
            ).fetchall()
            for row in rows:
                value = safe_text(row["duplicate_key"])
                if value:
                    keys.add(value)

    return keys


def persist_job_record(job: JobRecord) -> None:
    payload = enrich_job_payload(asdict(job), source_hint="Legacy CLI")
    summary = ingest_job_records(
        job_records=[payload],
        source_name="legacy_cli_validator",
        source_detail="src.validate_job_url",
        run_type="validate_urls_legacy",
    )

    if int(summary.get("error_count", 0)) > 0:
        raise RuntimeError("Failed to persist validated job locally.")


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


COMPANY_SUFFIX_HINTS = [
    "computer",
    "technologies",
    "technology",
    "solutions",
    "systems",
    "software",
    "services",
    "health",
    "healthcare",
    "financial",
    "group",
    "holding",
    "holdings",
    "partners",
    "networks",
    "labs",
]

LEGAL_ENTITY_SUFFIXES = {
    "llc",
    "inc",
    "inc.",
    "corp",
    "corp.",
    "corporation",
    "ltd",
    "ltd.",
    "limited",
    "gmbh",
    "plc",
}

SOFT_EXPIRED_PAGE_PATTERNS = [
    "the page you are looking for doesn't exist",
    "the page you are looking for does not exist",
    "this job is no longer available",
    "job no longer available",
    "job posting no longer available",
    "this position has been filled",
    "this requisition has been filled",
    "this opportunity is no longer available",
]

SOFT_EXPIRED_PAGE_SUPPORT_MARKERS = [
    "search for jobs",
    "search jobs",
    "view all jobs",
    "back to jobs",
    "back to careers",
]


class ExpiredJobPageError(RuntimeError):
    pass


def parse_csv_text(value: str) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _raise_if_soft_expired_page(soup: BeautifulSoup, *, url: str) -> None:
    page_text = soup.get_text(" ", strip=True)
    normalized_text = re.sub(r"\s+", " ", safe_text(page_text)).lower()
    if not normalized_text:
        return

    title_text = ""
    if soup.title and soup.title.string:
        title_text = safe_text(soup.title.string).lower()

    matched_pattern = next(
        (pattern for pattern in SOFT_EXPIRED_PAGE_PATTERNS if pattern in normalized_text or pattern in title_text),
        "",
    )
    if not matched_pattern:
        return

    has_support_marker = any(marker in normalized_text for marker in SOFT_EXPIRED_PAGE_SUPPORT_MARKERS)
    if not has_support_marker and "404" not in title_text and "not found" not in title_text:
        return

    raise ExpiredJobPageError(f"Soft-expired ATS job page: {url} | {matched_pattern}")


def load_runtime_settings() -> dict[str, str]:
    path = Path(RUNTIME_SETTINGS_FILE)

    if not path.exists():
        print(f"{RUNTIME_SETTINGS_FILE} not found, using default validation behavior.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): safe_text(v) for k, v in data.items()}
    except Exception as exc:
        print(f"Failed to read {RUNTIME_SETTINGS_FILE}: {exc}")

    return {}


def detect_ats_type(url: str) -> str:
    lowered = url.lower()
    if "greenhouse.io" in lowered:
        return "Greenhouse"
    if "lever.co" in lowered:
        return "Lever"
    if "myworkdayjobs.com" in lowered or "workday" in lowered:
        return "Workday"
    if "ashbyhq.com" in lowered:
        return "Ashby"
    if "smartrecruiters.com" in lowered:
        return "SmartRecruiters"
    return "Unknown"


def normalize_title(title: str) -> str:
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def normalize_location_text(location: str) -> str:
    text = safe_text(location)
    text = re.sub(r"\s+", " ", text).strip(" -|,")
    return text


def clean_location_candidate(location: str) -> str:
    text = normalize_location_text(location)
    if not text:
        return ""

    lowered = text.lower()

    if lowered in {"location", "locations", "job location", "apply now", "share this job"}:
        return ""

    text = re.sub(r"^(location|locations)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*\|\s*.*$", "", text).strip()

    return text


def looks_like_location(text: str) -> bool:
    candidate = clean_location_candidate(text)
    if not candidate:
        return False

    lowered = candidate.lower()

    if "remote" in lowered:
        return True

    if any(city in lowered for city in DFW_KEYWORDS):
        return True

    if re.search(r"\b[a-z .'-]+,\s*[A-Z]{2}\b", candidate):
        return True

    if re.search(r"\b[A-Z][a-zA-Z .'-]+\s*-\s*[A-Z]{2}\b", candidate):
        return True

    if re.search(r"\b[A-Z][a-zA-Z .'-]+\s+Area\b", candidate):
        return True

    if re.search(r"\b[A-Z][a-zA-Z .'-]+\s+[A-Z]{2}\b", candidate):
        return True

    tokens = re.split(r"[\s,/-]+", lowered)
    if any(token in US_STATE_CODES for token in tokens):
        return True

    return False


def infer_role_family(title: str) -> str:
    t = title.lower()

    if "chief digital officer" in t:
        return "Chief Digital Officer"
    if "chief information officer" in t or re.search(r"\bcio\b", t):
        return "CIO"
    if "chief operating officer" in t or re.search(r"\bcoo\b", t):
        return "COO"
    if "head of ai" in t or "applied ai" in t:
        return "Head of AI"
    if "head of platform" in t:
        return "Head of Platform"
    if "vp" in t and "product" in t and "technology" in t:
        return "VP Product Technology"
    if "vp" in t and "it" in t:
        return "VP IT"
    if "vp" in t and "technology" in t:
        return "VP Technology"
    if "chief technology officer" in t or re.search(r"\bcto\b", t):
        return "CTO"
    if "svp" in t and "technology" in t:
        return "SVP Technology"
    if "svp" in t and "it" in t:
        return "SVP IT"
    if "head" in t:
        return "Adjacent Near-Exec"

    return "Adjacent Near-Exec"


def extract_json_ld_candidates(soup: BeautifulSoup) -> list[dict]:
    candidates = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        raw = safe_text(raw)
        if not raw:
            continue

        try:
            data = json.loads(raw)
            if isinstance(data, list):
                candidates.extend([item for item in data if isinstance(item, dict)])
            elif isinstance(data, dict):
                candidates.append(data)
        except Exception:
            continue

    return candidates


def flatten_location_value(value) -> list[str]:
    results: list[str] = []

    if value is None:
        return results

    if isinstance(value, str):
        if value.strip():
            results.append(value.strip())
        return results

    if isinstance(value, list):
        for item in value:
            results.extend(flatten_location_value(item))
        return results

    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                safe_text(address.get("addressLocality")),
                safe_text(address.get("addressRegion")),
                safe_text(address.get("addressCountry")),
            ]
            combined = ", ".join([part for part in parts if part])
            if combined:
                results.append(combined)

        parts = [
            safe_text(value.get("addressLocality")),
            safe_text(value.get("addressRegion")),
            safe_text(value.get("addressCountry")),
            safe_text(value.get("name")),
            safe_text(value.get("value")),
        ]
        combined = ", ".join([part for part in parts[:3] if part])
        if combined:
            results.append(combined)

        for key in ["jobLocation", "applicantLocationRequirements", "address", "location"]:
            if key in value:
                results.extend(flatten_location_value(value.get(key)))

        return results

    return results


def extract_location_from_json_ld(soup: BeautifulSoup) -> str:
    candidates = extract_json_ld_candidates(soup)

    for item in candidates:
        for key in ["jobLocation", "applicantLocationRequirements", "location"]:
            values = flatten_location_value(item.get(key))
            for value in values:
                cleaned = clean_location_candidate(value)
                if looks_like_location(cleaned):
                    return cleaned

    return ""


def extract_location_from_common_selectors(soup: BeautifulSoup) -> str:
    selectors = [
        {"name": "div", "attrs": {"class": re.compile(r"location", re.IGNORECASE)}},
        {"name": "span", "attrs": {"class": re.compile(r"location", re.IGNORECASE)}},
        {"name": "div", "attrs": {"data-automation-id": re.compile(r"location", re.IGNORECASE)}},
        {"name": "span", "attrs": {"data-automation-id": re.compile(r"location", re.IGNORECASE)}},
        {"name": "li", "attrs": {"class": re.compile(r"location", re.IGNORECASE)}},
        {"name": "p", "attrs": {"class": re.compile(r"location", re.IGNORECASE)}},
    ]

    for selector in selectors:
        for tag in soup.find_all(selector["name"], attrs=selector["attrs"]):
            text = clean_location_candidate(tag.get_text(" ", strip=True))
            if looks_like_location(text):
                return text

    return ""


def extract_location_from_label_patterns(soup: BeautifulSoup) -> str:
    visible_text = soup.get_text("\n", strip=True)
    patterns = [
        r"Location\s*[:\-]\s*([^\n|]{3,80})",
        r"Locations\s*[:\-]\s*([^\n|]{3,120})",
        r"Job Location\s*[:\-]\s*([^\n|]{3,80})",
        r"Primary Location\s*[:\-]\s*([^\n|]{3,80})",
    ]

    for pattern in patterns:
        match = re.search(pattern, visible_text, re.IGNORECASE)
        if match:
            candidate = clean_location_candidate(match.group(1))
            if looks_like_location(candidate):
                return candidate

    return ""


def extract_title_from_json_ld(soup: BeautifulSoup) -> str:
    candidates = extract_json_ld_candidates(soup)
    for item in candidates:
        title = safe_text(item.get("title") or item.get("name"))
        if title:
            return title
    return ""


def _flatten_company_candidate(value) -> list[str]:
    results: list[str] = []

    if value is None:
        return results

    if isinstance(value, str):
        text = safe_text(value)
        if text:
            results.append(text)
        return results

    if isinstance(value, list):
        for item in value:
            results.extend(_flatten_company_candidate(item))
        return results

    if isinstance(value, dict):
        for key in ["name", "legalName", "alternateName", "@id", "value"]:
            text = safe_text(value.get(key))
            if text:
                results.append(text)
        return results

    return results


def _clean_company_candidate(value: str) -> str:
    text = safe_text(value)
    text = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[/#?].*$", "", text).strip()
    if re.search(r"\sat\s", text, flags=re.IGNORECASE):
        parts = [part.strip(" -|,()") for part in re.split(r"\sat\s", text, flags=re.IGNORECASE) if part.strip()]
        if len(parts) >= 2:
            text = parts[-1]
    text = re.sub(r"\s+", " ", text).strip(" -|,")
    return text


def _looks_generic_company_label(value: str) -> bool:
    cleaned = _clean_company_candidate(value)
    lowered = cleaned.lower()
    if not cleaned:
        return True

    generic_values = {
        "greenhouse",
        "greenhouse job board",
        "job board",
        "jobs",
        "careers",
        "workday",
        "myworkdayjobs",
        "smartrecruiters",
        "lever",
        "ashby",
        "page_title",
        "page title",
    }
    if lowered in generic_values:
        return True

    if "job board" in lowered or "careers" == lowered:
        return True

    if any(token in lowered for token in ["remote", "work from anywhere", "united states"]):
        return True

    generic_role_patterns = [
        r"\banalyst\b",
        r"\bengineer\b",
        r"\bmanager\b",
        r"\bdirector\b",
        r"\bvice president\b",
        r"\bsvp\b",
    ]
    if any(re.search(pattern, lowered) for pattern in generic_role_patterns):
        return True

    return False


def _looks_like_legal_entity_name(value: str) -> bool:
    tokens = re.split(r"[\s,]+", _clean_company_candidate(value).lower())
    return any(token in LEGAL_ENTITY_SUFFIXES for token in tokens if token)


def choose_best_company_name(extracted_company: str, fallback_company: str, url: str) -> str:
    cleaned_extracted = _clean_company_candidate(extracted_company)
    cleaned_fallback = _clean_company_candidate(fallback_company)
    hostname = (urlparse(url).hostname or "").lower()

    if cleaned_extracted and not _looks_generic_company_label(cleaned_extracted):
        if "myworkdayjobs.com" in hostname and cleaned_fallback:
            if _looks_like_legal_entity_name(cleaned_extracted):
                return cleaned_fallback
        return cleaned_extracted

    return cleaned_fallback or cleaned_extracted


def extract_company_from_json_ld(soup: BeautifulSoup) -> str:
    candidates = extract_json_ld_candidates(soup)

    for item in candidates:
        for key in ["hiringOrganization", "organization", "publisher", "company"]:
            values = _flatten_company_candidate(item.get(key))
            for value in values:
                cleaned = _clean_company_candidate(value)
                if cleaned and not _looks_generic_company_label(cleaned):
                    return cleaned

    return ""


def extract_company_from_meta(soup: BeautifulSoup) -> str:
    meta_candidates = [
        soup.find("meta", attrs={"property": "og:site_name"}),
        soup.find("meta", attrs={"name": "application-name"}),
        soup.find("meta", attrs={"name": "apple-mobile-web-app-title"}),
    ]

    for tag in meta_candidates:
        if tag and tag.get("content"):
            cleaned = _clean_company_candidate(tag.get("content"))
            if cleaned and not _looks_generic_company_label(cleaned):
                return cleaned

    if soup.title and soup.title.string:
        title_text = safe_text(soup.title.string)
        job_application_match = re.search(
            r"Job Application for .+? at (?P<company>.+)$",
            title_text,
            re.IGNORECASE,
        )
        if job_application_match:
            cleaned = _clean_company_candidate(job_application_match.group("company"))
            if cleaned and not _looks_generic_company_label(cleaned):
                return cleaned

        parts = [part.strip() for part in re.split(r"\s[-|]\s", title_text) if part.strip()]
        for part in reversed(parts):
            cleaned = _clean_company_candidate(part)
            if cleaned and not _looks_generic_company_label(cleaned):
                return cleaned

    return ""


def extract_location_from_meta(soup: BeautifulSoup) -> str:
    meta_candidates = [
        soup.find("meta", attrs={"name": "keywords"}),
        soup.find("meta", attrs={"property": "og:description"}),
        soup.find("meta", attrs={"name": "description"}),
    ]

    patterns = [
        r"\b([A-Z][a-zA-Z .'-]+),\s*([A-Z]{2})\b",
        r"\b(Remote(?:,\s*United States)?)\b",
    ]

    for tag in meta_candidates:
        content = safe_text(tag.get("content")) if tag else ""
        if not content:
            continue
        for pattern in patterns:
            match = re.search(pattern, content)
            if not match:
                continue
            candidate = clean_location_candidate(match.group(0))
            if looks_like_location(candidate):
                return candidate

    return ""


def parse_greenhouse_page(url: str) -> tuple[str, str, str, str, str]:
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    _raise_if_soft_expired_page(soup, url=response.url)

    final_url = response.url

    title = ""
    location = ""
    company = ""

    title_tag = soup.find("h1")
    if title_tag:
        title = title_tag.get_text(" ", strip=True)

    location_tag = soup.find("div", class_="location")
    if location_tag:
        location = clean_location_candidate(location_tag.get_text(" ", strip=True))

    if not title:
        title = extract_title_from_json_ld(soup)

    if not location:
        location = extract_location_from_json_ld(soup)

    if not location:
        location = extract_location_from_common_selectors(soup)

    if not location:
        location = extract_location_from_label_patterns(soup)

    if not location:
        location = extract_location_from_meta(soup)

    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    company = extract_company_from_json_ld(soup)
    if not company:
        company = extract_company_from_meta(soup)

    text = soup.get_text(" ", strip=True)
    return title, location, text, final_url, company


def _humanize_url_slug(value: str) -> str:
    text = safe_text(unquote(value))
    if not text:
        return ""

    text = re.sub(r"_[A-Za-z0-9-]+$", "", text).strip()
    text = text.replace("---", " ")
    text = text.replace("--", " ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip(" -|,")
    return text


def _looks_like_location_slug(value: str) -> bool:
    text = _humanize_url_slug(value)
    lowered = text.lower()
    if not text:
        return False

    if lowered in {"remote us", "remote united states", "remote"}:
        return True

    if re.search(r"\b[A-Za-z .'-]+\s+[A-Za-z]{2}\b", text):
        return True

    return any(city in lowered for city in DFW_KEYWORDS)


def _format_location_slug(value: str) -> str:
    text = _humanize_url_slug(value)
    lowered = text.lower()
    if not text:
        return ""

    if lowered in {"remote us", "remote united states"}:
        return "Remote, United States"
    if lowered == "remote":
        return "Remote"

    match = re.search(r"^(?P<city>[A-Za-z .'-]+)\s+(?P<region>[A-Za-z]{2})$", text)
    if match:
        return f"{match.group('city').strip()}, {match.group('region').strip().upper()}"

    return text


def extract_workday_fallback_from_url(url: str) -> tuple[str, str]:
    try:
        parsed = urlparse(safe_text(url))
    except Exception:
        return "", ""

    path_parts = [part for part in parsed.path.split("/") if safe_text(part)]
    if not path_parts:
        return "", ""

    try:
        job_index = next(index for index, part in enumerate(path_parts) if part.lower() == "job")
    except StopIteration:
        return "", ""

    tail_parts = path_parts[job_index + 1 :]
    if not tail_parts:
        return "", ""

    ignored = {"apply", "applymanually", "usemylastapplication", "external", "en-us", "en", "us"}
    filtered = [part for part in tail_parts if part.lower() not in ignored]
    if not filtered:
        return "", ""

    title = _humanize_url_slug(filtered[-1])
    location = ""
    if len(filtered) >= 2 and _looks_like_location_slug(filtered[-2]):
        location = _format_location_slug(filtered[-2])

    return title, location


def parse_page(url: str) -> tuple[str, str, str, str, str]:
    if "greenhouse.io" in url.lower():
        return parse_greenhouse_page(url)

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    _raise_if_soft_expired_page(soup, url=response.url)

    title = ""
    location = ""
    company = ""

    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    meta_title = soup.find("meta", attrs={"property": "og:title"})
    if not title and meta_title and meta_title.get("content"):
        title = meta_title["content"].strip()

    if not title:
        title = extract_title_from_json_ld(soup)

    location = extract_location_from_json_ld(soup)

    if not location:
        location = extract_location_from_common_selectors(soup)

    if not location:
        location = extract_location_from_label_patterns(soup)

    if not location:
        location = extract_location_from_meta(soup)

    lowered_url = url.lower()
    if "myworkdayjobs.com" in lowered_url or "workday" in lowered_url:
        fallback_title, fallback_location = extract_workday_fallback_from_url(response.url)
        if not title:
            title = fallback_title
        if not location:
            location = fallback_location

    company = extract_company_from_json_ld(soup)
    if not company:
        company = extract_company_from_meta(soup)

    text = soup.get_text(" ", strip=True)
    return title, location, text, response.url, company


def infer_company_from_domain(url: str) -> str:
    def _prettify_company_slug(slug: str) -> str:
        base = safe_text(slug).replace("-", " ").replace("_", " ")
        base = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base)
        base = re.sub(r"\s+", " ", base).strip()

        lowered = base.lower().replace(" ", "")
        for suffix in COMPANY_SUFFIX_HINTS:
            if lowered.endswith(suffix) and lowered != suffix:
                prefix = lowered[: -len(suffix)]
                if prefix:
                    return f"{prefix.title()} {suffix.title()}"

        return base.title() or "Unknown"

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").replace("www.", "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if "greenhouse.io" in hostname:
        if path_parts:
            return path_parts[0].replace("-", " ").title()

    if "lever.co" in hostname:
        if path_parts:
            return path_parts[0].replace("-", " ").title()

    if "ashbyhq.com" in hostname:
        if path_parts:
            return path_parts[0].replace("-", " ").title()

    if "smartrecruiters.com" in hostname:
        if path_parts:
            return path_parts[0].replace("-", " ").title()

    workday_match = re.match(r"^(?P<tenant>[^.]+)\.wd\d+\.myworkdayjobs\.com$", hostname)
    if workday_match:
        return _prettify_company_slug(workday_match.group("tenant"))

    parts = hostname.split(".")
    if len(parts) >= 2:
        return parts[-2].replace("-", " ").title()

    return hostname.replace("-", " ").title() or "Unknown"


def infer_location(text: str) -> str:
    lowered = text.lower()
    hybrid_markers = [
        "hybrid",
        "remote/in-office",
        "in-office schedule",
        "work from our",
        "days a week",
        "days per week",
        "office at least",
        "open to candidates in the",
    ]
    has_hybrid_signal = any(marker in lowered for marker in hybrid_markers)

    hybrid_patterns = [
        r"open to candidates in the\s+([A-Z][a-zA-Z .'-]+),\s*([A-Z]{2})\s+area",
        r"based in\s+([A-Z][a-zA-Z .'-]+),\s*([A-Z]{2})",
        r"located in\s+([A-Z][a-zA-Z .'-]+),\s*([A-Z]{2})",
    ]
    if has_hybrid_signal:
        for pattern in hybrid_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1).strip()}, {match.group(2).strip().upper()}"

    match = re.search(r"\b([A-Z][a-zA-Z .'-]+),\s*([A-Z]{2})\b", text)
    if has_hybrid_signal and match:
        return f"{match.group(1).strip()}, {match.group(2).strip()}"

    match = re.search(r"\b([A-Z][a-zA-Z .'-]+)\s*-\s*([A-Z]{2})\b", text)
    if has_hybrid_signal and match:
        return f"{match.group(1).strip()}, {match.group(2).strip()}"

    if "remote" in lowered and "united states" in lowered:
        return "Remote, United States"

    if "remote" in lowered:
        return "Remote"

    match = re.search(r"\b([A-Z][a-zA-Z .'-]+),\s*([A-Z]{2})\b", text)
    if match:
        return f"{match.group(1).strip()}, {match.group(2).strip()}"

    match = re.search(r"\b([A-Z][a-zA-Z .'-]+)\s*-\s*([A-Z]{2})\b", text)
    if match:
        return f"{match.group(1).strip()}, {match.group(2).strip()}"

    for city in DFW_KEYWORDS:
        if city in lowered:
            return city.title()

    return "Unknown"


def infer_remote_type(location: str, text: str = "") -> str:
    lowered = f"{location} {text}".lower()

    if any(
        marker in lowered
        for marker in [
            "hybrid",
            "remote/in-office",
            "in-office schedule",
            "office at least",
            "days a week",
            "days per week",
        ]
    ):
        return "Hybrid"

    if "remote" in lowered:
        return "Fully Remote"

    location_lowered = location.lower()
    if any(city in location_lowered for city in DFW_KEYWORDS):
        return "Dallas / DFW"

    return "Other"


def infer_dfw_match(location: str) -> str:
    lowered = location.lower()
    if any(city in lowered for city in DFW_KEYWORDS):
        return "Yes"
    if "remote" in lowered:
        return "Yes"
    return "No"


def infer_validation_status(title: str, location: str, text: str = "") -> tuple[str, str]:
    """
    Lightweight parse-quality signal, not final acceptance policy.

    This answers:
    - Did we extract a plausible title?
    - Did we extract a plausible location or remote signal?

    Final candidate acceptance belongs to pipeline_runtime.py.
    """
    normalized = normalize_title(title)
    valid_title = len(normalized) > 3
    valid_location = infer_remote_type(location, text) in {"Fully Remote", "Dallas / DFW", "Hybrid"} or location == "Unknown"

    if valid_title and valid_location:
        return "Validated", "Medium"

    if valid_title or valid_location:
        return "Review Needed", "Low"

    return "Rejected", "Low"


def extract_compensation(text: str) -> tuple[str, str]:
    match = re.search(r"\$\d[\d,]*\s*(?:-|to)\s*\$\d[\d,]*", text, re.IGNORECASE)
    if match:
        raw = match.group(0).strip()
        return raw, evaluate_compensation_status(raw)

    match = re.search(r"\$\d[\d,]*K\s*(?:-|to)\s*\$\d[\d,]*K", text, re.IGNORECASE)
    if match:
        raw = match.group(0).strip()
        return raw, evaluate_compensation_status(raw)

    match = re.search(
        r"Salary Range:\s*\$?\d[\d,]*(?:\.\d+)?\s*(?:-|to)\s*\$?\d[\d,]*(?:\.\d+)?",
        text,
        re.IGNORECASE,
    )
    if match:
        raw = match.group(0).split(":", 1)[-1].strip()
        return raw, evaluate_compensation_status(raw)

    return "", "Not Disclosed"


def parse_salary_number(value: str) -> int | None:
    value = value.upper().replace(",", "").replace("$", "").strip()

    multiplier = 1
    if value.endswith("K"):
        multiplier = 1000
        value = value[:-1].strip()

    try:
        return int(float(value) * multiplier)
    except ValueError:
        return None


def evaluate_compensation_status(comp_text: str) -> str:
    numbers = re.findall(r"\$?\d[\d,]*(?:\.\d+)?K?", comp_text, re.IGNORECASE)
    parsed = [parse_salary_number(n) for n in numbers]
    parsed = [n for n in parsed if n is not None]

    if not parsed:
        return "Unclear"

    max_comp = max(parsed)

    if max_comp < 250000:
        return "Below Target"

    return "Qualified"


def rough_fit_score(title: str, location: str, url: str, text: str) -> tuple[int, str, str]:
    """
    Lightweight descriptive fit signal for the record.

    This is not the final acceptance engine. Final policy belongs in
    services/pipeline_runtime.py.
    """
    score = 0
    reasons = []
    risks = []

    role_family = infer_role_family(title)
    remote_type = infer_remote_type(location, text)
    ats_type = detect_ats_type(url)
    lowered_text = text.lower()

    strong_roles = {
        "VP Technology",
        "VP IT",
        "CIO",
        "COO",
        "Head of AI",
        "Head of Platform",
        "VP Product Technology",
        "Chief Digital Officer",
        "CTO",
        "SVP Technology",
        "SVP IT",
    }

    if role_family in strong_roles:
        score += 25
        reasons.append(f"Strong title alignment: {role_family}")
    else:
        score += 12
        reasons.append("Adjacent near-executive role")

    if "ai" in lowered_text or "artificial intelligence" in lowered_text:
        score += 20
        reasons.append("AI relevance detected in posting")
    else:
        score += 5
        risks.append("AI relevance not clearly stated")

    if remote_type == "Fully Remote":
        score += 15
        reasons.append("Fully remote role")
    elif remote_type == "Dallas / DFW":
        score += 12
        reasons.append("Dallas / DFW role")
    else:
        risks.append("Location may not fit target geography")

    if ats_type != "Unknown":
        score += 10
        reasons.append(f"Recognized ATS: {ats_type}")

    if "vice president" in lowered_text or "chief" in lowered_text or "head of" in lowered_text:
        score += 10
        reasons.append("Leadership scope language detected")

    if "platform" in lowered_text or "technology" in lowered_text or "digital" in lowered_text or "it " in lowered_text:
        score += 10
        reasons.append("Technology/platform scope detected")

    if score >= 85:
        tier = "Top Priority"
    elif score >= 75:
        tier = "Strong"
    elif score >= 65:
        tier = "Review"
    else:
        tier = "Low"

    if not risks:
        risks.append("No major risks identified")

    rationale = "; ".join(reasons[:4])
    risk_flags = "; ".join(risks[:3])

    return min(score, 100), tier, rationale + " | Risks: " + risk_flags


def infer_parse_confidence(title: str, location: str, company: str) -> str:
    score = 0

    if len(normalize_title(title)) > 3:
        score += 1

    cleaned_location = clean_location_candidate(location)
    if cleaned_location and cleaned_location != "Unknown":
        score += 1

    if safe_text(company) and safe_text(company).lower() != "unknown":
        score += 1

    if score >= 3:
        return "High"
    if score == 2:
        return "Medium"
    return "Low"


def build_duplicate_key(company: str, title: str, location: str, req_id: str = "") -> str:
    company_part = re.sub(r"[^a-z0-9]", "", company.lower())
    title_part = re.sub(r"[^a-z0-9]", "", normalize_title(title))
    location_part = re.sub(r"[^a-z0-9]", "", location.lower())
    req_part = re.sub(r"[^a-z0-9]", "", req_id.lower())
    return f"{company_part}|{title_part}|{location_part}|{req_part}"


def create_job_record(job_url: str) -> JobRecord:
    """
    Parser-first record creation.

    This function should extract and infer structured fields from a URL and page.
    Final accept/reject policy should live in services/pipeline_runtime.py.
    """
    title, extracted_location, text, final_url, extracted_company = parse_page(job_url)

    company = choose_best_company_name(
        extracted_company=extracted_company,
        fallback_company=infer_company_from_domain(final_url),
        url=final_url,
    )
    location = clean_location_candidate(extracted_location) if extracted_location.strip() else infer_location(text)
    if not location:
        location = infer_location(text)

    remote_type = infer_remote_type(location)
    dallas_dfw_match = infer_dfw_match(location)
    ats_type = detect_ats_type(final_url)
    role_family = infer_role_family(title)
    normalized_title = normalize_title(title)

    validation_status, validation_confidence = infer_validation_status(title, location, text)
    fit_score, fit_tier, rationale_with_risks = rough_fit_score(title, location, final_url, text)
    parse_confidence = infer_parse_confidence(title, location, company)

    compensation_raw, compensation_status = extract_compensation(text)
    ai_priority = "High" if "ai" in text.lower() else "Medium"
    risk_flags = []
    if compensation_status == "Not Disclosed":
        risk_flags.append("Compensation not disclosed")
    if parse_confidence == "Low":
        risk_flags.append("Low parse confidence")

    application_angle = (
        "Emphasize enterprise technology leadership, transformation experience, "
        "and ability to align strategy with execution."
    )
    cover_letter_starter = (
        "I’m excited about this opportunity because it aligns with my background "
        "leading enterprise technology and transformation initiatives. "
        "My experience driving strategic execution, platform modernization, and "
        "cross-functional leadership would translate well to this role."
    )

    duplicate_key = build_duplicate_key(company, title, location)

    now = now_string()

    return JobRecord(
        date_found=now,
        date_last_validated=now,
        company=company,
        title=title,
        role_family=role_family,
        normalized_title=normalized_title,
        location=location,
        remote_type=remote_type,
        dallas_dfw_match=dallas_dfw_match,
        company_careers_url=final_url,
        job_posting_url=final_url,
        ats_type=ats_type,
        requisition_id="",
        source="Manual URL Test",
        compensation_raw=compensation_raw,
        compensation_status=compensation_status,
        validation_status=validation_status,
        validation_confidence=validation_confidence,
        fit_score=fit_score,
        fit_tier=fit_tier,
        ai_priority=ai_priority,
        match_rationale=rationale_with_risks,
        risk_flags="; ".join(risk_flags),
        application_angle=application_angle,
        description_text=text,
        cover_letter_starter=cover_letter_starter,
        status="New",
        duplicate_key=duplicate_key,
        active_status="Active",
    )


def load_job_urls_from_file(file_path: str) -> list[str]:
    urls = []

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    return urls


# ---------------------------------------------------------------------------
# Legacy CLI-only gates below
# ---------------------------------------------------------------------------
# These are retained for backwards compatibility with the standalone CLI flow.
# The app’s main acceptance policy should live in services/pipeline_runtime.py.
# ---------------------------------------------------------------------------

def passes_seniority_gate(title: str) -> bool:
    lowered = title.lower()
    seniority_terms = [
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
    return any(term in lowered for term in seniority_terms)


def passes_domain_gate(title: str) -> bool:
    lowered = title.lower()
    domain_terms = [
        "technology",
        "it",
        "information",
        "digital",
        "platform",
        "ai",
        "artificial intelligence",
        "product technology",
        "enterprise systems",
        "enterprise applications",
        "business technology",
        "business systems",
        "information security",
        "cybersecurity",
        "security",
        "data",
        "machine learning",
        "ml",
        "applications",
        "infrastructure",
        "engineering platform",
    ]
    return any(term in lowered for term in domain_terms)


def passes_strict_title_gate(title: str) -> bool:
    lowered = title.lower()

    rejected_terms = [
        "director",
        "senior director",
        "manager",
        "principal",
        "lead",
        "staff ",
        "counsel",
        "recruiting",
        "sales",
        "tax",
        "design",
        "safety",
    ]
    if any(term in lowered for term in rejected_terms):
        return False

    return passes_seniority_gate(title) and passes_domain_gate(title)


def passes_settings_title_gate(title: str, settings: dict[str, str]) -> bool:
    target_titles = parse_title_entries(settings.get("target_titles", ""))
    if not target_titles:
        return True

    lowered = title.lower()
    return any(term.lower() in lowered for term in target_titles)


def passes_strict_location_gate(location: str) -> bool:
    remote_type = infer_remote_type(location)

    if remote_type in {"Fully Remote", "Dallas / DFW"}:
        return True

    if location == "Unknown":
        return True

    return False


def passes_settings_location_gate(location: str, settings: dict[str, str]) -> bool:
    preferred_locations = parse_preferred_locations(settings.get("preferred_locations", ""))
    remote_only = settings.get("remote_only", "false").lower() == "true"
    include_remote = resolve_include_remote(settings)

    lowered = location.lower()

    if remote_only:
        if "remote" in lowered:
            return True
        if location == "Unknown":
            return True
        return False

    if include_remote and "remote" in lowered:
        return True

    if preferred_locations:
        if any(term.lower() in lowered for term in preferred_locations):
            return True
        return False

    if "remote" in lowered and not include_remote:
        return False

    return True


def passes_settings_exclude_gate(title: str, company: str, location: str, text: str, settings: dict[str, str]) -> bool:
    exclude_keywords = parse_csv_text(settings.get("exclude_keywords", ""))
    if not exclude_keywords:
        return True

    searchable_text = " ".join([title, company, location, text]).lower()
    return not any(keyword.lower() in searchable_text for keyword in exclude_keywords)


def main() -> None:
    settings = load_runtime_settings()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.validate_job_url <job_url_1> [job_url_2] ...")
        print("  python -m src.validate_job_url --file job_urls.txt")
        sys.exit(1)

    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print("Please provide a file path after --file")
            sys.exit(1)
        job_urls = load_job_urls_from_file(sys.argv[2])
    else:
        job_urls = sys.argv[1:]

    existing_keys = get_existing_duplicate_keys()

    added_count = 0
    skipped_count = 0
    error_count = 0

    duplicate_skip_count = 0
    title_skip_count = 0
    location_skip_count = 0
    validation_skip_count = 0
    compensation_skip_count = 0
    expired_skip_count = 0
    settings_skip_count = 0

    print("Running legacy CLI validation flow.")
    print("App acceptance policy is now expected to live primarily in services/pipeline_runtime.py.")

    for job_url in job_urls:
        print(f"\nProcessing: {job_url}")

        try:
            job = create_job_record(job_url)

            if job.duplicate_key in existing_keys:
                print("Skipped duplicate job.")
                print(f"Duplicate Key: {job.duplicate_key}")
                skipped_count += 1
                duplicate_skip_count += 1
                continue

            target_titles = []
            if settings:
                target_titles = [str(t).strip() for t in settings.get("target_titles", []) if str(t).strip()]

            if target_titles:
                if not passes_settings_title_gate(job.title, settings):
                    print("Skipped job due to settings title targeting.")
                    print(f"Title: {job.title}")
                    skipped_count += 1
                    settings_skip_count += 1
                    continue
            else:
                if not passes_strict_title_gate(job.title):
                    print("Skipped job due to title gate.")
                    print(f"Title: {job.title}")
                    skipped_count += 1
                    title_skip_count += 1
                    continue

            if not passes_strict_location_gate(job.location):
                print("Skipped job due to location gate.")
                print(f"Location: {job.location}")
                skipped_count += 1
                location_skip_count += 1
                continue

            if not passes_settings_location_gate(job.location, settings):
                print("Skipped job due to settings location targeting.")
                print(f"Location: {job.location}")
                skipped_count += 1
                settings_skip_count += 1
                continue

            if not passes_settings_exclude_gate(job.title, job.company, job.location, job.match_rationale, settings):
                print("Skipped job due to exclude keywords.")
                print(f"Title: {job.title}")
                skipped_count += 1
                settings_skip_count += 1
                continue

            if job.validation_status != "Validated":
                print("Skipped job due to validation status.")
                print(f"Validation Status: {job.validation_status}")
                skipped_count += 1
                validation_skip_count += 1
                continue

            if job.compensation_status == "Below Target":
                print("Skipped job due to compensation below target.")
                print(f"Compensation: {job.compensation_raw}")
                skipped_count += 1
                compensation_skip_count += 1
                continue

            if job.fit_score < 65:
                print("Skipped job due to fit score below threshold.")
                print(f"Fit Score: {job.fit_score}")
                skipped_count += 1
                continue

            persist_job_record(job)
            existing_keys.add(job.duplicate_key)

            print("Job processed successfully.")
            print(f"Company: {job.company}")
            print(f"Title: {job.title}")
            print(f"Location: {job.location}")
            print(f"Validation: {job.validation_status}")
            print(f"Validation Confidence: {job.validation_confidence}")
            print(f"Fit Score: {job.fit_score}")

            added_count += 1

        except Exception as exc:
            error_text = str(exc).lower()

            if any(x in error_text for x in [
                "404",
                "not found",
                "no longer available",
                "410",
                "500",
                "internal server error",
                "read timed out",
                "timeout",
            ]):
                print("Skipped dead, blocked, expired, or timed-out job.")
                skipped_count += 1
                expired_skip_count += 1
            else:
                print(f"Error processing job URL: {exc}")
                error_count += 1

    print("\nRun complete.")
    print(f"Added: {added_count}")
    print(f"Skipped total: {skipped_count}")
    print(f"  Duplicates: {duplicate_skip_count}")
    print(f"  Title gate: {title_skip_count}")
    print(f"  Location gate: {location_skip_count}")
    print(f"  Validation: {validation_skip_count}")
    print(f"  Compensation: {compensation_skip_count}")
    print(f"  Settings-driven filters: {settings_skip_count}")
    print(f"  Expired/dead: {expired_skip_count}")
    print(f"Errors: {error_count}")


if __name__ == "__main__":
    main()
