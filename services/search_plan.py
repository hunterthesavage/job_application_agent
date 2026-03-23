from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from services.openai_title_suggestions import suggest_titles_with_openai
except ImportError:
    suggest_titles_with_openai = None


ATS_SITE_BLOCK = "(site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com OR site:smartrecruiters.com)"
CAREER_SIGNAL_BLOCK = '("jobs" OR "careers" OR "hiring")'


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


@dataclass
class SearchPlanInput:
    target_titles: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    remote_only: bool = False
    profile_summary: str = ""
    resume_text: str = ""

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "SearchPlanInput":
        return cls(
            target_titles=dedupe_preserve_order(parse_csv_text(settings.get("target_titles", ""))),
            preferred_locations=dedupe_preserve_order(parse_preferred_locations(settings.get("preferred_locations", ""))),
            include_keywords=dedupe_preserve_order(parse_csv_text(settings.get("include_keywords", ""))),
            exclude_keywords=dedupe_preserve_order(parse_csv_text(settings.get("exclude_keywords", ""))),
            remote_only=safe_text(settings.get("remote_only", "false")).lower() == "true",
            profile_summary=safe_text(settings.get("profile_summary", "")),
            resume_text=safe_text(settings.get("resume_text", "")),
        )


@dataclass
class SearchPlan:
    base_titles: list[str] = field(default_factory=list)
    expanded_titles: list[str] = field(default_factory=list)
    effective_titles: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    remote_only: bool = False
    query_tiers: list[dict[str, Any]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_location_terms(preferred_locations: list[str], remote_only: bool) -> list[str]:
    if remote_only:
        return ["remote"]

    if preferred_locations:
        return dedupe_preserve_order(preferred_locations[:2] + ["remote"])[:3]

    return ["remote"]


def _build_keyword_terms(include_keywords: list[str], effective_titles: list[str]) -> list[str]:
    title_tokens = {
        token
        for title in effective_titles
        for token in normalize_text(title).split()
        if token
    }

    filtered: list[str] = []
    for keyword in include_keywords:
        normalized = normalize_text(keyword)
        if not normalized:
            continue
        if normalized in title_tokens:
            continue
        filtered.append(keyword)

    return dedupe_preserve_order(filtered)[:2]


def _expand_titles_with_ai(plan_input: SearchPlanInput) -> tuple[list[str], list[str]]:
    notes: list[str] = []

    base_titles = dedupe_preserve_order(plan_input.target_titles)
    if not base_titles:
        return [], ["No base titles supplied."]

    if suggest_titles_with_openai is None:
        return base_titles, ["AI title expansion unavailable. Using base titles only."]

    result = suggest_titles_with_openai(
        current_titles=", ".join(base_titles),
        profile_summary=plan_input.profile_summary,
        resume_text=plan_input.resume_text,
        include_keywords=", ".join(plan_input.include_keywords),
    )

    if not result.get("ok"):
        notes.append(f"AI title expansion unavailable: {safe_text(result.get('error', 'unknown error'))}")
        return base_titles, notes

    ai_titles = [
        safe_text(title)
        for title in result.get("titles", [])
        if safe_text(title)
    ]

    limited_ai_titles = ai_titles[:4]
    effective_titles = dedupe_preserve_order(base_titles + limited_ai_titles)[:6]

    notes.append(
        f"AI title expansion applied: base {len(base_titles)} | added {max(0, len(effective_titles) - len(base_titles))} | total {len(effective_titles)}"
    )

    extra_notes = safe_text(result.get("notes", ""))
    if extra_notes:
        notes.append(f"AI notes: {extra_notes}")

    return effective_titles, notes


def _build_query_tiers(
    effective_titles: list[str],
    location_terms: list[str],
    include_keywords: list[str],
) -> list[dict[str, Any]]:
    tiers: list[dict[str, Any]] = []
    if not effective_titles:
        return tiers

    keyword_terms = _build_keyword_terms(include_keywords, effective_titles)
    keyword_fragment = f' "{keyword_terms[0]}"' if keyword_terms else ""

    # Tier 1: grouped ATS query first
    grouped_queries: list[str] = []
    if len(effective_titles) > 1:
        title_or = " OR ".join(f'"{title}"' for title in effective_titles[:6])
        for location in location_terms[:2]:
            grouped_queries.append(
                f"({title_or}) \"{location}\"{keyword_fragment} {ATS_SITE_BLOCK}"
            )
    if grouped_queries:
        tiers.append(
            {
                "name": "ats_grouped",
                "label": "ATS grouped",
                "queries": dedupe_preserve_order(grouped_queries)[:4],
            }
        )

    # Tier 2: exact ATS queries
    strict_queries: list[str] = []
    for title in effective_titles[:4]:
        for location in location_terms[:2]:
            strict_queries.append(
                f"\"{title}\" \"{location}\"{keyword_fragment} {ATS_SITE_BLOCK}"
            )
    if strict_queries:
        tiers.append(
            {
                "name": "ats_strict",
                "label": "ATS strict",
                "queries": dedupe_preserve_order(strict_queries)[:8],
            }
        )

    # Tier 3: looser ATS queries, fewer quotes
    loose_queries: list[str] = []
    for title in effective_titles[:3]:
        for location in location_terms[:2]:
            loose_queries.append(
                f"{title} {location}{keyword_fragment} {ATS_SITE_BLOCK}"
            )
    if loose_queries:
        tiers.append(
            {
                "name": "ats_loose",
                "label": "ATS loose",
                "queries": dedupe_preserve_order(loose_queries)[:6],
            }
        )

    # Tier 4: broader career-web discovery
    career_queries: list[str] = []
    for title in effective_titles[:2]:
        for location in location_terms[:2]:
            career_queries.append(
                f"\"{title}\" \"{location}\" {CAREER_SIGNAL_BLOCK}"
            )
    if career_queries:
        tiers.append(
            {
                "name": "career_web",
                "label": "Career web",
                "queries": dedupe_preserve_order(career_queries)[:4],
            }
        )

    return tiers


def build_search_plan(
    settings: dict[str, Any],
    use_ai_expansion: bool = False,
) -> SearchPlan:
    plan_input = SearchPlanInput.from_settings(settings)

    base_titles = dedupe_preserve_order(plan_input.target_titles)

    notes: list[str] = []
    if use_ai_expansion:
        effective_titles, ai_notes = _expand_titles_with_ai(plan_input)
        notes.extend(ai_notes)
    else:
        effective_titles = base_titles[:]

    if not effective_titles:
        notes.append("No effective titles available for query generation.")

    location_terms = _build_location_terms(
        preferred_locations=plan_input.preferred_locations,
        remote_only=plan_input.remote_only,
    )

    query_tiers = _build_query_tiers(
        effective_titles=effective_titles,
        location_terms=location_terms,
        include_keywords=plan_input.include_keywords,
    )

    queries: list[str] = []
    for tier in query_tiers:
        queries.extend(tier.get("queries", []))

    queries = dedupe_preserve_order(queries)[:18]

    return SearchPlan(
        base_titles=base_titles,
        expanded_titles=[title for title in effective_titles if title not in base_titles],
        effective_titles=effective_titles,
        preferred_locations=plan_input.preferred_locations,
        include_keywords=plan_input.include_keywords,
        exclude_keywords=plan_input.exclude_keywords,
        remote_only=plan_input.remote_only,
        query_tiers=query_tiers,
        queries=queries,
        notes=notes,
    )
