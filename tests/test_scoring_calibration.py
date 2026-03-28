from services.scoring_calibration import (
    ai_label_from_score_result,
    evaluate_calibration_cases,
    label_distance,
    normalize_expected_label,
    qualifier_label_from_match,
    render_calibration_report,
)


def test_normalize_expected_label_accepts_common_aliases():
    assert normalize_expected_label("Apply") == "yes"
    assert normalize_expected_label("review") == "maybe"
    assert normalize_expected_label("Skip") == "no"


def test_qualifier_label_from_match_maps_acceptance_and_score():
    assert qualifier_label_from_match({"should_accept": False, "qualification": {"score": 90}}) == "no"
    assert qualifier_label_from_match({"should_accept": True, "qualification": {"score": 72}}) == "maybe"
    assert qualifier_label_from_match({"should_accept": True, "qualification": {"score": 80}}) == "yes"


def test_ai_label_from_score_result_uses_three_bucket_mapping():
    assert ai_label_from_score_result({"fit_score": 83}) == "yes"
    assert ai_label_from_score_result({"fit_score": 68}) == "maybe"
    assert ai_label_from_score_result({"fit_score": 18}) == "no"


def test_label_distance_uses_adjacent_bucket_scoring():
    assert label_distance("yes", "yes") == 0
    assert label_distance("yes", "maybe") == 1
    assert label_distance("yes", "no") == 2


def test_evaluate_calibration_cases_summarizes_qualifier_and_ai(monkeypatch):
    import services.scoring_calibration as calibration

    monkeypatch.setattr(
        calibration,
        "score_job_match",
        lambda job, settings: {
            "score": 82 if "Information Technology" in job.title else 15,
            "should_accept": "Information Technology" in job.title,
            "reason_text": "ok" if "Information Technology" in job.title else "qualifier reject: wrong function",
            "qualification": {
                "score": 82 if "Information Technology" in job.title else 15,
                "reject_reason": "" if "Information Technology" in job.title else "wrong function",
            },
        },
    )
    monkeypatch.setattr(
        calibration,
        "score_accepted_job",
        lambda payload, resume_profile_text, model=None: {
            "status": "scored",
            "fit_score": 84 if "Information Technology" in payload["title"] else 20,
            "match_summary": "stub",
        },
    )

    report = evaluate_calibration_cases(
        [
            {
                "id": "good",
                "expected_label": "yes",
                "title": "Vice President, Information Technology",
                "company": "Example",
                "location": "United States Remote",
                "description_text": "Executive technology role",
                "target_titles": "VP of IT",
                "preferred_locations": "Remote",
                "remote_only": "true",
            },
            {
                "id": "bad",
                "expected_label": "no",
                "title": "Vice President, Sales",
                "company": "Example",
                "location": "United States Remote",
                "description_text": "Sales role",
                "target_titles": "VP of IT",
                "preferred_locations": "Remote",
                "remote_only": "true",
            },
        ],
        resume_profile_text="Executive technology leader",
        use_ai_scoring=True,
    )

    assert report["total_cases"] == 2
    assert report["qualifier_summary"]["exact_matches"] == 2
    assert report["ai_summary"]["exact_matches"] == 2
    assert report["ai_summary"]["skipped_or_unscored"] == 0


def test_render_calibration_report_includes_far_misses_section():
    report = {
        "generated_at": "2026-03-28T12:00:00Z",
        "total_cases": 1,
        "use_ai_scoring": False,
        "qualifier_summary": {"exact_matches": 0, "adjacent_matches": 0, "far_misses": 1},
        "ai_summary": {"exact_matches": 0, "adjacent_matches": 0, "far_misses": 0, "skipped_or_unscored": 1},
        "results": [
            {
                "id": "bad_case",
                "expected_label": "yes",
                "qualifier_label": "no",
                "qualifier_score": 12,
                "qualifier_distance": 2,
                "ai_label": "",
                "ai_distance": None,
                "ai_status": "skipped",
                "title": "VP Sales",
            }
        ],
    }

    output = render_calibration_report(report)

    assert "# Scoring Calibration Report" in output
    assert "## Far Misses" in output
    assert "`bad_case` expected `yes`, qualifier `no`" in output
