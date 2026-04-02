def test_build_output_filename_fallback_is_generic():
    from services.cover_letters import build_output_filename

    filename = build_output_filename(
        {
            "cover_letter_filename_pattern": "",
        },
        {
            "company": "",
            "title": "",
        },
    )

    assert "Hunter" not in filename
    assert "Samuels" not in filename
    assert filename.endswith(".txt")


def test_build_cover_letter_prompt_prioritizes_voice_for_succinct_setting():
    from services.cover_letters import build_cover_letter_prompt

    prompt = build_cover_letter_prompt(
        "Executive Summary:\nProgram leader",
        {
            "company": "Figma",
            "title": "Design Program Manager, AI",
            "location": "Remote",
            "role_family": "Program Management",
            "match_rationale": "Strong operating cadence and cross-functional leadership.",
            "application_angle": "Help operationalize AI programs.",
            "cover_letter_starter": "",
            "compensation_raw": "",
        },
        "Very succinct and to the point, no fluff.",
    )

    assert "The Cover Letter Voice is the highest-priority writing instruction" in prompt
    assert "Very succinct and to the point, no fluff." in prompt
    assert "2 to 3 short paragraphs" in prompt
    assert "120 to 180 words" in prompt
    assert "4 to 6 paragraphs" not in prompt
    assert "executive-level" not in prompt


def test_build_cover_letter_prompt_uses_reasonable_default_best_practices():
    from services.cover_letters import build_cover_letter_prompt

    prompt = build_cover_letter_prompt(
        "Executive Summary:\nProgram leader",
        {
            "company": "Figma",
            "title": "Design Program Manager, AI",
            "location": "Remote",
            "role_family": "Program Management",
            "match_rationale": "Strong operating cadence and cross-functional leadership.",
            "application_angle": "Help operationalize AI programs.",
            "cover_letter_starter": "",
            "compensation_raw": "",
        },
        "",
    )

    assert "Clear, specific, and professional." in prompt
    assert "3 to 4 reasonably short paragraphs" in prompt
    assert "180 to 300 words" in prompt
