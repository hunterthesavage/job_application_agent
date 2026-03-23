from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any
from urllib.parse import urlparse


KNOWN_ATS_TYPES = {"Greenhouse", "Lever", "Workday", "Ashby", "SmartRecruiters"}
THIRD_PARTY_HOSTS = {
    "indeed.com",
    "linkedin.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "builtin.com",
    "wellfound.com",
    "otta.com",
    "trueup.io",
}
CAREER_PATH_HINTS = [
    "/careers",
    "/career",
    "/jobs",
    "/job",
    "/join-us",
    "/work-with-us",
]
TRUST_RANKS = {
    "": 0,
    "Unknown": 0,
    "Web Discovered": 1,
    "Third-Party Listing": 1,
    "Career Site Confirmed": 2,
    "ATS Confirmed": 3,
}
SOURCE_TYPE_RANKS = {
    "": 0,
    "Unknown": 0,
    "Web Discovery": 1,
    "Third-Party Listing": 1,
    "Company Careers": 2,
    "Company Career Site": 2,
    "ATS": 3,
}


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def hostname_for_url(url: str) -> str:
    try:
        return urlparse(safe_text(url)).netloc.lower()
    except Exception:
        return ""


def path_for_url(url: str) -> str:
    try:
        return urlparse(safe_text(url)).path or ""
    except Exception:
        return ""


def first_path_segment(url: str) -> str:
    parts = [part for part in path_for_url(url).split("/") if part]
    return parts[0] if parts else ""


def is_known_ats(ats_type: str) -> bool:
    return safe_text(ats_type) in KNOWN_ATS_TYPES


def is_third_party_listing(url: str) -> bool:
    host = hostname_for_url(url)
    return any(host.endswith(domain) for domain in THIRD_PARTY_HOSTS)


def looks_like_company_career_site(url: str) -> bool:
    if not safe_text(url):
        return False
    if is_third_party_listing(url):
        return False

    host = hostname_for_url(url)
    path = path_for_url(url).lower()

    if not host:
        return False

    return any(hint in path for hint in CAREER_PATH_HINTS)


def determine_source_type(job_url: str, ats_type: str) -> str:
    if is_known_ats(ats_type):
        return "ATS"
    if looks_like_company_career_site(job_url):
        return "Company Careers"
    if is_third_party_listing(job_url):
        return "Third-Party Listing"
    return "Web Discovery"


def determine_source_trust(job_url: str, ats_type: str) -> str:
    if is_known_ats(ats_type):
        return "ATS Confirmed"
    if looks_like_company_career_site(job_url):
        return "Career Site Confirmed"
    if is_third_party_listing(job_url):
        return "Third-Party Listing"
    return "Web Discovered"


def build_source_detail(job_url: str, ats_type: str, source_hint: str = "") -> str:
    host = hostname_for_url(job_url)
    parts: list[str] = []

    if safe_text(source_hint):
        parts.append(safe_text(source_hint))

    if is_known_ats(ats_type):
        slug = first_path_segment(job_url)
        if slug:
            parts.append(f"{safe_text(ats_type)} board: {slug}")
        else:
            parts.append(safe_text(ats_type))
    elif looks_like_company_career_site(job_url):
        parts.append("Company careers page")
    elif is_third_party_listing(job_url):
        parts.append("Third-party listing")
    else:
        parts.append("Broader web discovery")

    if host:
        parts.append(host)

    return " | ".join(part for part in parts if part)


def source_key_for_job(job_url: str, ats_type: str) -> str:
    host = hostname_for_url(job_url)
    slug = first_path_segment(job_url)

    if is_known_ats(ats_type) and slug:
        return f"{safe_text(ats_type).lower()}::{host}::{slug.lower()}"

    return host


def source_root_for_job(job_url: str, ats_type: str) -> str:
    parsed = urlparse(safe_text(job_url))
    if not parsed.scheme or not parsed.netloc:
        return safe_text(job_url)

    slug = first_path_segment(job_url)
    if is_known_ats(ats_type) and slug:
        return f"{parsed.scheme}://{parsed.netloc}/{slug}"

    return f"{parsed.scheme}://{parsed.netloc}"


def trust_rank(source_trust: str) -> int:
    return int(TRUST_RANKS.get(safe_text(source_trust), 0))


def source_type_rank(source_type: str) -> int:
    return int(SOURCE_TYPE_RANKS.get(safe_text(source_type), 0))


def choose_better_trust(existing_trust: str, new_trust: str) -> str:
    existing = safe_text(existing_trust)
    new = safe_text(new_trust)
    if trust_rank(new) > trust_rank(existing):
        return new
    return existing or new


def choose_better_source_type(existing_type: str, new_type: str) -> str:
    existing = safe_text(existing_type)
    new = safe_text(new_type)
    if source_type_rank(new) > source_type_rank(existing):
        return new
    return existing or new


def choose_better_source_detail(existing_detail: str, new_detail: str, existing_trust: str, new_trust: str) -> str:
    existing = safe_text(existing_detail)
    new = safe_text(new_detail)
    if not existing:
        return new
    if trust_rank(new_trust) > trust_rank(existing_trust) and new:
        return new
    return existing


def enrich_job_payload(job: Any, source_hint: str = "", source_detail_hint: str = "") -> dict[str, Any]:
    if is_dataclass(job):
        payload = asdict(job)
    elif isinstance(job, dict):
        payload = dict(job)
    else:
        raise TypeError("job must be a dict or dataclass instance")

    job_url = safe_text(payload.get("job_posting_url", ""))
    ats_type = safe_text(payload.get("ats_type", "Unknown")) or "Unknown"

    payload["source"] = safe_text(payload.get("source", "")) or source_hint or "Local Pipeline"
    payload["source_type"] = determine_source_type(job_url, ats_type)
    payload["source_trust"] = determine_source_trust(job_url, ats_type)
    payload["source_detail"] = source_detail_hint or build_source_detail(job_url, ats_type, source_hint=payload.get("source", ""))

    return payload
