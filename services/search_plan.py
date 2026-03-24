from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from services.openai_title_suggestions import suggest_titles_with_openai
except ImportError:
    suggest_titles_with_openai = None


ATS_SITE_BLOCK = "(" + " OR ".join(
    [
        "site:greenhouse.io",
        "site:lever.co",
        "site:myworkdayjobs.com",
        "site:ashbyhq.com",
        "site:smartrecruiters.com",
        "site:recruiting.paylocity.com",
        "site:jobs.jobvite.com",
        "site:jobs.icims.com",
        "site:taleo.net",
        "site:adp.com",
        "site:careers.bamboohr.com",
        "site:paycomonline.net",
        "site:ukg.com",
    ]
) + ")"

CAREER_WEB_SIGNAL_BLOCK = '("jobs" OR "careers" OR "hiring" OR "employment")'

JOB_BOARD_DISCOVERY_BLOCK = "(" + " OR ".join(
    [
        "site:linkedin.com/jobs",
        "site:indeed.com",
        "site:glassdoor.com/Job",
        "site:ziprecruiter.com",
        "site:wellfound.com",
        "site:trueup.io",
        "site:otta.com",
    ]
) + ")"


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
    title_variants: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    location_variants: list[str] = field(default_factory=list)
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    remote_only: bool = False
    query_tiers: list[dict[str, Any]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify_title_specificity(base_titles: list[str]) -> str:
    normalized_titles = [normalize_text(title) for title in base_titles if normalize_text(title)]
    if not normalized_titles:
        return "generic"

    joined = " ".join(normalized_titles)
    unique_tokens = {token for token in joined.split() if token}

    generic_titles = {
        "analyst",
        "manager",
        "engineer",
        "developer",
        "director",
        "specialist",
        "consultant",
        "architect",
        "administrator",
        "coordinator",
    }

    if len(normalized_titles) == 1:
        only = normalized_titles[0]
        if only in generic_titles:
            return "generic"
        if len(unique_tokens) <= 2:
            return "medium"

    if len(unique_tokens) <= 2:
        return "medium"

    return "specific"


def _query_budget_for_specificity(specificity: str) -> dict[str, int]:
    budgets = {
        "generic": {
            "title_variants": 4,
            "location_variants": 2,
            "ats_grouped": 2,
            "ats_strict": 4,
            "ats_loose": 4,
            "career_web": 2,
            "job_board_discovery": 2,
            "total_queries": 12,
        },
        "medium": {
            "title_variants": 5,
            "location_variants": 2,
            "ats_grouped": 2,
            "ats_strict": 6,
            "ats_loose": 6,
            "career_web": 4,
            "job_board_discovery": 4,
            "total_queries": 18,
        },
        "specific": {
            "title_variants": 6,
            "location_variants": 3,
            "ats_grouped": 6,
            "ats_strict": 12,
            "ats_loose": 10,
            "career_web": 8,
            "job_board_discovery": 8,
            "total_queries": 30,
        },
    }
    return budgets.get(specificity, budgets["medium"])


def _build_keyword_terms(include_keywords: list[str], title_variants: list[str]) -> list[str]:
    title_tokens = {
        token
        for title in title_variants
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


def _title_without_commas(title: str) -> str:
    return " ".join(safe_text(title).replace(",", " ").split())


def _location_without_commas(location: str) -> str:
    return " ".join(safe_text(location).replace(",", " ").split())


def _build_title_variants(effective_titles: list[str], max_variants: int = 10) -> list[str]:
    variants: list[str] = []

    for title in effective_titles:
        clean_title = safe_text(title)
        if not clean_title:
            continue

        variants.append(clean_title)

        no_commas = _title_without_commas(clean_title)
        if no_commas and normalize_text(no_commas) != normalize_text(clean_title):
            variants.append(no_commas)

    return dedupe_preserve_order(variants)[:max_variants]


def _build_location_variants(preferred_locations: list[str], remote_only: bool, max_variants: int = 6) -> list[str]:
    variants: list[str] = []

    if remote_only:
        variants.append("remote")
        return dedupe_preserve_order(variants)

    for location in preferred_locations[:3]:
        clean_location = safe_text(location)
        if not clean_location:
            continue

        variants.append(clean_location)

        no_commas = _location_without_commas(clean_location)
        if no_commas and normalize_text(no_commas) != normalize_text(clean_location):
            variants.append(no_commas)

    variants.append("remote")
    return dedupe_preserve_order(variants)[:max_variants]


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
    title_variants: list[str],
    location_variants: list[str],
    include_keywords: list[str],
    budgets: dict[str, int],
) -> list[dict[str, Any]]:
    tiers: list[dict[str, Any]] = []
    if not title_variants:
        return tiers

    keyword_terms = _build_keyword_terms(include_keywords, title_variants)
    keyword_fragment = f' "{keyword_terms[0]}"' if keyword_terms else ""

    grouped_title_limit = min(len(title_variants), budgets.get("title_variants", 6))
    location_limit = min(len(location_variants), budgets.get("location_variants", 3))

    grouped_queries: list[str] = []
    if grouped_title_limit > 1:
        title_or = " OR ".join(f'"{title}"' for title in title_variants[:grouped_title_limit])
        for location in location_variants[:location_limit]:
            grouped_queries.append(
                f"({title_or}) \"{location}\"{keyword_fragment} {ATS_SITE_BLOCK}"
            )
    if grouped_queries:
        tiers.append(
            {
                "name": "ats_grouped",
                "label": "ATS grouped",
                "queries": dedupe_preserve_order(grouped_queries)[:budgets.get("ats_grouped", 2)],
            }
        )

    strict_queries: list[str] = []
    for title in title_variants[:budgets.get("title_variants", 6)]:
        for location in location_variants[:location_limit]:
            strict_queries.append(
                f"\"{title}\" \"{location}\"{keyword_fragment} {ATS_SITE_BLOCK}"
            )
    if strict_queries:
        tiers.append(
            {
                "name": "ats_strict",
                "label": "ATS strict",
                "queries": dedupe_preserve_order(strict_queries)[:budgets.get("ats_strict", 6)],
            }
        )

    loose_queries: list[str] = []
    for title in title_variants[:budgets.get("title_variants", 6)]:
        for location in location_variants[:location_limit]:
            loose_queries.append(
                f"{title} {location}{keyword_fragment} {ATS_SITE_BLOCK}"
            )
    if loose_queries:
        tiers.append(
            {
                "name": "ats_loose",
                "label": "ATS loose",
                "queries": dedupe_preserve_order(loose_queries)[:budgets.get("ats_loose", 6)],
            }
        )

    career_queries: list[str] = []
    for title in title_variants[:budgets.get("title_variants", 6)]:
        for location in location_variants[:location_limit]:
            career_queries.append(
                f"\"{title}\" \"{location}\" {CAREER_WEB_SIGNAL_BLOCK}"
            )
    if career_queries:
        tiers.append(
            {
                "name": "career_web",
                "label": "Career web",
                "queries": dedupe_preserve_order(career_queries)[:budgets.get("career_web", 4)],
            }
        )

    job_board_queries: list[str] = []
    for title in title_variants[:budgets.get("title_variants", 6)]:
        for location in location_variants[:min(location_limit, 2)]:
            job_board_queries.append(
                f"\"{title}\" \"{location}\" {JOB_BOARD_DISCOVERY_BLOCK}"
            )
    if job_board_queries:
        tiers.append(
            {
                "name": "job_board_discovery",
                "label": "Job board discovery",
                "queries": dedupe_preserve_order(job_board_queries)[:budgets.get("job_board_discovery", 4)],
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

    specificity = _classify_title_specificity(base_titles)
    budgets = _query_budget_for_specificity(specificity)

    title_variants = _build_title_variants(
        effective_titles,
        max_variants=budgets.get("title_variants", 6),
    )
    location_variants = _build_location_variants(
        preferred_locations=plan_input.preferred_locations,
        remote_only=plan_input.remote_only,
        max_variants=budgets.get("location_variants", 3),
    )

    notes.append(f"Search specificity: {specificity}")
    notes.append(
        "Search budget: "
        f"title_variants={budgets.get('title_variants', 0)}, "
        f"locations={budgets.get('location_variants', 0)}, "
        f"total_queries<={budgets.get('total_queries', 0)}"
    )

    if plan_input.preferred_locations and not plan_input.remote_only:
        notes.append(
            "Effective location policy: "
            + " | ".join(plan_input.preferred_locations[:3])
            + " + Remote"
        )
    elif plan_input.remote_only:
        notes.append("Effective location policy: Remote only")

    query_tiers = _build_query_tiers(
        title_variants=title_variants,
        location_variants=location_variants,
        include_keywords=plan_input.include_keywords,
        budgets=budgets,
    )

    queries: list[str] = []
    for tier in query_tiers:
        queries.extend(tier.get("queries", []))

    queries = dedupe_preserve_order(queries)[:budgets.get("total_queries", 18)]

    return SearchPlan(
        base_titles=base_titles,
        expanded_titles=[title for title in effective_titles if title not in base_titles],
        effective_titles=effective_titles,
        title_variants=title_variants,
        preferred_locations=plan_input.preferred_locations,
        location_variants=location_variants,
        include_keywords=plan_input.include_keywords,
        exclude_keywords=plan_input.exclude_keywords,
        remote_only=plan_input.remote_only,
        query_tiers=query_tiers,
        queries=queries,
        notes=notes,
    )
