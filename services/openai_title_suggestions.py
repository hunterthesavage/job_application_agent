
from __future__ import annotations

import json
import os
import re

import requests

from services.openai_key import get_effective_openai_api_key


OPENAI_TITLE_SUGGEST_MODEL = os.getenv("JOB_AGENT_OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def _clean_title(title: str) -> str:
    text = str(title or "").strip()
    text = " ".join(text.split())
    return text


def _unique_titles(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []

    for value in values:
        cleaned = _clean_title(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(cleaned)

    return results


def _clean_location(value: str) -> str:
    text = str(value or "").strip()
    text = " ".join(text.split())
    return text


def _parse_location_lines(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    if "\n" in text:
        return [part.strip() for part in text.splitlines() if part.strip()]
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    return [text]


def _unique_locations(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []

    for value in values:
        cleaned = _clean_location(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(cleaned)

    return results


ROLE_PREFIX_TOKENS = {"manager", "mgr", "director", "dir"}


def _tokenize_title(value: str) -> list[str]:
    cleaned = _clean_title(value).lower().replace("/", " ")
    return [part for part in cleaned.replace(",", " ").split() if part]


def _is_close_title_variant(main_title: str, variant: str) -> bool:
    main_clean = _clean_title(main_title)
    variant_clean = _clean_title(variant)
    if not main_clean or not variant_clean:
        return False

    lowered_variant = variant_clean.lower()
    if re.search(r"\bvice pres\b", lowered_variant):
        return False

    main_tokens = _tokenize_title(main_clean)
    variant_tokens = _tokenize_title(variant_clean)
    if not main_tokens or not variant_tokens:
        return False

    main_first = main_tokens[0]
    variant_first = variant_tokens[0]
    if main_first not in ROLE_PREFIX_TOKENS and variant_first in ROLE_PREFIX_TOKENS:
        return False

    return True


def _build_prompt(
    current_titles: str,
    profile_summary: str = "",
    resume_text: str = "",
    include_keywords: str = "",
    max_titles: int = 6,
) -> str:
    return f"""
You are helping a job seeker broaden executive and senior technology role titles for job search.

Return strict JSON with this shape:
{{
  "titles": ["Title 1", "Title 2"],
  "notes": "One short sentence"
}}

Rules:
- Return only JSON.
- Suggest up to {max_titles} titles total.
- Keep titles in the same seniority band as the input.
- Keep titles in the same functional lane unless the profile strongly supports a nearby adjacent lane.
- Prefer close ATS-friendly variants first, then only the most relevant adjacent titles.
- Focus on SaaS, AI, enterprise software, platform, digital, IT, and technology leadership roles only when supported by the input.
- Avoid broad drift into unrelated executive areas like sales, finance, HR, legal, or operations unless explicitly supported.
- Avoid duplicates.
- Do not include obviously junior titles.
- Prefer titles that are likely to appear in ATS systems and company career sites.
- Be conservative. Fewer, tighter titles are better than broad coverage.

Current target titles:
{current_titles}

Profile summary:
{profile_summary}

Resume text:
{resume_text[:4000]}

Include keywords:
{include_keywords}
""".strip()


def _build_title_group_prompt(
    main_titles: list[str],
    profile_summary: str = "",
    resume_text: str = "",
    include_keywords: str = "",
    max_variants_per_title: int = 5,
) -> str:
    title_lines = "\n".join(f"- {title}" for title in main_titles if _clean_title(title))
    return f"""
You are helping a job seeker expand each job title into close ATS-friendly subtitle variants.

Return strict JSON with this shape:
{{
  "title_groups": [
    {{
      "main_title": "VP of IT",
      "variants": ["Vice President of IT", "VP Information Technology"]
    }}
  ],
  "notes": "One short sentence"
}}

Rules:
- Return JSON only.
- For each main title, return up to {max_variants_per_title} variants.
- Keep each variant very close to the main title.
- Keep the same seniority band and the same functional lane.
- Prioritize only level variance and abbreviation variance when they make sense.
- Examples of allowed behavior: Manager vs Mgr, Director vs Dir, VP vs Vice President, IT vs Information Technology, AI vs Artificial Intelligence.
- Prefer standard ATS phrasing and natural word order.
- Do not create awkward inversions like `Manager Information Technology` or `Mgr IT` when the natural title is `IT Manager`.
- Do not shorten words into partial fragments like `Vice Pres`.
- Do not invent adjacent roles that materially change scope or function.
- Do not include the main title again in the variants list.
- If a title does not need variants, return an empty list for that title.
- Prefer ATS-friendly wording that is likely to appear on real career sites.
- Be conservative. Tight variants are better than broad brainstorming.
- Avoid duplicates.

Main titles:
{title_lines}

Profile summary:
{profile_summary}

Resume text:
{resume_text[:4000]}

Include keywords:
{include_keywords}
""".strip()


def _build_run_input_refinement_prompt(
    current_titles: str,
    preferred_locations: str = "",
    profile_summary: str = "",
    resume_text: str = "",
    include_keywords: str = "",
    include_remote: bool = True,
    max_titles: int = 6,
    max_locations: int = 6,
) -> str:
    return f"""
You are helping a job seeker tighten and normalize their job-search inputs before a run.

Return strict JSON with this shape:
{{
  "titles": ["Title 1", "Title 2"],
  "locations": ["Location 1", "Location 2"],
  "notes": "One short sentence"
}}

Rules:
- Return only JSON.
- Suggest up to {max_titles} additional titles total.
- Suggest up to {max_locations} normalized location entries total.
- Keep titles in the same seniority band as the input.
- Keep titles in the same functional lane unless the profile strongly supports a nearby adjacent lane.
- Normalize locations into clean search-friendly entries, one geographic target per item.
- Prefer replacing loose umbrella fragments with clean structured locations when you can infer them safely.
- Do not invent new geographies outside what the user clearly implied.
- If remote-only is enabled, keep `Remote` as one location when appropriate.
- Prefer conservative cleanup over broad expansion.
- Avoid duplicates.

Current target titles:
{current_titles}

Current preferred locations:
{preferred_locations}

Include remote:
{"true" if include_remote else "false"}

Profile summary:
{profile_summary}

Resume text:
{resume_text[:4000]}

Include keywords:
{include_keywords}
""".strip()


def suggest_titles_with_openai(
    current_titles: str,
    profile_summary: str = "",
    resume_text: str = "",
    include_keywords: str = "",
    max_titles: int = 6,
) -> dict[str, object]:
    api_key = get_effective_openai_api_key()
    if not api_key:
        return {
            "ok": False,
            "error": "No OpenAI API key is available. Add a key in Settings or Setup Wizard first.",
            "titles": [],
            "notes": "",
        }

    suggestion_limit = max(1, min(int(max_titles or 6), 10))

    prompt = _build_prompt(
        current_titles=current_titles,
        profile_summary=profile_summary,
        resume_text=resume_text,
        include_keywords=include_keywords,
        max_titles=suggestion_limit,
    )

    payload = {
        "model": OPENAI_TITLE_SUGGEST_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You expand job-search titles and return strict JSON only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.4,
    }

    headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        raw = response.text
        data = json.loads(raw)
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = json.loads(content or "{}")
        titles = _unique_titles(parsed.get("titles", []))[:suggestion_limit]
        notes = str(parsed.get("notes", "") or "").strip()

        if not titles:
            return {
                "ok": False,
                "error": "OpenAI returned no title suggestions.",
                "titles": [],
                "notes": notes,
            }

        return {
            "ok": True,
            "error": "",
            "titles": titles,
            "notes": notes,
            "model": OPENAI_TITLE_SUGGEST_MODEL,
        }

    except requests.HTTPError as exc:
        try:
            detail = exc.response.text
        except Exception:
            detail = str(exc)
        return {
            "ok": False,
            "error": f"OpenAI request failed ({getattr(exc.response, 'status_code', 'unknown')}). {detail}",
            "titles": [],
            "notes": "",
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "titles": [],
            "notes": "",
        }


def suggest_title_groups_with_openai(
    main_titles: list[str],
    profile_summary: str = "",
    resume_text: str = "",
    include_keywords: str = "",
    max_variants_per_title: int = 5,
) -> dict[str, object]:
    api_key = get_effective_openai_api_key()
    cleaned_titles = _unique_titles(main_titles)
    if not api_key:
        return {
            "ok": False,
            "error": "No OpenAI API key is available. Add a key in Settings or Setup Wizard first.",
            "title_groups": [],
            "notes": "",
        }
    if not cleaned_titles:
        return {
            "ok": False,
            "error": "No titles were provided for subtitle generation.",
            "title_groups": [],
            "notes": "",
        }

    variant_limit = max(0, min(int(max_variants_per_title or 5), 5))
    prompt = _build_title_group_prompt(
        main_titles=cleaned_titles,
        profile_summary=profile_summary,
        resume_text=resume_text,
        include_keywords=include_keywords,
        max_variants_per_title=variant_limit,
    )

    payload = {
        "model": OPENAI_TITLE_SUGGEST_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You expand job-search titles into tight subtitle variants and return strict JSON only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        raw = json.loads(response.text)
        content = (
            raw.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = json.loads(content or "{}")
        raw_groups = parsed.get("title_groups", [])
        notes = str(parsed.get("notes", "") or "").strip()

        normalized_groups: list[dict[str, object]] = []
        for main_title in cleaned_titles:
            raw_group = next(
                (
                    group for group in raw_groups
                    if isinstance(group, dict)
                    and _clean_title(group.get("main_title", ""))
                    and _clean_title(group.get("main_title", "")).casefold() == main_title.casefold()
                ),
                {},
            ) if isinstance(raw_groups, list) else {}
            variants = _unique_titles(list(raw_group.get("variants", []) or []))[:variant_limit]
            variants = [variant for variant in variants if variant.casefold() != main_title.casefold()]
            variants = [variant for variant in variants if _is_close_title_variant(main_title, variant)]
            normalized_groups.append(
                {
                    "main_title": main_title,
                    "variants": variants,
                }
            )

        return {
            "ok": True,
            "error": "",
            "title_groups": normalized_groups,
            "notes": notes,
            "model": OPENAI_TITLE_SUGGEST_MODEL,
        }
    except requests.HTTPError as exc:
        try:
            detail = exc.response.text
        except Exception:
            detail = str(exc)
        return {
            "ok": False,
            "error": f"OpenAI request failed ({getattr(exc.response, 'status_code', 'unknown')}). {detail}",
            "title_groups": [],
            "notes": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "title_groups": [],
            "notes": "",
        }


def suggest_run_input_refinements_with_openai(
    current_titles: str,
    preferred_locations: str = "",
    profile_summary: str = "",
    resume_text: str = "",
    include_keywords: str = "",
    include_remote: bool = True,
    max_titles: int = 6,
    max_locations: int = 6,
) -> dict[str, object]:
    api_key = get_effective_openai_api_key()
    if not api_key:
        return {
            "ok": False,
            "error": "No OpenAI API key is available. Add a key in Settings or Setup Wizard first.",
            "titles": [],
            "locations": [],
            "notes": "",
        }

    title_limit = max(1, min(int(max_titles or 6), 10))
    location_limit = max(1, min(int(max_locations or 6), 10))

    prompt = _build_run_input_refinement_prompt(
        current_titles=current_titles,
        preferred_locations=preferred_locations,
        profile_summary=profile_summary,
        resume_text=resume_text,
        include_keywords=include_keywords,
        include_remote=include_remote,
        max_titles=title_limit,
        max_locations=location_limit,
    )

    payload = {
        "model": OPENAI_TITLE_SUGGEST_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You normalize job-search inputs and return strict JSON only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        raw = response.text
        data = json.loads(raw)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content or "{}")
        titles = _unique_titles(parsed.get("titles", []))[:title_limit]
        locations = _unique_locations(parsed.get("locations", []))[:location_limit]
        notes = str(parsed.get("notes", "") or "").strip()

        return {
            "ok": True,
            "error": "",
            "titles": titles,
            "locations": locations,
            "notes": notes,
            "model": OPENAI_TITLE_SUGGEST_MODEL,
        }
    except requests.HTTPError as exc:
        try:
            detail = exc.response.text
        except Exception:
            detail = str(exc)
        return {
            "ok": False,
            "error": f"OpenAI request failed ({getattr(exc.response, 'status_code', 'unknown')}). {detail}",
            "titles": [],
            "locations": [],
            "notes": "",
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "titles": [],
            "locations": [],
            "notes": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "titles": [],
            "locations": [],
            "notes": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "titles": [],
            "notes": "",
        }
