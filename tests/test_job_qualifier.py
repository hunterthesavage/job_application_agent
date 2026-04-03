from services.job_qualifier import qualify_job


def test_qualify_job_accepts_search_safe_title_variant_for_vp_it():
    result = qualify_job(
        job_title="Vice President, Information Technology",
        company="ExampleCo",
        location="United States Remote",
        job_text="Owns enterprise systems, infrastructure, and technology strategy.",
        settings={
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        },
    )

    assert result.should_accept is True
    assert result.reject_reason == ""
    assert result.score >= 50


def test_qualify_job_still_rejects_wrong_executive_function():
    result = qualify_job(
        job_title="Vice President, Sales",
        company="RevenueCo",
        location="United States Remote",
        job_text="Leads revenue, territories, and sales operations.",
        settings={
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
        },
    )

    assert result.should_accept is False
    assert result.reject_reason == "wrong function"


def test_qualify_job_uses_structured_location_matching_for_city_without_state_abbreviation():
    result = qualify_job(
        job_title="Vice President of Technology",
        company="ExampleCo",
        location="Innovation Campus (Dallas), United States of America",
        job_text="Leads enterprise technology strategy and operations.",
        settings={
            "target_titles": "Vice President of Technology",
            "preferred_locations": "Dallas, TX",
            "include_remote": "true",
            "remote_only": "false",
        },
    )

    assert result.should_accept is True
    assert result.reject_reason == ""
    assert "matched" in result.rationale.lower()
