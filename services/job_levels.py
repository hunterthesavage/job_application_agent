from __future__ import annotations

from typing import Any


JOB_LEVEL_OPTIONS = [
    "Individual Contributor",
    "IC Senior",
    "Manager",
    "Sr. Manager",
    "Director",
    "Sr. Director",
    "VP",
    "SVP",
    "C-Suite",
]


JOB_LEVEL_RANKS: dict[str, int] = {
    "Individual Contributor": 1,
    "IC Senior": 2,
    "Manager": 3,
    "Sr. Manager": 4,
    "Director": 5,
    "Sr. Director": 6,
    "VP": 7,
    "SVP": 8,
    "C-Suite": 9,
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    return " ".join(
        _clean(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .replace("&", " and ")
        .split()
    )


def _matches_phrase(normalized_text: str, tokens: list[str], phrase: str) -> bool:
    normalized_phrase = _normalize_text(phrase)
    if not normalized_phrase:
        return False
    if " " in normalized_phrase:
        return normalized_phrase in normalized_text
    return normalized_phrase in tokens


def parse_preferred_job_levels(value: str) -> list[str]:
    text = _clean(value)
    if not text:
        return []

    raw_parts = []
    if "\n" in text:
        raw_parts = text.splitlines()
    elif ";" in text:
        raw_parts = text.split(";")
    else:
        raw_parts = text.split(",")

    selected: list[str] = []
    seen: set[str] = set()

    for raw_part in raw_parts:
        part = _clean(raw_part)
        if not part:
            continue
        for option in JOB_LEVEL_OPTIONS:
            if part.casefold() == option.casefold():
                if option not in seen:
                    selected.append(option)
                    seen.add(option)
                break

    return selected


def serialize_preferred_job_levels(levels: list[str]) -> str:
    selected: list[str] = []
    seen: set[str] = set()

    for option in JOB_LEVEL_OPTIONS:
        if option in levels and option not in seen:
            selected.append(option)
            seen.add(option)

    return ", ".join(selected)


def infer_job_level(job_title: str) -> str:
    normalized = _normalize_text(job_title)
    if not normalized:
        return ""

    tokens = normalized.split()

    chief_terms = ["chief", "ceo", "cto", "cio", "ciso", "cdo", "coo", "cao"]
    if any(_matches_phrase(normalized, tokens, term) for term in chief_terms):
        return "C-Suite"

    if normalized == "president" or normalized.startswith("president "):
        return "C-Suite"

    level_rules = [
        ("SVP", ["executive vice president", "senior vice president", "evp", "svp"]),
        ("VP", ["vice president", "vp", "head of"]),
        ("Sr. Director", ["senior director", "sr director"]),
        ("Director", ["director"]),
        ("Sr. Manager", ["senior manager", "sr manager"]),
        ("Manager", ["manager"]),
        ("IC Senior", ["principal", "staff", "lead", "senior", "sr", "architect"]),
        (
            "Individual Contributor",
            [
                "engineer",
                "developer",
                "analyst",
                "specialist",
                "administrator",
                "consultant",
                "designer",
                "scientist",
                "individual contributor",
            ],
        ),
    ]

    for level, phrases in level_rules:
        if any(_matches_phrase(normalized, tokens, phrase) for phrase in phrases):
            return level

    return ""


def get_level_preference_penalty(job_title: str, preferred_levels: list[str]) -> tuple[int, str, str]:
    selected = [level for level in preferred_levels if level in JOB_LEVEL_RANKS]
    if not selected:
        return 0, "", ""

    detected_level = infer_job_level(job_title)
    if not detected_level:
        return 0, "", ""

    detected_rank = JOB_LEVEL_RANKS[detected_level]
    selected_ranks = sorted(JOB_LEVEL_RANKS[level] for level in selected)

    if detected_level in selected:
        return 0, detected_level, ""

    min_rank = selected_ranks[0]
    max_rank = selected_ranks[-1]

    if detected_rank < min_rank:
        distance = min_rank - detected_rank
        penalty = min(35, 10 + (distance * 8))
        return (
            penalty,
            detected_level,
            f"Title level appears below selected job levels (detected: {detected_level}; preferred: {', '.join(selected)})",
        )

    if detected_rank > max_rank:
        distance = detected_rank - max_rank
        penalty = min(15, 4 + (distance * 4))
        return (
            penalty,
            detected_level,
            f"Title level appears above selected job levels (detected: {detected_level}; preferred: {', '.join(selected)})",
        )

    return (
        8,
        detected_level,
        f"Title level falls outside the selected job levels (detected: {detected_level}; preferred: {', '.join(selected)})",
    )
