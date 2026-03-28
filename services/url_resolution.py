from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PREFERRED_JOB_HOST_MARKERS = [
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "recruiting.paylocity.com",
    "jobs.jobvite.com",
    "jobs.icims.com",
    "taleo.net",
    "careers.bamboohr.com",
    "paycomonline.net",
    "adp.com",
]

DISCOVERY_ONLY_HOST_MARKERS = [
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "trueup.io",
    "otta.com",
    "wellfound.com",
    "arcussearch.com",
]

COMMON_REDIRECT_QUERY_KEYS = [
    "url",
    "u",
    "target",
    "dest",
    "destination",
    "redirect",
    "redirect_url",
]

BLOCKED_DISCOVERY_PATH_MARKERS = [
    "/jobs/search",
    "/jobs-",
    "/q-",
    "/cmp/",
    "/companies/",
    "/company/",
    "/salaries",
    "/salary",
    "/career-advice",
    "/career",
    "/community",
    "/communities",
    "/overview",
    "/reviews",
    "/interviews",
    "/profile/",
    "/profiles/",
    "/hiring/page/",
    "/hiring/companies/",
    "/job-alert",
    "/job-alerts",
]

DETAIL_PATH_HINTS = [
    "/jobs/view/",
    "/viewjob",
    "/job/",
    "/jobs/",
    "/position/",
    "/positions/",
    "/opportunity/",
    "/opportunities/",
    "/role/",
    "/roles/",
    "/vacancy/",
    "/vacancies/",
]


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_url(url: str) -> str:
    raw = safe_text(url)
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or ""
        while "//" in path:
            path = path.replace("//", "/")
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        query = parsed.query or ""
        return f"{scheme}://{netloc}{path}" + (f"?{query}" if query else "")
    except Exception:
        return raw


def host_for_url(url: str) -> str:
    try:
        return urlparse(safe_text(url)).netloc.lower()
    except Exception:
        return ""


def path_for_url(url: str) -> str:
    try:
        return (urlparse(safe_text(url)).path or "").lower()
    except Exception:
        return ""


def is_preferred_job_host(url: str) -> bool:
    host = host_for_url(url)
    return any(marker in host for marker in PREFERRED_JOB_HOST_MARKERS)


def is_discovery_only_host(url: str) -> bool:
    host = host_for_url(url)
    return any(marker in host for marker in DISCOVERY_ONLY_HOST_MARKERS)


def extract_redirect_target(url: str) -> str:
    raw = safe_text(url)
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)

        for key in COMMON_REDIRECT_QUERY_KEYS:
            values = query.get(key, [])
            if values:
                candidate = unquote(safe_text(values[0]))
                if candidate.startswith("http://") or candidate.startswith("https://"):
                    return candidate

        return ""
    except Exception:
        return ""


def _looks_like_numeric_job_id(path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        if len(digits) >= 5:
            return True
    return False


def is_likely_job_detail_url(url: str) -> bool:
    normalized = normalize_url(url)
    if not normalized:
        return False

    if is_preferred_job_host(normalized):
        return True

    if not is_discovery_only_host(normalized):
        return False

    path = path_for_url(normalized)
    host = host_for_url(normalized)

    if any(marker in path for marker in BLOCKED_DISCOVERY_PATH_MARKERS):
        return False

    if "linkedin.com" in host:
        return "/jobs/view/" in path and _looks_like_numeric_job_id(path)

    if "indeed.com" in host:
        return "/viewjob" in path or ("jk=" in normalized)

    if "glassdoor.com" in host:
        return "/job-listing/" in path

    if "ziprecruiter.com" in host:
        return "/jobs/" in path and len([p for p in path.split("/") if p]) >= 2

    if "trueup.io" in host:
        return "/job/" in path or "/jobs/" in path

    if "otta.com" in host:
        return "/jobs/" in path and len([p for p in path.split("/") if p]) >= 2

    if "wellfound.com" in host:
        return "/jobs/" in path

    if "arcussearch.com" in host:
        return "/job/" in path

    if any(hint in path for hint in DETAIL_PATH_HINTS):
        return True

    return False


def choose_best_discovery_url(urls: list[str]) -> str:
    best_url, _ = choose_best_discovery_url_with_reason(urls)
    return best_url


def choose_best_discovery_url_with_reason(urls: list[str]) -> tuple[str, str]:
    cleaned = [normalize_url(url) for url in urls if safe_text(url)]
    cleaned = list(dict.fromkeys(cleaned))

    if not cleaned:
        return "", "no_candidate_url"

    preferred = [url for url in cleaned if is_preferred_job_host(url)]
    if preferred:
        return preferred[0], "preferred_host"

    detail_like = [url for url in cleaned if is_likely_job_detail_url(url)]
    if detail_like:
        return detail_like[0], "detail_like_discovery_url"

    return "", "no_preferred_or_detail_candidate"


def resolve_candidate_url(url: str) -> tuple[str, str]:
    raw = safe_text(url)
    if not raw:
        return "", "blank"

    redirect_target = extract_redirect_target(raw)
    if redirect_target:
        return normalize_url(redirect_target), "redirect_target"

    return normalize_url(raw), "direct"


def resolve_discovery_url_via_page(url: str, timeout: int = 8) -> tuple[str, str]:
    """
    Discovery-only URLs are valid only if they resolve to a preferred employer/ATS URL.
    Otherwise they should be dropped.
    """
    base_url = normalize_url(url)
    if not base_url:
        return "", "blank"

    if is_preferred_job_host(base_url):
        return base_url, "already_preferred"

    if not is_discovery_only_host(base_url):
        return "", "non_discovery_host"

    if not is_likely_job_detail_url(base_url):
        return "", "discovery_non_detail"

    try:
        response = requests.get(
            base_url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
        )
        final_url = normalize_url(response.url or base_url)

        if is_preferred_job_host(final_url):
            return final_url, "redirected_to_preferred"

        soup = BeautifulSoup(response.text, "lxml")
        candidate_urls: list[str] = []

        canonical_tag = soup.find("link", rel="canonical")
        if canonical_tag and canonical_tag.get("href"):
            candidate_urls.append(urljoin(final_url, canonical_tag.get("href")))

        meta_refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and str(v).lower() == "refresh"})
        if meta_refresh and meta_refresh.get("content"):
            content = safe_text(meta_refresh.get("content"))
            if "url=" in content.lower():
                candidate_urls.append(content.split("=", 1)[1].strip())

        for tag in soup.find_all("a", href=True):
            href = safe_text(tag.get("href"))
            if not href:
                continue
            candidate_urls.append(urljoin(final_url, href))

        preferred_candidates = []
        for candidate in candidate_urls:
            normalized = normalize_url(candidate)
            if normalized and is_preferred_job_host(normalized):
                preferred_candidates.append(normalized)

        preferred_candidates = list(dict.fromkeys(preferred_candidates))
        if preferred_candidates:
            return preferred_candidates[0], "page_extracted_preferred"

        return "", "no_preferred_link_found"

    except Exception:
        return "", "page_resolution_failed"
