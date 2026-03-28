
from __future__ import annotations

import json
import os

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
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "titles": [],
            "notes": "",
        }
