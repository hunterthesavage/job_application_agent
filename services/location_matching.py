from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


STATE_ABBREVIATIONS = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}

ABBREVIATION_TO_STATE = {abbr: name for name, abbr in STATE_ABBREVIATIONS.items()}

COUNTRY_ALIASES = {
    "us": "united states",
    "u s": "united states",
    "u.s": "united states",
    "u.s.": "united states",
    "usa": "united states",
    "u s a": "united states",
    "united states of america": "united states",
    "uk": "united kingdom",
    "u k": "united kingdom",
    "u.k": "united kingdom",
    "u.k.": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",
    "scotland": "united kingdom",
    "wales": "united kingdom",
}

PROVINCE_ABBREVIATIONS = {
    "alberta": "ab",
    "british columbia": "bc",
    "manitoba": "mb",
    "new brunswick": "nb",
    "newfoundland and labrador": "nl",
    "nova scotia": "ns",
    "ontario": "on",
    "prince edward island": "pe",
    "quebec": "qc",
    "saskatchewan": "sk",
    "northwest territories": "nt",
    "nunavut": "nu",
    "yukon": "yt",
}

ABBREVIATION_TO_PROVINCE = {abbr: name for name, abbr in PROVINCE_ABBREVIATIONS.items()}

REMOTE_PHRASES = [
    "remote",
    "work from home",
    "wfh",
    "distributed",
    "virtual",
    "telecommute",
    "telecommuting",
    "anywhere",
]

US_SCOPE_REMOTE_PHRASES = [
    "united states",
    "remote united states",
    "remote us",
    "us remote",
    "usa remote",
    "anywhere in us",
    "anywhere in the us",
    "us only",
    "usa only",
    "nationwide",
    "national",
]

HYBRID_PHRASES = [
    "hybrid",
]

SEPARATOR_PATTERN = re.compile(r"[,/|]+")
LEADING_NOISE_PATTERNS = [
    r"^remote\s+only\s+in\s+",
    r"^remote\s+only\s+",
    r"^remote\s+in\s+",
    r"^remote\s+",
    r"^hybrid\s+in\s+",
    r"^hybrid\s+",
    r"^based\s+in\s+",
    r"^located\s+in\s+",
    r"^anywhere\s+in\s+",
    r"^onsite\s+in\s+",
    r"^on\s+site\s+in\s+",
    r"^in\s+",
]


@dataclass(frozen=True)
class ParsedLocation:
    raw: str
    normalized: str
    city: str = ""
    region: str = ""
    country: str = ""
    is_remote: bool = False
    is_hybrid: bool = False
    is_us_scope_remote: bool = False
    is_blank: bool = False


