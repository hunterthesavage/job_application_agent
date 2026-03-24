from services.ai_job_scoring import (
    apply_score_to_job_payload,
    build_default_score_result,
    normalize_score_result,
)
from services.openai_key import get_effective_openai_api_key


def test_normalize_score_result_accepts_richer_requirement_payload():
    payload = {
        "fit_score": 78,
        "confidence": "High",
        "match_summary": "Strong overlap with the required enterprise technology leadership scope.",
        "match_reasons": [
            "Led enterprise platform and transformation programs",
            "Matches senior technology leadership scope",
        ],
        "gaps_or_risks": [
            "Industry domain depth is implied, not explicit",
        ],
        "resume_signals_used": [
            "enterprise transformation",
            "platform modernization",
        ],
        "must_have_requirements": [
            "Executive technology leadership",
            "Enterprise transformation experience",
        ],
        "preferred_requirements": [
            "Data leadership",
        ],
        "matched_must_haves": [
            "Executive technology leadership",
        ],
        "missing_must_haves": [
            "Enterprise transformation experience",
        ],
        "matched_preferred": [
            "Data leadership",
        ],
        "missing_preferred": [],
    }

    normalized = normalize_score_result(payload)

    assert normalized["fit_score"] == 78
    assert normalized["fit_label"] == "Moderate"
    assert normalized["recommended_action"] == "Apply with Caution"
    assert normalized["confidence"] == "High"
    assert "enterprise technology leadership" in normalized["match_summary"].lower()


def test_build_default_score_result_stays_safe_for_missing_data():
    result = build_default_score_result(
        status="skipped",
        fit_score=0,
        match_summary="Missing resume/profile text.",
        gaps_or_risks=["Missing resume/profile text"],
    )

    assert result["status"] == "skipped"
    assert result["fit_score"] == 0
    assert result["fit_label"] == "Not Recommended"
    assert result["recommended_action"] == "Skip"
    assert "Missing resume/profile text" in result["gaps_or_risks"]


def test_apply_score_to_job_payload_maps_into_current_job_fields():
    job_payload = {
        "company": "ExampleCo",
        "title": "VP Technology",
        "fit_score": 20,
        "fit_tier": "Weak",
        "ai_priority": "Skip",
        "match_rationale": "Old rationale",
        "risk_flags": "Old risk",
        "application_angle": "Old angle",
    }

    score_result = {
        "fit_score": 86,
        "confidence": "Medium",
        "match_summary": "Clear match on senior technology leadership and transformation scope.",
        "match_reasons": [
            "Direct match on technology leadership",
            "Relevant transformation background",
        ],
        "gaps_or_risks": [
            "Specific industry depth is not explicit",
        ],
        "resume_signals_used": [
            "technology leadership",
            "transformation",
        ],
    }

    updated = apply_score_to_job_payload(job_payload, score_result)

    assert updated["fit_score"] == 86
    assert updated["fit_tier"] == "Strong"
    assert updated["ai_priority"] == "Apply"
    assert updated["match_rationale"] == "Clear match on senior technology leadership and transformation scope."
    assert updated["risk_flags"] == "Specific industry depth is not explicit"
    assert "Direct match on technology leadership" in updated["application_angle"]


def test_effective_openai_key_prefers_saved_key(monkeypatch):
    monkeypatch.setattr(
        "services.openai_key.load_saved_openai_api_key",
        lambda: "saved-key-123",
    )
    monkeypatch.setattr(
        "services.openai_key.load_environment_openai_api_key",
        lambda: "env-key-456",
    )

    assert get_effective_openai_api_key() == "saved-key-123"
