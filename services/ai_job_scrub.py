from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.ai_job_scoring import _clean, _clean_list, _extract_json_object, _extract_response_text
from services.openai_key import get_effective_openai_api_key

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


DEFAULT_MODEL = "gpt-4.1-mini"


def _normalize_confidence(value: Any) -> str:
    text = _clean(value).lower()
    if text == "high":
        return "High"
    if text == "medium":
        return "Medium"
    return "Low"


def _merge_text_items(*parts: Any) -> str:
    merged: list[str] = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, (list, tuple)):
            items = _clean_list(part)
        else:
            items = [item.strip() for item in str(part).split(";") if item.strip()]
        for item in items:
            if item not in merged:
                merged.append(item)
    return "; ".join(merged)


def normalize_scrub_result(payload: Dict[str, Any], *, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    scrub_status = str(payload.get("scrub_status") or "review").strip().lower()
    if scrub_status not in {"clean", "review", "reject"}:
        scrub_status = "review"

    return {
        "scrub_status": scrub_status,
        "scrub_summary": str(payload.get("scrub_summary") or ""),
        "scrub_flags": _clean_list(payload.get("scrub_flags")),
        "scrub_confidence": _normalize_confidence(payload.get("scrub_confidence")),
        "corrected_title": _clean(payload.get("corrected_title")),
        "corrected_company": _clean(payload.get("corrected_company")),
        "corrected_compensation_raw": _clean(payload.get("corrected_compensation_raw")),
        "correction_confidence": _normalize_confidence(payload.get("correction_confidence")),
        "correction_notes": _clean_list(payload.get("correction_notes")),
        "model": str(payload.get("model") or model),
        "status": str(payload.get("status") or "scrubbed"),
    }


def build_default_scrub_result(
    *,
    scrub_status: str = "review",
    scrub_summary: str = "",
    scrub_flags: Optional[List[str]] = None,
    scrub_confidence: str = "Low",
    corrected_title: str = "",
    corrected_company: str = "",
    corrected_compensation_raw: str = "",
    correction_confidence: str = "Low",
    correction_notes: Optional[List[str]] = None,
    model: str = DEFAULT_MODEL,
    status: str = "skipped",
) -> Dict[str, Any]:
    return normalize_scrub_result(
        {
            "scrub_status": scrub_status,
            "scrub_summary": scrub_summary,
            "scrub_flags": scrub_flags or [],
            "scrub_confidence": scrub_confidence,
            "corrected_title": corrected_title,
            "corrected_company": corrected_company,
            "corrected_compensation_raw": corrected_compensation_raw,
            "correction_confidence": correction_confidence,
            "correction_notes": correction_notes or [],
            "model": model,
            "status": status,
        },
        model=model,
    )


def build_scrub_input(job_payload: Dict[str, Any], resume_profile_text: str) -> Dict[str, Any]:
    return {
        "job": {
            "company": job_payload.get("company"),
            "title": job_payload.get("title"),
            "normalized_title": job_payload.get("normalized_title"),
            "role_family": job_payload.get("role_family"),
            "location": job_payload.get("location"),
            "remote_type": job_payload.get("remote_type"),
            "validation_status": job_payload.get("validation_status"),
            "validation_confidence": job_payload.get("validation_confidence"),
            "fit_score": job_payload.get("fit_score"),
            "fit_tier": job_payload.get("fit_tier"),
            "ai_priority": job_payload.get("ai_priority"),
            "match_rationale": job_payload.get("match_rationale"),
            "risk_flags": job_payload.get("risk_flags"),
            "application_angle": job_payload.get("application_angle"),
            "compensation_raw": job_payload.get("compensation_raw"),
            "job_posting_url": job_payload.get("job_posting_url"),
            "description_text": job_payload.get("description_text"),
        },
        "resume_profile_text": resume_profile_text,
    }


def build_scrub_prompt(job_payload: Dict[str, Any], resume_profile_text: str) -> str:
    scrub_input = build_scrub_input(job_payload, resume_profile_text)
    schema = {
        "scrub_status": "clean, review, or reject",
        "scrub_summary": "1 to 2 sentences",
        "scrub_flags": ["specific concern"],
        "scrub_confidence": "High, Medium, or Low",
        "corrected_title": "blank unless page evidence strongly supports a more accurate title",
        "corrected_company": "blank unless page evidence strongly supports a more accurate company name",
        "corrected_compensation_raw": "blank unless page evidence strongly supports a more accurate compensation string",
        "correction_confidence": "High, Medium, or Low",
        "correction_notes": ["short note explaining a high-confidence correction"],
    }

    return (
        "You are doing a final sanity check on a job that already passed qualification and scoring.\n"
        "Return JSON only.\n"
        "Be conservative.\n"
        "Focus on only three questions:\n"
        "1. Is this role in the right functional and seniority lane?\n"
        "2. Does the parsed job look internally consistent?\n"
        "3. Is there enough concrete job description evidence to trust the current score?\n\n"
        "Use scrub_status values:\n"
        "- clean: no meaningful contradiction found\n"
        "- review: some ambiguity or evidence gaps exist\n"
        "- reject: strong contradiction or clear mismatch exists\n\n"
        "Only return corrected_title, corrected_company, or corrected_compensation_raw when the page evidence is strong.\n"
        "If confidence is not High, leave correction fields blank.\n"
        "Do not guess or normalize stylistically. Only correct fields that appear materially wrong or incomplete.\n\n"
        f"Required JSON schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Scrub input:\n{json.dumps(scrub_input, indent=2)}"
    )


@dataclass
class AIJobScrubService:
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 30.0

    def _build_client(self) -> Optional[Any]:
        api_key = get_effective_openai_api_key()
        if not api_key or OpenAI is None:
            return None
        return OpenAI(api_key=api_key, timeout=self.timeout_seconds)

    def _call_model(self, prompt: str) -> Dict[str, Any]:
        client = self._build_client()
        if client is None:
            return build_default_scrub_result(
                scrub_status="review",
                scrub_summary="AI scrub was skipped because the OpenAI client or API key is not available.",
                scrub_flags=["Missing saved or environment OpenAI API key, or openai package"],
                scrub_confidence="Low",
                model=self.model,
                status="skipped",
            )

        response = client.responses.create(
            model=self.model,
            input=prompt,
        )

        raw_text = _extract_response_text(response)
        if not raw_text.strip():
            return build_default_scrub_result(
                scrub_status="review",
                scrub_summary="AI scrub returned an empty response.",
                scrub_flags=["Empty model response"],
                scrub_confidence="Low",
                model=self.model,
                status="error",
            )

        try:
            parsed = json.loads(_extract_json_object(raw_text))
        except json.JSONDecodeError:
            return build_default_scrub_result(
                scrub_status="review",
                scrub_summary="AI scrub returned a non-JSON response.",
                scrub_flags=["Could not parse model response as JSON"],
                scrub_confidence="Low",
                model=self.model,
                status="error",
            )

        parsed["model"] = self.model
        parsed["status"] = "scrubbed"
        return normalize_scrub_result(parsed, model=self.model)

    def scrub_job(self, job_payload: Dict[str, Any], resume_profile_text: str) -> Dict[str, Any]:
        if not _clean(resume_profile_text):
            return build_default_scrub_result(
                scrub_status="review",
                scrub_summary="AI scrub was skipped because resume/profile text was missing.",
                scrub_flags=["Missing resume/profile text"],
                scrub_confidence="Low",
                model=self.model,
                status="skipped",
            )

        if not _clean(job_payload.get("title")) and not _clean(job_payload.get("description_text")):
            return build_default_scrub_result(
                scrub_status="review",
                scrub_summary="AI scrub was skipped because job content was too limited.",
                scrub_flags=["Missing job title and description text"],
                scrub_confidence="Low",
                model=self.model,
                status="skipped",
            )

        prompt = build_scrub_prompt(job_payload, resume_profile_text)
        result = self._call_model(prompt)
        result["debug_prompt_preview"] = prompt[:1500]
        return result


def apply_scrub_to_job_payload(job_payload: Dict[str, Any], scrub_result: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_scrub_result(scrub_result)

    correction_notes = list(normalized.get("correction_notes", []))
    description_text = _clean(job_payload.get("description_text"))
    title_or_company_changed = False

    if description_text and normalized.get("correction_confidence") == "High":
        field_specs = [
            ("corrected_title", "title", "Title"),
            ("corrected_company", "company", "Company"),
            ("corrected_compensation_raw", "compensation_raw", "Compensation"),
        ]
        for corrected_key, payload_key, label in field_specs:
            corrected_value = _clean(normalized.get(corrected_key, ""))
            current_value = _clean(job_payload.get(payload_key, ""))
            if not corrected_value or corrected_value == current_value:
                continue

            job_payload[payload_key] = corrected_value
            correction_notes.append(f"AI scrub corrected {label} to {corrected_value}")

            if payload_key in {"title", "company"}:
                title_or_company_changed = True

        if title_or_company_changed:
            job_payload["duplicate_key"] = ""
            job_payload["normalized_title"] = ""

    job_payload["risk_flags"] = _merge_text_items(
        job_payload.get("risk_flags", ""),
        normalized.get("scrub_flags", []),
        correction_notes,
    )

    scrub_status = normalized.get("scrub_status", "review")
    if scrub_status == "reject":
        job_payload["ai_priority"] = "Skip"
    elif scrub_status == "review" and _clean(job_payload.get("ai_priority")) == "Apply":
        job_payload["ai_priority"] = "Hold"

    return job_payload


def scrub_accepted_job(job_payload: Dict[str, Any], resume_profile_text: str, *, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    service = AIJobScrubService(model=model)
    return service.scrub_job(job_payload, resume_profile_text)
