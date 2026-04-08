from __future__ import annotations

import json
import uuid
from typing import Any

from services.search_plan import dedupe_preserve_order, parse_title_entries


MAX_MAIN_TITLES = 10
MAX_SUBTITLE_VARIANTS = 5

SEARCH_TOKEN_EXPANSIONS = {
    "ai": "artificial intelligence",
    "avp": "assistant vice president",
    "dir": "director",
    "eng": "engineering",
    "evp": "executive vice president",
    "hr": "human resources",
    "infra": "infrastructure",
    "it": "information technology",
    "mgr": "manager",
    "ops": "operations",
    "sr": "senior",
    "strat": "strategy",
    "svp": "senior vice president",
    "svc": "service",
    "svcs": "services",
    "tech": "technology",
    "trans": "transformation",
    "vp": "vice president",
}

SEARCH_ROLE_PREFIX_PATTERNS = [
    ["executive", "vice", "president"],
    ["assistant", "vice", "president"],
    ["senior", "vice", "president"],
    ["vice", "president"],
    ["senior", "manager"],
    ["managing", "director"],
    ["senior", "director"],
    ["manager"],
    ["director"],
    ["head"],
    ["chief"],
]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _normalized_key(value: Any) -> str:
    text = _safe_text(value)
    return text.casefold()


def _expand_search_title_tokens(value: Any) -> list[str]:
    text = (
        _safe_text(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .replace("&", " and ")
    )
    tokens: list[str] = []
    for raw_token in text.split():
        token = raw_token.strip(".")
        if not token:
            continue
        replacement = SEARCH_TOKEN_EXPANSIONS.get(token)
        if replacement:
            tokens.extend(replacement.split())
        else:
            tokens.append(token)
    return tokens


def _role_prefix_length(tokens: list[str]) -> int:
    for pattern in SEARCH_ROLE_PREFIX_PATTERNS:
        if tokens[: len(pattern)] == pattern:
            return len(pattern)
    return 0


def canonicalize_search_title(value: Any) -> str:
    tokens = _expand_search_title_tokens(value)
    if not tokens:
        return ""

    prefix_length = _role_prefix_length(tokens)
    if prefix_length:
        prefix = tokens[:prefix_length]
        remainder = tokens[prefix_length:]
        if remainder and remainder[0] != "of":
            tokens = prefix + ["of"] + remainder

    return " ".join(tokens)


def _new_group_id() -> str:
    return f"title-group-{uuid.uuid4().hex[:8]}"


def normalize_title_variants(raw_variants: list[dict[str, Any]] | None, *, main_title: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = {_normalized_key(main_title)}

    for raw_variant in raw_variants or []:
        if not isinstance(raw_variant, dict):
            continue
        title = _safe_text(raw_variant.get("title", ""))
        if not title:
            continue
        key = _normalized_key(title)
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "title": title,
                "selected": bool(raw_variant.get("selected", True)),
                "source": _safe_text(raw_variant.get("source", "")) or "ai",
            }
        )
        if len(normalized) >= MAX_SUBTITLE_VARIANTS:
            break

    return normalized


def normalize_title_groups(raw_groups: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_main_titles: set[str] = set()

    for raw_group in raw_groups or []:
        if not isinstance(raw_group, dict):
            continue
        main_title = _safe_text(raw_group.get("main_title", ""))
        if not main_title:
            continue
        key = _normalized_key(main_title)
        if not key or key in seen_main_titles:
            continue
        seen_main_titles.add(key)
        normalized.append(
            {
                "id": _safe_text(raw_group.get("id", "")) or _new_group_id(),
                "main_title": main_title,
                "variants": normalize_title_variants(raw_group.get("variants", []), main_title=main_title),
            }
        )
        if len(normalized) >= MAX_MAIN_TITLES:
            break

    return normalized


def create_empty_title_group() -> dict[str, Any]:
    return {
        "id": _new_group_id(),
        "main_title": "",
        "variants": [],
    }


def parse_title_groups_setting(value: str) -> list[dict[str, Any]]:
    raw_text = _safe_text(value)
    if not raw_text:
        return []
    try:
        data = json.loads(raw_text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return normalize_title_groups(data)


def load_title_groups_from_settings(settings: dict[str, Any]) -> list[dict[str, Any]]:
    structured = parse_title_groups_setting(settings.get("target_title_groups", ""))
    if structured:
        return structured

    legacy_titles = dedupe_preserve_order(parse_title_entries(settings.get("target_titles", "")))
    return normalize_title_groups(
        [
            {
                "main_title": title,
                "variants": [],
            }
            for title in legacy_titles
        ]
    )


def serialize_title_groups(groups: list[dict[str, Any]]) -> str:
    normalized = normalize_title_groups(groups)
    if not normalized:
        return ""
    return json.dumps(normalized, ensure_ascii=True)


def build_effective_title_list(groups: list[dict[str, Any]]) -> list[str]:
    normalized = normalize_title_groups(groups)
    effective: list[str] = []

    for group in normalized:
        main_title = _safe_text(group.get("main_title", ""))
        if main_title:
            effective.append(main_title)
        for variant in group.get("variants", []):
            if not isinstance(variant, dict):
                continue
            if not bool(variant.get("selected", True)):
                continue
            title = _safe_text(variant.get("title", ""))
            if title:
                effective.append(title)

    return dedupe_preserve_order(effective)


def build_effective_titles_text(groups: list[dict[str, Any]]) -> str:
    titles = build_effective_title_list(groups)
    return "\n".join(titles)


def build_search_title_list(groups: list[dict[str, Any]]) -> list[str]:
    normalized = normalize_title_groups(groups)
    search_titles: list[str] = []

    for group in normalized:
        candidates = [_safe_text(group.get("main_title", ""))]
        for variant in group.get("variants", []):
            if not isinstance(variant, dict):
                continue
            if not bool(variant.get("selected", True)):
                continue
            candidates.append(_safe_text(variant.get("title", "")))

        for candidate in candidates:
            canonical = canonicalize_search_title(candidate)
            if canonical:
                search_titles.append(canonical)

    return dedupe_preserve_order(search_titles)


def build_search_titles_text(groups: list[dict[str, Any]]) -> str:
    return "\n".join(build_search_title_list(groups))


def merge_ai_variants_into_groups(
    existing_groups: list[dict[str, Any]],
    ai_variants_by_main_title: dict[str, list[str]],
) -> list[dict[str, Any]]:
    normalized_existing = normalize_title_groups(existing_groups)
    merged_groups: list[dict[str, Any]] = []

    for group in normalized_existing:
        main_title = _safe_text(group.get("main_title", ""))
        existing_variants = normalize_title_variants(group.get("variants", []), main_title=main_title)
        existing_by_key = {
            _normalized_key(variant.get("title", "")): variant
            for variant in existing_variants
        }
        ai_titles = ai_variants_by_main_title.get(main_title, [])
        merged_variants: list[dict[str, Any]] = []
        for ai_title in ai_titles[:MAX_SUBTITLE_VARIANTS]:
            title = _safe_text(ai_title)
            if not title:
                continue
            key = _normalized_key(title)
            existing_variant = existing_by_key.get(key)
            merged_variants.append(
                {
                    "title": title,
                    "selected": bool(existing_variant.get("selected", True)) if existing_variant else True,
                    "source": "ai",
                }
            )
        merged_groups.append(
            {
                "id": group.get("id", "") or _new_group_id(),
                "main_title": main_title,
                "variants": normalize_title_variants(merged_variants, main_title=main_title),
            }
        )

    return normalize_title_groups(merged_groups)