def safe_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def normalize_text(value: object) -> str:
    text = safe_text(value).lower()
    if not text:
        return ""
    text = text.replace("&", " and ")
    text = re.sub(r"[\(\)\[\]]", " ", text)
    text = re.sub(r"[-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_part(value: str) -> str:
    text = normalize_text(value)
    text = text.replace(".", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_country(value: str) -> str:
    text = _clean_part(value)
    if not text:
        return ""
    return COUNTRY_ALIASES.get(text, text)


def canonical_region(value: str) -> str:
    text = _clean_part(value)
    if not text:
        return ""

    if text in STATE_ABBREVIATIONS:
        return STATE_ABBREVIATIONS[text]
    if text in ABBREVIATION_TO_STATE:
        return text

    if text in PROVINCE_ABBREVIATIONS:
        return PROVINCE_ABBREVIATIONS[text]
    if text in ABBREVIATION_TO_PROVINCE:
        return text

    return text


def canonical_city(value: str) -> str:
    text = _clean_part(value)
    if not text:
        return ""
    return text


def _contains_any_phrase(normalized_text: str, phrases: Iterable[str]) -> bool:
    return any(phrase in normalized_text for phrase in phrases)


def is_remote_location(location_text: str) -> bool:
    normalized = normalize_text(location_text)
    if not normalized:
        return False
    return _contains_any_phrase(normalized, REMOTE_PHRASES)


def is_hybrid_location(location_text: str) -> bool:
    normalized = normalize_text(location_text)
    if not normalized:
        return False
    return _contains_any_phrase(normalized, HYBRID_PHRASES)


def is_us_scope_location(location_text: str) -> bool:
    normalized = normalize_text(location_text)
    if not normalized:
        return False
    return _contains_any_phrase(normalized, US_SCOPE_REMOTE_PHRASES)


def _strip_leading_noise(value: str) -> str:
    text = normalize_text(value)
    changed = True
    while changed and text:
        changed = False
        for pattern in LEADING_NOISE_PATTERNS:
            updated = re.sub(pattern, "", text)
            if updated != text:
                text = updated.strip()
                changed = True
    return text


def _split_location_parts(value: str) -> list[str]:
    raw = safe_text(value)
    if not raw:
        return []

    normalized = _strip_leading_noise(raw)
    normalized = normalized.replace("metro area", "")
    normalized = normalized.replace("metropolitan area", "")

    parts = [_clean_part(part) for part in SEPARATOR_PATTERN.split(normalized)]
    return [part for part in parts if part]


def _is_known_country(part: str) -> bool:
    return canonical_country(part) in {"united states", "united kingdom", "canada"}


def _is_known_region(part: str) -> bool:
    region_candidate = canonical_region(part)
    return (
        region_candidate in STATE_ABBREVIATIONS.values()
        or region_candidate in PROVINCE_ABBREVIATIONS.values()
    )


def parse_location(location_text: str) -> ParsedLocation:
    raw = safe_text(location_text)
    normalized = normalize_text(raw)

    if not normalized:
        return ParsedLocation(
            raw=raw,
            normalized="",
            is_blank=True,
        )

    remote_flag = is_remote_location(raw)
    hybrid_flag = is_hybrid_location(raw)
    us_scope_flag = is_us_scope_location(raw)

    stripped_normalized = _strip_leading_noise(raw)
    parts = _split_location_parts(raw)

    if stripped_normalized and _is_known_country(stripped_normalized):
        return ParsedLocation(
            raw=raw,
            normalized=normalized,
            city="",
            region="",
            country=canonical_country(stripped_normalized),
            is_remote=remote_flag,
            is_hybrid=hybrid_flag,
            is_us_scope_remote=us_scope_flag,
            is_blank=False,
        )

    if stripped_normalized and _is_known_region(stripped_normalized):
        return ParsedLocation(
            raw=raw,
            normalized=normalized,
            city="",
            region=canonical_region(stripped_normalized),
            country="",
            is_remote=remote_flag,
            is_hybrid=hybrid_flag,
            is_us_scope_remote=us_scope_flag,
            is_blank=False,
        )

    city = ""
    region = ""
    country = ""

    filtered_parts = []
    for part in parts:
        if part in {"remote", "hybrid", "onsite", "on site"}:
            continue
        filtered_parts.append(part)

    for part in filtered_parts:
        if _is_known_country(part):
            country = canonical_country(part)
            continue

        if _is_known_region(part):
            region = canonical_region(part)
            continue

        if not city:
            city = canonical_city(part)

    return ParsedLocation(
        raw=raw,
        normalized=normalized,
        city=city,
        region=region,
        country=country,
        is_remote=remote_flag,
        is_hybrid=hybrid_flag,
        is_us_scope_remote=us_scope_flag,
        is_blank=False,
    )


def _same_region(left: ParsedLocation, right: ParsedLocation) -> bool:
    return bool(left.region and right.region and left.region == right.region)


def _same_city(left: ParsedLocation, right: ParsedLocation) -> bool:
    return bool(left.city and right.city and left.city == right.city)


def _structured_match(job_location: ParsedLocation, preferred_location: ParsedLocation) -> tuple[bool, str]:
    if preferred_location.is_blank:
        return False, "blank preferred location"

    if preferred_location.country and not preferred_location.city and not preferred_location.region:
        if job_location.country == preferred_location.country:
            return True, f"matched country '{preferred_location.country}'"
        return False, "country mismatch"

    if preferred_location.region and not preferred_location.city:
        if _same_region(job_location, preferred_location):
            return True, f"matched region '{preferred_location.region}'"
        return False, "region mismatch"

    if preferred_location.city and preferred_location.region:
        if _same_city(job_location, preferred_location) and _same_region(job_location, preferred_location):
            return True, f"matched city+region '{preferred_location.city}, {preferred_location.region}'"
        return False, "city_region mismatch"

    if preferred_location.city and not preferred_location.region:
        if _same_city(job_location, preferred_location):
            return True, f"matched city '{preferred_location.city}'"
        return False, "city mismatch"

    return False, "no structured match"


def _fallback_token_match(job_location: ParsedLocation, preferred_location: ParsedLocation) -> tuple[bool, str]:
    job_norm = job_location.normalized
    pref_norm = preferred_location.normalized

    if not job_norm or not pref_norm:
        return False, "blank normalized location"

    if pref_norm in job_norm:
        return True, f"matched normalized phrase '{pref_norm}'"

    pref_tokens = {token for token in pref_norm.split() if len(token) >= 2}
    job_tokens = {token for token in job_norm.split() if len(token) >= 2}

    if pref_tokens and pref_tokens.issubset(job_tokens):
        return True, "matched by token subset"

    return False, "no token match"


def location_matches_preference(job_location: str, preferred_locations: list[str]) -> tuple[bool, str]:
    parsed_job = parse_location(job_location)

    if not preferred_locations:
        return True, "no preferred location set"

    if parsed_job.is_blank:
        return False, "blank job location"

    for preferred in preferred_locations:
        parsed_pref = parse_location(preferred)

        matched, reason = _structured_match(parsed_job, parsed_pref)
        if matched:
            return True, f"{reason} from '{preferred}'"

        matched, reason = _fallback_token_match(parsed_job, parsed_pref)
        if matched:
            return True, f"{reason} from '{preferred}'"

    return False, "no preferred location match"


def evaluate_location_filters(job_location: str, preferred_locations: list[str], remote_only: bool) -> tuple[bool, str]:
    parsed_job = parse_location(job_location)

    if remote_only:
        if parsed_job.is_remote:
            return True, "remote_only matched remote location"
        if parsed_job.is_us_scope_remote:
            return True, "remote_only matched us-scope location"
        return False, "remote_only_gate"

    if parsed_job.is_remote:
        return True, "matched remote location"

    if parsed_job.is_us_scope_remote:
        return True, "matched us-scope location"

    if not preferred_locations:
        if not parsed_job.is_blank:
            return True, "no preferred location set"
        return False, "blank_location_gate"

    matched, reason = location_matches_preference(job_location, preferred_locations)
    if matched:
        return True, reason

    return False, "settings_location_gate"


class BaseLocationResolver:
    def resolve(self, location_text: str) -> ParsedLocation:
        return parse_location(location_text)


class NullLocationResolver(BaseLocationResolver):
    pass


DEFAULT_LOCATION_RESOLVER = NullLocationResolver()


def resolve_location(location_text: str, resolver: BaseLocationResolver | None = None) -> ParsedLocation:
    active_resolver = resolver or DEFAULT_LOCATION_RESOLVER
    return active_resolver.resolve(location_text)
