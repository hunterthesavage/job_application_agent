from services.ai_job_scrub import (
    AIJobScrubService,
    apply_scrub_to_job_payload,
    build_default_scrub_result,
    normalize_scrub_result,
)


def test_normalize_scrub_result_accepts_expected_fields():
    payload = {
        "scrub_status": "reject",
        "scrub_summary": "Role appears to be finance-led rather than technology-led.",
        "scrub_flags": [
            "Primary function appears misaligned with executive technology lane",
            "Job description evidence is too thin to trust the score",
        ],
        "scrub_confidence": "high",
        "corrected_title": "Vice President, Technology",
        "corrected_company": "Example Holdings",
        "correction_confidence": "high",
        "correction_notes": ["Page title clearly uses the vice president title variant"],
    }

    normalized = normalize_scrub_result(payload)

    assert normalized["scrub_status"] == "reject"
    assert normalized["scrub_confidence"] == "High"
    assert normalized["corrected_title"] == "Vice President, Technology"
    assert normalized["corrected_company"] == "Example Holdings"
    assert normalized["correction_confidence"] == "High"
    assert "finance-led" in normalized["scrub_summary"]
    assert len(normalized["scrub_flags"]) == 2


def test_build_default_scrub_result_stays_safe():
    result = build_default_scrub_result(
        scrub_status="review",
        scrub_summary="Resume/profile text was missing.",
        scrub_flags=["Missing resume/profile text"],
        scrub_confidence="Low",
        status="skipped",
    )

    assert result["scrub_status"] == "review"
    assert result["status"] == "skipped"
    assert result["scrub_flags"] == ["Missing resume/profile text"]


def test_apply_scrub_to_job_payload_merges_risks_and_downgrades_apply():
    job_payload = {
        "ai_priority": "Apply",
        "risk_flags": "Existing concern",
        "description_text": "Lead enterprise technology operations.",
    }
    scrub_result = {
        "scrub_status": "review",
        "scrub_flags": [
            "Job description is vague",
            "Role scope is somewhat ambiguous",
        ],
    }

    updated = apply_scrub_to_job_payload(job_payload, scrub_result)

    assert updated["ai_priority"] == "Hold"
    assert updated["risk_flags"] == (
        "Existing concern; Job description is vague; Role scope is somewhat ambiguous"
    )


def test_apply_scrub_to_job_payload_reject_forces_skip():
    job_payload = {
        "ai_priority": "Apply",
        "risk_flags": "",
    }
    scrub_result = {
        "scrub_status": "reject",
        "scrub_flags": ["Clear function mismatch"],
    }

    updated = apply_scrub_to_job_payload(job_payload, scrub_result)

    assert updated["ai_priority"] == "Skip"
    assert updated["risk_flags"] == "Clear function mismatch"


def test_apply_scrub_to_job_payload_applies_high_confidence_field_corrections():
    job_payload = {
        "title": "VP Tech",
        "company": "ExampleCo LLC",
        "compensation_raw": "",
        "duplicate_key": "exampleco|vptech|dallas",
        "normalized_title": "vp tech",
        "ai_priority": "Apply",
        "risk_flags": "",
        "description_text": "Vice President of Technology at ExampleCo. Compensation: $220,000 - $260,000.",
    }
    scrub_result = {
        "scrub_status": "clean",
        "scrub_confidence": "High",
        "corrected_title": "Vice President of Technology",
        "corrected_company": "ExampleCo",
        "corrected_compensation_raw": "$220,000 - $260,000",
        "correction_confidence": "High",
        "correction_notes": ["Page header and compensation section were explicit."],
    }

    updated = apply_scrub_to_job_payload(job_payload, scrub_result)

    assert updated["title"] == "Vice President of Technology"
    assert updated["company"] == "ExampleCo"
    assert updated["compensation_raw"] == "$220,000 - $260,000"
    assert updated["duplicate_key"] == ""
    assert updated["normalized_title"] == ""
    assert "AI scrub corrected Title to Vice President of Technology" in updated["risk_flags"]
    assert "AI scrub corrected Company to ExampleCo" in updated["risk_flags"]


def test_apply_scrub_to_job_payload_ignores_corrections_without_high_confidence():
    job_payload = {
        "title": "VP Tech",
        "company": "ExampleCo LLC",
        "compensation_raw": "",
        "duplicate_key": "exampleco|vptech|dallas",
        "normalized_title": "vp tech",
        "ai_priority": "Apply",
        "risk_flags": "",
        "description_text": "Lead technology organization.",
    }
    scrub_result = {
        "scrub_status": "clean",
        "corrected_title": "Vice President of Technology",
        "correction_confidence": "Medium",
    }

    updated = apply_scrub_to_job_payload(job_payload, scrub_result)

    assert updated["title"] == "VP Tech"
    assert updated["company"] == "ExampleCo LLC"
    assert updated["duplicate_key"] == "exampleco|vptech|dallas"


def test_scrub_service_skips_when_resume_profile_missing():
    service = AIJobScrubService()
    result = service.scrub_job(
        {
            "title": "VP Technology",
            "description_text": "Lead enterprise technology transformation.",
        },
        "",
    )

    assert result["status"] == "skipped"
    assert result["scrub_status"] == "review"
    assert "Missing resume/profile text" in result["scrub_flags"]
