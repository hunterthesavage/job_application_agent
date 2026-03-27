from __future__ import annotations

from collections import Counter
from typing import Any

from services.db import db_connection

SHADOW_SELECTION_CAP = 25
SUPPORTED_NEXT_GEN_SEED_VENDORS = {"greenhouse", "lever", "workday", "sap successfactors"}


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


def _tokenize(values: list[str]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        for token in _normalize_text(value).split():
            if len(token) >= 3:
                tokens.append(token)
    return list(dict.fromkeys(tokens))


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


def _selection_sort_key(item: tuple[int, str, str, Any], *, source_layer_mode: str) -> tuple[Any, ...]:
    score, company_name, endpoint_url, row = item
    ats_vendor = _safe_text(row["ats_vendor"]).lower() or "unknown"
    supported_priority = int(ats_vendor in SUPPORTED_NEXT_GEN_SEED_VENDORS)
    if source_layer_mode == "next_gen":
        return (-supported_priority, -score, company_name.lower(), endpoint_url.lower())
    return (-score, company_name.lower(), endpoint_url.lower())


def run_shadow_endpoint_selection(settings: dict[str, str] | None = None) -> dict[str, Any]:
    settings = settings or {}
    source_layer_mode = _safe_text(settings.get("_source_layer_mode", "legacy")).lower() or "legacy"

    title_tokens = _tokenize(_parse_csv_like(settings.get("target_titles", "")))
    location_tokens = _tokenize(_parse_location_like(settings.get("preferred_locations", "")))
    remote_only = _safe_text(settings.get("remote_only", "false")).lower() == "true"

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

    for row in rows:
        ats_vendor = str(row["ats_vendor"] or "").strip().lower() or "unknown"
        ats_counter[ats_vendor] += 1

        if str(row["review_status"] or "").strip().lower() == "approved":
            approved_count += 1
        if str(row["careers_url_status"] or "").strip().lower() == "candidate":
            candidate_count += 1
        if int(row["is_primary"] or 0) == 1:
            primary_count += 1

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
        ),
        key=lambda item: _selection_sort_key(item, source_layer_mode=source_layer_mode),
    )

    selected_rows = [item[3] for item in scored_rows[:SHADOW_SELECTION_CAP]]
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
        "Next-gen source layer shadow summary:",
        f"- Active imported endpoints: {len(rows)}",
        f"- Approved endpoints: {approved_count}",
        f"- Candidate endpoints: {candidate_count}",
        f"- Primary endpoints: {primary_count}",
        f"- Selected shadow candidates: {len(selected_rows)}",
    ]
    if source_layer_mode == "next_gen":
        supported_selected = sum(
            1
            for row in selected_rows
            if (_safe_text(row["ats_vendor"]).lower() or "unknown") in SUPPORTED_NEXT_GEN_SEED_VENDORS
        )
        lines.append(f"- Next-gen seed-supporting candidates: {supported_selected}")
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
        "selected_endpoint_count": len(selected_rows),
        "selected_company_names": selected_companies,
        "selected_candidates": selected_candidates,
        "ats_counts": dict(ats_counter),
        "selected_ats_counts": dict(selected_ats_counter),
        "output": "\n".join(lines),
    }
