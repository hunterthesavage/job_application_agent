from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from services.openai_title_suggestions import suggest_titles_with_openai
except ImportError:
    suggest_titles_with_openai = None


ATS_SITE_BLOCK = "(site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com OR site:smartrecruiters.com)"


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
    queries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_location_terms(preferred_locations: list[str], remote_only: bool) -> list[str]:
    if remote_only:
        return ["remote"]

    if preferred_locations:
        terms = dedupe_preserve_order(preferred_locations[:2] + ["remote"])
        return terms[:3]

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


def _build_queries(
    effective_titles: list[str],
    location_terms: list[str],
    include_keywords: list[str],
) -> list[str]:
    queries: list[str] = []

    if not effective_titles:
        return queries

    keyword_terms = _build_keyword_terms(include_keywords, effective_titles)

    # grouped title query first
    if len(effective_titles) > 1:
        title_or = " OR ".join(f'"{title}"' for title in effective_titles[:6])
        for location in location_terms[:2]:
            parts = [f"({title_or})", f'"{location}"']
            if keyword_terms:
                parts.append(f'"{keyword_terms[0]}"')
            parts.append(ATS_SITE_BLOCK)
            queries.append(" ".join(parts))

    # exact-ish title queries next
    for title in effective_titles[:4]:
        for location in location_terms[:2]:
            parts = [f'"{title}"', f'"{location}"']
            if keyword_terms:
                parts.append(f'"{keyword_terms[0]}"')
            parts.append(ATS_SITE_BLOCK)
            queries.append(" ".join(parts))

    # title-only fallback
    for title in effective_titles[:2]:
        parts = [f'"{title}"']
        if keyword_terms:
            parts.append(f'"{keyword_terms[0]}"')
        parts.append(ATS_SITE_BLOCK)
        queries.append(" ".join(parts))

    return dedupe_preserve_order([q.strip() for q in queries if q.strip()])[:12]


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

    queries = _build_queries(
        effective_titles=effective_titles,
        location_terms=location_terms,
        include_keywords=plan_input.include_keywords,
    )

    return SearchPlan(
        base_titles=base_titles,
        expanded_titles=[title for title in effective_titles if title not in base_titles],
        effective_titles=effective_titles,
        preferred_locations=plan_input.preferred_locations,
        include_keywords=plan_input.include_keywords,
        exclude_keywords=plan_input.exclude_keywords,
        remote_only=plan_input.remote_only,
        queries=queries,
        notes=notes,
    )
