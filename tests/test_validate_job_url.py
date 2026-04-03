from src.validate_job_url import extract_workday_fallback_from_url


def test_extract_workday_fallback_from_url_reads_title_from_slug():
    title, location = extract_workday_fallback_from_url(
        "https://thekey.wd1.myworkdayjobs.com/en-US/thekey/job/Vice-President-Information-Technology_JR103768"
    )

    assert title == "Vice President Information Technology"
    assert location == ""


def test_extract_workday_fallback_from_url_reads_location_segment_when_present():
    title, location = extract_workday_fallback_from_url(
        "https://gdt.wd1.myworkdayjobs.com/GDT_Careers/job/Dallas-TX/Technology-Contracts-Counsel_R-101840"
    )

    assert title == "Technology Contracts Counsel"
    assert location == "Dallas, TX"
