def test_build_search_plan_balanced_does_not_add_broad_tier():
    from services.search_plan import build_search_plan

    plan = build_search_plan(
        settings={
            "target_titles": "VP of IT",
            "preferred_locations": "Dallas",
            "remote_only": "true",
            "search_strategy": "balanced",
        },
        use_ai_expansion=False,
    )

    tier_names = [tier.get("name") for tier in plan.query_tiers]

    assert "ats_broad" not in tier_names
    assert plan.search_strategy == "balanced"


def test_build_search_plan_broad_recall_adds_decomposed_title_tier():
    from services.search_plan import build_search_plan

    plan = build_search_plan(
        settings={
            "target_titles": "Vice President of Information Technology",
            "preferred_locations": "Dallas",
            "remote_only": "true",
            "search_strategy": "broad_recall",
        },
        use_ai_expansion=False,
    )

    broad_tier = next((tier for tier in plan.query_tiers if tier.get("name") == "ats_broad"), None)

    assert broad_tier is not None
    assert broad_tier["queries"]
    assert any('"information technology"' in query for query in broad_tier["queries"])
    assert any('"vice president"' in query for query in broad_tier["queries"])
    assert all('("vice president" OR "vp")' not in query for query in broad_tier["queries"])
    assert plan.search_strategy == "broad_recall"


def test_build_search_plan_notes_include_search_strategy_mode():
    from services.search_plan import build_search_plan

    plan = build_search_plan(
        settings={
            "target_titles": "Business Analyst",
            "preferred_locations": "Dallas",
            "search_strategy": "broad_recall",
        },
        use_ai_expansion=False,
    )

    assert any("Search strategy mode: Broad recall" == note for note in plan.notes)


def test_build_search_plan_expands_shorthand_title_into_search_safe_variant():
    from services.search_plan import build_search_plan
    from services.search_plan import normalize_text

    plan = build_search_plan(
        settings={
            "target_titles": "VP of IT",
            "preferred_locations": "Remote",
            "remote_only": "true",
            "search_strategy": "broad_recall",
        },
        use_ai_expansion=False,
    )

    assert any(
        normalize_text(title) == "vice president of information technology"
        for title in plan.title_variants
    )
    assert not any(normalize_text(title) == "vp of it" for title in plan.title_variants)
    broad_tier = next((tier for tier in plan.query_tiers if tier.get("name") == "ats_broad"), None)
    assert broad_tier is not None
    assert any('"information technology"' in query for query in broad_tier["queries"])
    assert not any(' "it" ' in query for query in broad_tier["queries"])
    assert all('("vice president" OR "vp")' not in query for query in broad_tier["queries"])
