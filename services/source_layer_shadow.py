from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse

from services.db import db_connection

SHADOW_SELECTION_CAP = 25
DIRECT_SOURCE_SELECTION_CAP = 12
SUPPORTED_NEXT_GEN_SEED_VENDORS = {
    "greenhouse",
    "lever",
    "workday",
    "sap successfactors",
    "icims",
    "taleo / oracle recruiting",
}

SENIORITY_MARKERS = {
    "chief",
    "ceo",
    "cto",
    "cio",
    "cfo",
    "coo",
    "vice",
    "president",
    "vp",
    "svp",
    "evp",
    "avp",
    "head",
    "director",
}

TECHNOLOGY_MARKERS = {
    "technology",
    "information",
    "it",
    "engineering",
    "infrastructure",
    "platform",
    "systems",
    "applications",
    "application",
    "software",
    "security",
    "cybersecurity",
    "cyber",
    "data",
    "analytics",
    "digital",
    "cloud",
    "network",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_text(value: Any) -> str:
    return " ".join(
        _safe_text(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .split()
    )


def _parse_csv_like(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _parse_location_like(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    if "\n" in text:
        return [part.strip() for part in text.splitlines() if part.strip()]
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    return [text]


def _parse_multivalue_setting(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    if "\n" in text:
        return [part.strip() for part in text.splitlines() if part.strip()]
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return [text]


def _parse_int_setting(value: Any, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        return default
    return parsed if parsed >= 0 else default


def _tokenize(values: list[str]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        for token in _normalize_text(value).split():
            if len(token) >= 3:
                tokens.append(token)
    return list(dict.fromkeys(tokens))


def _is_sparse_senior_technology_search(target_titles: list[str]) -> bool:
    cleaned_titles = [title for title in target_titles if _safe_text(title)]
    if not cleaned_titles or len(cleaned_titles) > 3:
        return False

    normalized = " ".join(_normalize_text(title) for title in cleaned_titles)
    tokens = set(normalized.split())
    has_seniority = bool(tokens.intersection(SENIORITY_MARKERS))
    has_technology = bool(tokens.intersection(TECHNOLOGY_MARKERS))
    return has_seniority and has_technology


def _score_shadow_candidate(
    row: Any,
    *,
    title_tokens: list[str],
    location_tokens: list[str],
    remote_only: bool,
    source_layer_mode: str,
) -> int:
    score = 0

    review_status = _safe_text(row["review_status"]).lower()
    careers_url_status = _safe_text(row["careers_url_status"]).lower()
    ats_vendor = _safe_text(row["ats_vendor"]).lower() or "unknown"

    if review_status == "approved":
        score += 80
    elif review_status == "unreviewed":
        score += 55
    elif review_status == "needs_review":
        score += 45

    if careers_url_status == "validated":
        score += 15
    elif careers_url_status == "candidate":
        score += 5

    if int(row["is_primary"] or 0) == 1:
        score += 15

    score += int(float(row["confidence_score"] or 0) * 10)
    score += int(float(row["health_score"] or 0) * 10)

    if ats_vendor != "unknown":
        score += 5

    searchable_text = " ".join(
        [
            _safe_text(row["company_name"]),
            _safe_text(row["canonical_domain"]),
            _safe_text(row["hq"]),
            _safe_text(row["notes"]),
            _safe_text(row["endpoint_url"]),
            ats_vendor,
        ]
    )
    normalized = _normalize_text(searchable_text)

    title_matches = sum(1 for token in title_tokens if token in normalized)
    location_matches = sum(1 for token in location_tokens if token in normalized)
    score += min(title_matches, 3) * 8
    score += min(location_matches, 3) * 4

    if remote_only and "remote" in normalized:
        score += 6

    return score


def _supports_next_gen_seed_endpoint(ats_vendor: str, endpoint_url: str) -> bool:
    vendor = _safe_text(ats_vendor).lower() or "unknown"
    endpoint = _safe_text(endpoint_url)
    if not endpoint:
        return False

    try:
        parsed = urlparse(endpoint)
    except Exception:
        return False

    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()

    if vendor == "greenhouse":
        return "job-boards.greenhouse.io" in host or "boards.greenhouse.io" in host
    if vendor == "lever":
        return "jobs.lever.co" in host
    if vendor == "workday":
        return "myworkdayjobs.com" in host
    if vendor == "sap successfactors":
        generic_hosts = ("successfactors.com", "sapsf.com", "ondemand.com")
        return not any(marker in host for marker in generic_hosts)
    if vendor == "icims":
        return True
    if vendor == "taleo / oracle recruiting":
        if "taleo.net" not in host or "/careersection/" not in path:
            return False
        return path.endswith("/jobsearch.ftl") or path.endswith("/mysearches.ftl")
    return False


def _next_gen_seed_shape_priority(ats_vendor: str, endpoint_url: str) -> int:
    vendor = _safe_text(ats_vendor).lower() or "unknown"
    endpoint = _safe_text(endpoint_url)
    if not endpoint:
        return 0

    try:
        parsed = urlparse(endpoint)
    except Exception:
        return 0

    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower().rstrip("/")
    path_parts = [part for part in path.split("/") if part]
    last_part = path_parts[-1] if path_parts else ""

    if vendor == "workday":
        if "myworkdayjobs.com" not in host:
            return 0
        if last_part == "login":
            return 0
        if last_part == "search":
            return 1
        if any(part in {"en-us", "en-ca", "fr-fr"} for part in path_parts) and last_part not in {"search", "login"}:
            return 4
        if last_part in {"careers", "external", "external_careers", "externalcareers_globalsite", "assurant_careers"}:
            return 3
        return 2

    if vendor == "icims":
        if any(marker in path for marker in {"job-scams", "job-scam", "resources", "resource", "career-areas", "locations", "categories"}):
            return 0
        if last_part in {"jobs", "results.html", "careers", "careers-home"}:
            return 3
        return 2

    if vendor == "sap successfactors":
        if any(marker in path for marker in {"reasonable-accommodations", "accommodations", "benefits", "faq", "content/"}):
            return 0
        if "/search" in path or last_part in {"careers", "jobs", "viewalljobs"}:
            return 3
        if "/go" in path:
            return 2
        return 1

    if vendor == "taleo / oracle recruiting":
        return 3 if path.endswith("/jobsearch.ftl") else 2

    if vendor in {"greenhouse", "lever"}:
        return 3

    return 1


def _next_gen_vendor_priority(ats_vendor: str, *, senior_technology_bias: bool) -> int:
    vendor = _safe_text(ats_vendor).lower() or "unknown"
    if not senior_technology_bias:
        return 0

    if vendor == "workday":
        return 5
    if vendor == "icims":
        return 4
    if vendor in {"greenhouse", "lever"}:
        return 3
    if vendor == "taleo / oracle recruiting":
        return 2
    if vendor == "sap successfactors":
        return 1
    return 0


def _is_preferred_next_gen_seed_row(row: Any) -> bool:
    ats_vendor = _safe_text(row["ats_vendor"]).lower() or "unknown"
    endpoint_url = _safe_text(row["endpoint_url"])
    careers_url_status = _safe_text(row["careers_url_status"]).lower()
    review_status = _safe_text(row["review_status"]).lower()

    if not _supports_next_gen_seed_endpoint(ats_vendor, endpoint_url):
        return False
    if careers_url_status != "validated":
        return False
    if review_status == "rejected":
        return False

    try:
        confidence_score = float(row["confidence_score"] or 0)
    except Exception:
        confidence_score = 0.0

    return confidence_score >= 0.80 and int(row["is_primary"] or 0) == 1


def _senior_technology_vendor_quotas(selection_cap: int) -> list[tuple[str, int]]:
    if selection_cap <= 0:
        return []

    quotas: list[tuple[str, int]] = [
        ("workday", max(1, round(selection_cap * 0.40))),
        ("icims", max(1, round(selection_cap * 0.28))),
        ("sap successfactors", max(1, round(selection_cap * 0.16))),
        ("taleo / oracle recruiting", max(1, round(selection_cap * 0.08))),
        ("greenhouse", max(1, round(selection_cap * 0.04))),
        ("lever", max(1, round(selection_cap * 0.04))),
    ]

    allocated = sum(limit for _, limit in quotas)
    if allocated > selection_cap:
        overflow = allocated - selection_cap
        adjustable = [
            idx for idx, (_, limit) in enumerate(quotas) if limit > 1
        ]
        while overflow > 0 and adjustable:
            for idx in reversed(adjustable):
                vendor, limit = quotas[idx]
                if limit <= 1:
                    continue
                quotas[idx] = (vendor, limit - 1)
                overflow -= 1
                if overflow == 0:
                    break
            adjustable = [
                idx for idx, (_, limit) in enumerate(quotas) if limit > 1
            ]
    elif allocated < selection_cap:
        vendor, limit = quotas[0]
        quotas[0] = (vendor, limit + (selection_cap - allocated))

    return quotas


def _select_diversified_next_gen_rows(
    scored_rows: list[tuple[int, str, str, Any]],
    *,
    selection_cap: int,
    preferred_endpoint_urls: set[str] | None = None,
    stop_after_quota_pass: bool = False,
    excluded_endpoint_urls: set[str] | None = None,
) -> list[Any]:
    if selection_cap <= 0 or not scored_rows:
        return []

    preferred_endpoint_urls = preferred_endpoint_urls or set()
    excluded_endpoint_urls = excluded_endpoint_urls or set()

    quotas = _senior_technology_vendor_quotas(selection_cap)
    selected_indices: set[int] = set()
    selected_endpoint_urls: set[str] = set()
    selected_rows: list[Any] = []

    for vendor, limit in quotas:
        if len(selected_rows) >= selection_cap:
            break
        taken = 0
        for idx, (_, _, endpoint_url, row) in enumerate(scored_rows):
            if idx in selected_indices:
                continue
            if endpoint_url in selected_endpoint_urls:
                continue
            if endpoint_url in excluded_endpoint_urls:
                continue
            if preferred_endpoint_urls and endpoint_url not in preferred_endpoint_urls:
                continue
            ats_vendor = _safe_text(row["ats_vendor"]).lower() or "unknown"
            if ats_vendor != vendor:
                continue
            if not _supports_next_gen_seed_endpoint(ats_vendor, endpoint_url):
                continue
            selected_indices.add(idx)
            selected_endpoint_urls.add(endpoint_url)
            selected_rows.append(row)
            taken += 1
            if taken >= limit or len(selected_rows) >= selection_cap:
                break

    if stop_after_quota_pass:
        return selected_rows[:selection_cap]

    if len(selected_rows) >= selection_cap:
        return selected_rows[:selection_cap]

    for idx, (_, _, endpoint_url, row) in enumerate(scored_rows):
        if idx in selected_indices:
            continue
        if endpoint_url in selected_endpoint_urls:
            continue
        if endpoint_url in excluded_endpoint_urls:
            continue
        if preferred_endpoint_urls and endpoint_url not in preferred_endpoint_urls:
            continue
        ats_vendor = _safe_text(row["ats_vendor"]).lower() or "unknown"
        if not _supports_next_gen_seed_endpoint(ats_vendor, endpoint_url):
            continue
        selected_indices.add(idx)
        selected_endpoint_urls.add(endpoint_url)
        selected_rows.append(row)
        if len(selected_rows) >= selection_cap:
            return selected_rows

    for idx, (_, _, endpoint_url, row) in enumerate(scored_rows):
        if idx in selected_indices:
            continue
        if endpoint_url in selected_endpoint_urls:
            continue
        if endpoint_url in excluded_endpoint_urls:
            continue
        selected_endpoint_urls.add(endpoint_url)
        selected_rows.append(row)
        if len(selected_rows) >= selection_cap:
            break

    return selected_rows


def _selection_sort_key(
    item: tuple[int, str, str, Any],
    *,
    source_layer_mode: str,
    senior_technology_bias: bool,
) -> tuple[Any, ...]:
    score, company_name, endpoint_url, row = item
    ats_vendor = _safe_text(row["ats_vendor"]).lower() or "unknown"
    supported_priority = int(ats_vendor in SUPPORTED_NEXT_GEN_SEED_VENDORS)
    seedable_priority = int(_supports_next_gen_seed_endpoint(ats_vendor, endpoint_url))
    seed_shape_priority = _next_gen_seed_shape_priority(ats_vendor, endpoint_url)
    vendor_priority = _next_gen_vendor_priority(ats_vendor, senior_technology_bias=senior_technology_bias)
    if source_layer_mode == "next_gen":
        return (-seedable_priority, -seed_shape_priority, -vendor_priority, -supported_priority, -score, company_name.lower(), endpoint_url.lower())
    return (-score, company_name.lower(), endpoint_url.lower())


def run_shadow_endpoint_selection(settings: dict[str, str] | None = None) -> dict[str, Any]:
    settings = settings or {}
    source_layer_mode = _safe_text(settings.get("_source_layer_mode", "legacy")).lower() or "legacy"
    selection_offset = _parse_int_setting(settings.get("_shadow_selection_offset", 0), 0)
    default_selection_cap = DIRECT_SOURCE_SELECTION_CAP if source_layer_mode == "next_gen" else SHADOW_SELECTION_CAP
    selection_cap = _parse_int_setting(
        settings.get("_shadow_selection_cap", default_selection_cap),
        default_selection_cap,
    ) or default_selection_cap
    excluded_endpoint_urls = {
        _safe_text(url)
        for url in _parse_multivalue_setting(settings.get("_shadow_exclude_endpoint_urls", ""))
        if _safe_text(url)
    }

    title_tokens = _tokenize(_parse_csv_like(settings.get("target_titles", "")))
    target_titles = _parse_csv_like(settings.get("target_titles", ""))
    location_tokens = _tokenize(_parse_location_like(settings.get("preferred_locations", "")))
    remote_only = _safe_text(settings.get("remote_only", "false")).lower() == "true"
    senior_technology_bias = _is_sparse_senior_technology_search(target_titles)

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.name AS company_name,
                c.canonical_domain,
                c.hq,
                endpoint_url,
                ats_vendor,
                confidence_score,
                health_score,
                review_status,
                careers_url_status,
                is_primary,
                hiring_endpoints.active AS active,
                notes
            FROM hiring_endpoints
            JOIN companies c ON c.id = hiring_endpoints.company_id
            WHERE hiring_endpoints.active = 1
            """
        ).fetchall()

    ats_counter: Counter[str] = Counter()
    approved_count = 0
    candidate_count = 0
    primary_count = 0
    preferred_next_gen_seed_count = 0

    for row in rows:
        ats_vendor = str(row["ats_vendor"] or "").strip().lower() or "unknown"
        ats_counter[ats_vendor] += 1

        if str(row["review_status"] or "").strip().lower() == "approved":
            approved_count += 1
        if str(row["careers_url_status"] or "").strip().lower() == "candidate":
            candidate_count += 1
        if int(row["is_primary"] or 0) == 1:
            primary_count += 1
        if _is_preferred_next_gen_seed_row(row):
            preferred_next_gen_seed_count += 1

    scored_rows = sorted(
        (
            (
                _score_shadow_candidate(
                    row,
                    title_tokens=title_tokens,
                    location_tokens=location_tokens,
                    remote_only=remote_only,
                    source_layer_mode=source_layer_mode,
                ),
                _safe_text(row["company_name"]) or "(unknown company)",
                _safe_text(row["endpoint_url"]),
                row,
            )
            for row in rows
            if _safe_text(row["endpoint_url"]) not in excluded_endpoint_urls
        ),
        key=lambda item: _selection_sort_key(
            item,
            source_layer_mode=source_layer_mode,
            senior_technology_bias=senior_technology_bias,
        ),
    )

    if source_layer_mode == "next_gen":
        preferred_endpoint_urls = {
            _safe_text(row["endpoint_url"])
            for row in rows
            if _is_preferred_next_gen_seed_row(row)
        }
        if preferred_endpoint_urls and senior_technology_bias:
            selected_rows = _select_diversified_next_gen_rows(
                scored_rows[selection_offset:],
                selection_cap=selection_cap,
                preferred_endpoint_urls=preferred_endpoint_urls,
                stop_after_quota_pass=True,
            )
        elif preferred_endpoint_urls:
            selected_rows = [
                item[3]
                for item in scored_rows[selection_offset:]
                if item[2] in preferred_endpoint_urls
            ][:selection_cap]
        elif senior_technology_bias:
            selected_rows = _select_diversified_next_gen_rows(
                scored_rows[selection_offset:],
                selection_cap=selection_cap,
            )
        else:
            selected_rows = [item[3] for item in scored_rows[selection_offset:selection_offset + selection_cap]]

        if len(selected_rows) < selection_cap:
            selected_endpoint_urls = {
                _safe_text(row["endpoint_url"])
                for row in selected_rows
            }
            remaining_rows = _select_diversified_next_gen_rows(
                scored_rows[selection_offset:],
                selection_cap=selection_cap - len(selected_rows),
                excluded_endpoint_urls=selected_endpoint_urls,
            )
            selected_rows.extend(remaining_rows)
    else:
        selected_rows = [item[3] for item in scored_rows[selection_offset:selection_offset + selection_cap]]
    selected_companies = list(
        dict.fromkeys(
            _safe_text(row["company_name"]) or "(unknown company)"
            for row in selected_rows
        )
    )[:5]
    selected_candidates = [
        {
            "company_name": _safe_text(row["company_name"]) or "(unknown company)",
            "endpoint_url": _safe_text(row["endpoint_url"]),
            "ats_vendor": _safe_text(row["ats_vendor"]).lower() or "unknown",
            "review_status": _safe_text(row["review_status"]).lower(),
            "careers_url_status": _safe_text(row["careers_url_status"]).lower(),
        }
        for row in selected_rows
    ]
    selected_ats_counter: Counter[str] = Counter(
        _safe_text(row["ats_vendor"]).lower() or "unknown" for row in selected_rows
    )

    top_ats = [f"{vendor} {count}" for vendor, count in ats_counter.most_common(5)]
    top_selected_ats = [
        f"{vendor} {count}" for vendor, count in selected_ats_counter.most_common(5)
    ]

    lines = [
        "Direct-source seed shadow summary:",
        f"- Active imported endpoints: {len(rows)}",
        f"- Approved endpoints: {approved_count}",
        f"- Candidate endpoints: {candidate_count}",
        f"- Primary endpoints: {primary_count}",
        f"- Selected shadow candidates: {len(selected_rows)}",
    ]
    if selection_offset:
        lines.append(f"- Shadow selection offset: {selection_offset}")
    if source_layer_mode == "next_gen":
        supported_selected = sum(
            1
            for row in selected_rows
            if _supports_next_gen_seed_endpoint(
                _safe_text(row["ats_vendor"]).lower() or "unknown",
                _safe_text(row["endpoint_url"]),
            )
        )
        lines.append(f"- Direct-source seed-supporting candidates: {supported_selected}")
        lines.append(f"- Preferred direct-source seed pool: {preferred_next_gen_seed_count}")
        lines.append(
            f"- Preferred direct-source candidates selected: {sum(1 for row in selected_rows if _is_preferred_next_gen_seed_row(row))}"
        )
        if senior_technology_bias:
            lines.append("- Direct-source ranking bias: senior technology leadership")
            lines.append("- Direct-source ATS mix profile: diversified senior tech")
    if selected_companies:
        lines.append(f"- Selected companies: {', '.join(selected_companies)}")
    else:
        lines.append("- Selected companies: none yet")
    if top_selected_ats:
        lines.append(f"- Selected ATS families: {', '.join(top_selected_ats)}")
    else:
        lines.append("- Selected ATS families: none yet")
    if top_ats:
        lines.append(f"- Top ATS families: {', '.join(top_ats)}")
    else:
        lines.append("- Top ATS families: none yet")

    return {
        "active_endpoint_count": len(rows),
        "approved_endpoint_count": approved_count,
        "candidate_endpoint_count": candidate_count,
        "primary_endpoint_count": primary_count,
        "preferred_next_gen_seed_count": preferred_next_gen_seed_count,
        "selected_endpoint_count": len(selected_rows),
        "selected_company_names": selected_companies,
        "selected_candidates": selected_candidates,
        "ats_counts": dict(ats_counter),
        "selected_ats_counts": dict(selected_ats_counter),
        "output": "\n".join(lines),
    }
