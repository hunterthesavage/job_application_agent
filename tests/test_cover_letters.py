def test_infer_candidate_name_from_resume_text_reads_top_name_line():
    from services.cover_letters import infer_candidate_name_from_resume_text

    resume_text = """Jane Q. Executive
Chicago, IL
jane@example.com
Executive technology leader
"""

    assert infer_candidate_name_from_resume_text(resume_text) == "Jane Q. Executive"


def test_infer_candidate_name_from_resume_text_does_not_invent_name():
    from services.cover_letters import infer_candidate_name_from_resume_text

    resume_text = """Executive technology leader
15 years leading transformation
ServiceNow, AI, cloud modernization
"""

    assert infer_candidate_name_from_resume_text(resume_text) == ""


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
