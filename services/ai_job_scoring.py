from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


SCORE_VERSION = "v1"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_DESCRIPTION_CHARS = 6000
MAX_RESUME_CHARS = 8000

DEFAULT_PROFILE_PATHS = (
    "profile_context.txt",
    "data/profile_context.txt",
    "resume_profile.txt",
    "data/resume_profile.txt",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clamp_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _truncate_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _join_semicolon(values: Sequence[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return "; ".join(cleaned)


def _join_bullets(values: Sequence[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    if not cleaned:
        return ""
    return "\n".join(f"- {item}" for item in cleaned)


def fit_label_from_score(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Weak"
    return "Not Recommended"


def recommended_action_from_score(score: int) -> str:
    if score >= 80:
        return "Apply"
    if score >= 60:
        return "Apply with Caution"
    if score >= 40:
        return "Hold"
    return "Skip"


def _normalize_confidence(value: Any) -> str:
    if not value:
        return "Low"
    text = str(value).strip().lower()
    if text == "high":
        return "High"
    if text == "medium":
        return "Medium"
    return "Low"


def build_default_score_result(
    *,
    status: str = "skipped",
    model: str = DEFAULT_MODEL,
    fit_score: int = 0,
    match_summary: str = "",
    match_reasons: Optional[List[str]] = None,
    gaps_or_risks: Optional[List[str]] = None,
    resume_signals_used: Optional[List[str]] = None,
    confidence: str = "Low",
) -> Dict[str, Any]:
    fit_score = _clamp_score(fit_score)
    return {
        "score_version": SCORE_VERSION,
        "fit_score": fit_score,
        "fit_label": fit_label_from_score(fit_score),
        "confidence": _normalize_confidence(confidence),
        "recommended_action": recommended_action_from_score(fit_score),
        "match_summary": match_summary or "",
        "match_reasons": match_reasons or [],
        "gaps_or_risks": gaps_or_risks or [],
        "resume_signals_used": resume_signals_used or [],
        "scored_at": _utc_now_iso(),
        "model": model,
        "status": status,
    }


def normalize_score_result(payload: Dict[str, Any], *, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    fit_score = _clamp_score(payload.get("fit_score", 0))
    return {
        "score_version": payload.get("score_version") or SCORE_VERSION,
        "fit_score": fit_score,
        "fit_label": fit_label_from_score(fit_score),
        "confidence": _normalize_confidence(payload.get("confidence")),
        "recommended_action": recommended_action_from_score(fit_score),
        "match_summary": str(payload.get("match_summary") or ""),
        "match_reasons": [str(x) for x in (payload.get("match_reasons") or []) if str(x).strip()],
        "gaps_or_risks": [str(x) for x in (payload.get("gaps_or_risks") or []) if str(x).strip()],
        "resume_signals_used": [str(x) for x in (payload.get("resume_signals_used") or []) if str(x).strip()],
        "scored_at": payload.get("scored_at") or _utc_now_iso(),
        "model": payload.get("model") or model,
        "status": payload.get("status") or "scored",
    }


def build_scoring_input(job_payload: Dict[str, Any], resume_profile_text: str) -> Dict[str, Any]:
    description_text = (
        job_payload.get("description_text")
        or job_payload.get("job_description")
        or job_payload.get("page_text")
        or ""
    )

    salary_value = (
        job_payload.get("salary")
        or job_payload.get("compensation_raw")
        or ""
    )

    job_url_value = (
        job_payload.get("job_url")
        or job_payload.get("job_posting_url")
        or ""
    )

    return {
        "job": {
            "company": job_payload.get("company"),
            "title": job_payload.get("title"),
            "location": job_payload.get("location"),
            "salary": salary_value,
            "job_url": job_url_value,
            "description_text": _truncate_text(description_text, MAX_DESCRIPTION_CHARS),
            "normalized_title": job_payload.get("normalized_title"),
            "role_family": job_payload.get("role_family"),
            "remote_type": job_payload.get("remote_type"),
            "validation_status": job_payload.get("validation_status"),
            "validation_confidence": job_payload.get("validation_confidence"),
            "existing_fit_score": job_payload.get("fit_score"),
            "existing_fit_tier": job_payload.get("fit_tier"),
            "existing_match_rationale": job_payload.get("match_rationale"),
        },
        "resume_profile_text": _truncate_text(resume_profile_text, MAX_RESUME_CHARS),
    }


def build_scoring_prompt(job_payload: Dict[str, Any], resume_profile_text: str) -> str:
    scoring_input = build_scoring_input(job_payload, resume_profile_text)
    schema = {
        "fit_score": "integer from 0 to 100",
        "confidence": "High, Medium, or Low",
        "match_summary": "1 to 3 sentences",
        "match_reasons": ["bullet reason"],
        "gaps_or_risks": ["bullet risk"],
        "resume_signals_used": ["resume signal used in reasoning"],
    }
    return (
        "You are scoring how well a job matches a candidate profile.\n"
        "Return JSON only.\n"
        "Be conservative and evidence-based.\n"
        "Do not inflate scores for senior-sounding titles alone.\n"
        "Prefer low confidence when the job description is sparse.\n"
        "Penalize jobs that are clearly outside the candidate's likely background.\n"
        "Keep responses compact and specific.\n\n"
        "Scoring guidance:\n"
        "- 80 to 100: strong fit, likely worth applying\n"
        "- 60 to 79: plausible fit, some gaps or uncertainty\n"
        "- 40 to 59: weak fit, meaningful mismatch or ambiguity\n"
        "- 0 to 39: poor fit, major mismatch\n\n"
        f"Required JSON schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Scoring input:\n{json.dumps(scoring_input, indent=2)}"
    )


def _extract_response_text(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text

    output = getattr(response, "output", None) or []
    collected: List[str] = []

    for item in output:
        content = getattr(item, "content", None) or []
        for part in content:
            text_value = getattr(part, "text", None)
            if text_value:
                collected.append(text_value)

    return "\n".join(collected).strip()


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def resolve_profile_path(
    explicit_path: str | Path | None = None,
    candidate_paths: Optional[Sequence[str | Path]] = None,
) -> Optional[Path]:
    env_path = _clean(os.getenv("JOB_AGENT_RESUME_PROFILE", ""))
    candidates: List[Path] = []

    if explicit_path:
        candidates.append(Path(explicit_path))
    if env_path:
        candidates.append(Path(env_path))

    for candidate in (candidate_paths or DEFAULT_PROFILE_PATHS):
        candidates.append(Path(candidate))

    seen: set[str] = set()
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path.expanduser()

        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)

        if resolved.exists() and resolved.is_file():
            return resolved

    return None


def load_resume_profile_text(
    explicit_path: str | Path | None = None,
    candidate_paths: Optional[Sequence[str | Path]] = None,
) -> Tuple[str, str]:
    resolved = resolve_profile_path(explicit_path=explicit_path, candidate_paths=candidate_paths)
    if resolved is None:
        return "", ""

    try:
        text = resolved.read_text(encoding="utf-8").strip()
    except Exception:
        return "", ""

    if not text:
        return "", str(resolved)

    return text, str(resolved)


def apply_score_to_job_payload(job_payload: Dict[str, Any], score_result: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_score_result(score_result)

    job_payload["fit_score"] = normalized.get("fit_score", 0)
    job_payload["fit_tier"] = normalized.get("fit_label", "")
    job_payload["ai_priority"] = normalized.get("recommended_action", "")
    job_payload["match_rationale"] = _clean(normalized.get("match_summary", ""))
    job_payload["risk_flags"] = _join_semicolon(normalized.get("gaps_or_risks", []))
    job_payload["application_angle"] = _join_bullets(normalized.get("match_reasons", []))

    return job_payload


@dataclass
class AIJobScoringService:
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 30.0

    def _build_client(self) -> Optional[Any]:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or OpenAI is None:
            return None
        return OpenAI(api_key=api_key, timeout=self.timeout_seconds)

    def _call_model(self, prompt: str) -> Dict[str, Any]:
        client = self._build_client()
        if client is None:
            return build_default_score_result(
                status="skipped",
                model=self.model,
                fit_score=0,
                confidence="Low",
                match_summary="AI job scoring was skipped because the OpenAI client or API key is not available.",
                gaps_or_risks=["Missing OPENAI_API_KEY or openai package"],
            )

        response = client.responses.create(
            model=self.model,
            input=prompt,
        )

        raw_text = _extract_response_text(response)
        if not raw_text.strip():
            return build_default_score_result(
                status="error",
                model=self.model,
                fit_score=0,
                confidence="Low",
                match_summary="AI job scoring returned an empty response.",
                gaps_or_risks=["Empty model response"],
            )

        json_text = _extract_json_object(raw_text)

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            return build_default_score_result(
                status="error",
                model=self.model,
                fit_score=0,
                confidence="Low",
                match_summary="AI job scoring returned a non-JSON response.",
                gaps_or_risks=["Could not parse model response as JSON"],
            )

        parsed["status"] = "scored"
        parsed["model"] = self.model
        return normalize_score_result(parsed, model=self.model)

    def score_job(self, job_payload: Dict[str, Any], resume_profile_text: str) -> Dict[str, Any]:
        if not resume_profile_text or not resume_profile_text.strip():
            return build_default_score_result(
                status="skipped",
                model=self.model,
                fit_score=0,
                confidence="Low",
                match_summary="Resume/profile text was missing, so AI job scoring was skipped.",
                gaps_or_risks=["Missing resume/profile text"],
            )

        title = str(job_payload.get("title") or "").strip()
        description_text = str(
            job_payload.get("description_text")
            or job_payload.get("job_description")
            or job_payload.get("page_text")
            or ""
        ).strip()

        if not title and not description_text:
            return build_default_score_result(
                status="skipped",
                model=self.model,
                fit_score=0,
                confidence="Low",
                match_summary="Job content was too limited to score reliably.",
                gaps_or_risks=["Missing job title and description text"],
            )

        prompt = build_scoring_prompt(job_payload, resume_profile_text)

        try:
            result = self._call_model(prompt)
        except Exception as exc:
            result = build_default_score_result(
                status="error",
                model=self.model,
                fit_score=0,
                confidence="Low",
                match_summary="AI job scoring failed during model execution.",
                gaps_or_risks=[f"Model execution error: {type(exc).__name__}"],
            )

        result["debug_prompt_preview"] = prompt[:1500]
        return result


def score_accepted_job(job_payload: Dict[str, Any], resume_profile_text: str, *, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    service = AIJobScoringService(model=model)
    return service.score_job(job_payload, resume_profile_text)
