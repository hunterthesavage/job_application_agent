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
