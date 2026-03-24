from services.job_levels import (
    get_level_preference_penalty,
    infer_job_level,
    parse_preferred_job_levels,
    serialize_preferred_job_levels,
)


def test_parse_and_serialize_preferred_job_levels_round_trip():
    selected = parse_preferred_job_levels("VP, SVP, C-Suite")

    assert selected == ["VP", "SVP", "C-Suite"]
    assert serialize_preferred_job_levels(selected) == "VP, SVP, C-Suite"


def test_infer_job_level_detects_executive_and_manager_titles():
    assert infer_job_level("Vice President, Enterprise Technology") == "VP"
    assert infer_job_level("Senior Director of Infrastructure") == "Sr. Director"
    assert infer_job_level("Engineering Manager") == "Manager"


def test_level_preference_penalty_hits_lower_level_titles_hard():
    penalty, detected_level, reason = get_level_preference_penalty(
        "Senior Director of Technology",
        ["VP", "SVP", "C-Suite"],
    )

    assert penalty > 0
    assert detected_level == "Sr. Director"
    assert "below selected job levels" in reason
