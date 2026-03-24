from ui.components import _split_scrub_corrections


def test_split_scrub_corrections_separates_corrections_from_risks():
    corrections, risks = _split_scrub_corrections(
        "Job description is vague; AI scrub corrected Title to Vice President of Technology; "
        "AI scrub corrected Company to ExampleCo; Location may be stale"
    )

    assert corrections == [
        "AI scrub corrected Title to Vice President of Technology",
        "AI scrub corrected Company to ExampleCo",
    ]
    assert risks == [
        "Job description is vague",
        "Location may be stale",
    ]


def test_split_scrub_corrections_handles_blank_input():
    corrections, risks = _split_scrub_corrections("")

    assert corrections == []
    assert risks == []
