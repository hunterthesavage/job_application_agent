from ui.components import _format_compensation_display, _split_scrub_corrections


def test_split_scrub_corrections_separates_corrections_from_risks():
    corrections, risks = _split_scrub_corrections(
        "Job description is vague; AI scrub updated Title: VP Tech -> Vice President of Technology; "
        "Live page refresh updated Company: Xapo61 -> Xapo Bank; Location may be stale"
    )

    assert corrections == [
        "AI scrub updated Title: VP Tech -> Vice President of Technology",
        "Live page refresh updated Company: Xapo61 -> Xapo Bank",
    ]
    assert risks == [
        "Job description is vague",
        "Location may be stale",
    ]


def test_split_scrub_corrections_handles_blank_input():
    corrections, risks = _split_scrub_corrections("")

    assert corrections == []
    assert risks == []


def test_format_compensation_display_normalizes_yearly_range():
    assert _format_compensation_display("225-325k") == "$225,000-$325,000"


def test_format_compensation_display_normalizes_hourly_range():
    assert _format_compensation_display("$55 to $65 per hour") == "$55-$65/hr"
