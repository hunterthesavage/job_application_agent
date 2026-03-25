from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from services.openai_key import get_effective_openai_api_key


OPENAI_PROFILE_TEMPLATE_MODEL = os.getenv("JOB_AGENT_OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _build_prompt(resume_text: str) -> str:
    return f"""
You are helping a job seeker set up an AI-assisted local job search app.

Using only the resume text below, return strict JSON with this shape:
{{
  "profile_summary": "2 to 4 sentences",
  "strengths_to_highlight": "One item per line",
  "cover_letter_voice": "1 to 2 sentences"
}}

Rules:
- Return only JSON.
- Be specific, concise, and professional.
- Do not invent employers, metrics, certifications, or titles that are not supported by the resume.
- Write the summary as a reusable executive or senior-professional profile.
- Write strengths_to_highlight as short, high-signal strengths separated by newline characters.
- Write cover_letter_voice as guidance for how a tailored cover letter should sound.
- Do not include contact info.
- Do not include markdown.

Resume text:
{resume_text[:12000]}
""".strip()


def generate_profile_context_from_resume(resume_text: str) -> dict[str, object]:
    cleaned_resume = str(resume_text or "").strip()
    if not cleaned_resume:
        return {
            "ok": False,
            "error": "Paste resume text first, then generate the profile from that resume.",
            "profile_summary": "",
            "strengths_to_highlight": "",
            "cover_letter_voice": "",
        }

    api_key = get_effective_openai_api_key()
    if not api_key:
        return {
            "ok": False,
            "error": "No OpenAI API key is available. Add a key first, then generate the profile from the resume text.",
            "profile_summary": "",
            "strengths_to_highlight": "",
            "cover_letter_voice": "",
        }

    payload = {
        "model": OPENAI_PROFILE_TEMPLATE_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You generate structured candidate profile context from resume text and return strict JSON only.",
            },
            {
                "role": "user",
                "content": _build_prompt(cleaned_resume),
            },
        ],
        "temperature": 0.3,
    }

    request = urllib.request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = json.loads(content or "{}")

        profile_summary = str(parsed.get("profile_summary", "") or "").strip()
        strengths_to_highlight = str(parsed.get("strengths_to_highlight", "") or "").strip()
        cover_letter_voice = str(parsed.get("cover_letter_voice", "") or "").strip()

        if not profile_summary and not strengths_to_highlight and not cover_letter_voice:
            return {
                "ok": False,
                "error": "OpenAI returned an empty profile response.",
                "profile_summary": "",
                "strengths_to_highlight": "",
                "cover_letter_voice": "",
            }

        return {
            "ok": True,
            "error": "",
            "profile_summary": profile_summary,
            "strengths_to_highlight": strengths_to_highlight,
            "cover_letter_voice": cover_letter_voice,
            "model": OPENAI_PROFILE_TEMPLATE_MODEL,
        }

    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        return {
            "ok": False,
            "error": f"OpenAI request failed ({exc.code}). {detail}",
            "profile_summary": "",
            "strengths_to_highlight": "",
            "cover_letter_voice": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenAI request failed. {exc}",
            "profile_summary": "",
            "strengths_to_highlight": "",
            "cover_letter_voice": "",
        }
