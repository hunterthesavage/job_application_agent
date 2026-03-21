from __future__ import annotations


TITLE_SYNONYM_GROUPS = {
    "nurse": [
        "nurse",
        "registered nurse",
        "rn",
        "nursing",
        "nurse practitioner",
        "np",
        "aprn",
        "clinical nurse",
        "care coordinator",
        "care manager",
    ],
    "analyst": [
        "analyst",
        "analytics",
        "analytics engineer",
        "business intelligence",
        "bi",
        "data analyst",
        "reporting analyst",
        "insights",
        "strategy analyst",
        "financial analyst",
        "fp&a",
    ],
    "data analyst": [
        "data analyst",
        "analytics analyst",
        "business intelligence analyst",
        "bi analyst",
        "reporting analyst",
        "analytics engineer",
        "insights analyst",
    ],
    "product": [
        "product",
        "product manager",
        "product owner",
        "product operations",
    ],
    "engineer": [
        "engineer",
        "engineering",
        "developer",
        "software",
        "platform",
        "infrastructure",
    ],
}

LOCATION_ALIAS_GROUPS = {
    "boston": [
        "boston",
        "boston, ma",
        "greater boston",
        "cambridge",
        "somerville",
        "brookline",
        "quincy",
        "waltham",
        "newton",
        "watertown",
        "lexington",
        "needham",
        "massachusetts",
        "ma",
    ],
    "dallas": [
        "dallas",
        "dallas, tx",
        "plano",
        "frisco",
        "irving",
        "addison",
        "richardson",
        "carrollton",
        "texas",
        "tx",
    ],
    "new york": [
        "new york",
        "new york, ny",
        "nyc",
        "manhattan",
        "brooklyn",
        "queens",
        "bronx",
        "staten island",
        "new york state",
        "ny",
    ],
}


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("/", " ").replace("-", " ").split())


def expand_title_terms(target_titles: list[str]) -> list[str]:
    expanded: list[str] = []

    for raw_term in target_titles:
        term = normalize_text(raw_term)
        if not term:
            continue

        expanded.append(term)

        if term in TITLE_SYNONYM_GROUPS:
            expanded.extend(normalize_text(item) for item in TITLE_SYNONYM_GROUPS[term])

    return list(dict.fromkeys(expanded))


def expand_location_terms(preferred_locations: list[str]) -> list[str]:
    expanded: list[str] = []

    for raw_term in preferred_locations:
        term = normalize_text(raw_term)
        if not term:
            continue

        expanded.append(term)

        if term in LOCATION_ALIAS_GROUPS:
            expanded.extend(normalize_text(item) for item in LOCATION_ALIAS_GROUPS[term])

    return list(dict.fromkeys(expanded))
