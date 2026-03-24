from services.ai_job_scoring import (
    _apply_preferred_job_level_adjustment,
    apply_score_to_job_payload,
    build_scoring_prompt,
    build_scoring_profile_from_settings,
    build_default_score_result,
    build_scoring_input,
    load_scoring_profile_text,
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


def test_build_scoring_input_includes_preferred_job_levels():
    scoring_input = build_scoring_input(
        {
            "title": "VP Technology",
            "company": "ExampleCo",
        },
        "Resume text",
        preferred_job_levels=["VP", "SVP"],
    )

    assert scoring_input["job"]["detected_job_level"] == "VP"
    assert scoring_input["candidate_preferences"]["preferred_job_levels"] == ["VP", "SVP"]


def test_preferred_job_level_adjustment_penalizes_lower_level_titles():
    result = _apply_preferred_job_level_adjustment(
        {
            "fit_score": 84,
            "match_summary": "Strong technology match.",
            "gaps_or_risks": [],
        },
        {
            "title": "Senior Director of Infrastructure",
        },
        ["VP", "SVP", "C-Suite"],
    )

    assert result["fit_score"] < 84
    assert result["recommended_action"] != "Apply"
    assert any("below selected job levels" in item for item in result["gaps_or_risks"])


def test_build_scoring_profile_from_settings_uses_profile_fields_not_voice():
    profile_text = build_scoring_profile_from_settings(
        {
            "profile_summary": "Executive technology leader.",
            "strengths_to_highlight": "Transformation, enterprise platforms",
            "resume_text": "Led global infrastructure modernization.",
            "cover_letter_voice": "Warm and polished",
        }
    )

    assert "High Priority Candidate Signals:" in profile_text
    assert "Executive Summary:" in profile_text
    assert "Strengths to Highlight:" in profile_text
    assert "Supporting Candidate Evidence:" in profile_text
    assert "Resume Text:" in profile_text
    assert "Warm and polished" not in profile_text


def test_load_scoring_profile_text_prefers_saved_settings(monkeypatch):
    monkeypatch.setattr(
        "services.ai_job_scoring.load_settings",
        lambda: {
            "profile_summary": "Saved summary",
            "strengths_to_highlight": "Saved strengths",
            "resume_text": "Saved resume",
        },
    )
    monkeypatch.setattr(
        "services.ai_job_scoring.load_resume_profile_text",
        lambda explicit_path=None, candidate_paths=None: ("File profile text", "profile_context.txt"),
    )

    profile_text, source = load_scoring_profile_text()

    assert "Saved summary" in profile_text
    assert source == "Settings -> Profile Context"


def test_load_scoring_profile_text_falls_back_to_file(monkeypatch):
    monkeypatch.setattr(
        "services.ai_job_scoring.load_settings",
        lambda: {
            "profile_summary": "",
            "strengths_to_highlight": "",
            "resume_text": "",
        },
    )
    monkeypatch.setattr(
        "services.ai_job_scoring.load_resume_profile_text",
        lambda explicit_path=None, candidate_paths=None: ("File profile text", "profile_context.txt"),
    )

    profile_text, source = load_scoring_profile_text()

    assert profile_text == "File profile text"
    assert source == "profile_context.txt"


def test_build_scoring_prompt_includes_profile_weighting_instruction():
    prompt = build_scoring_prompt(
        {
            "title": "VP Technology",
            "company": "ExampleCo",
            "description_text": "Lead enterprise technology strategy and transformation.",
        },
        (
            "High Priority Candidate Signals:\n"
            "Executive Summary:\nExecutive technology leader\n\n"
            "Strengths to Highlight:\nTransformation\n\n"
            "Supporting Candidate Evidence:\n"
            "Resume Text:\nDetailed background"
        ),
        preferred_job_levels=["VP"],
    )

    assert "Weight candidate evidence in this order" in prompt
    assert "1. Executive Summary" in prompt
    assert "2. Strengths to Highlight" in prompt
    assert "3. Resume Text" in prompt
