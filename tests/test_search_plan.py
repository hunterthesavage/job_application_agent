import json


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
    assert any(normalize_text(title) == "vp of it" for title in plan.title_variants)
    broad_tier = next((tier for tier in plan.query_tiers if tier.get("name") == "ats_broad"), None)
    strict_tier = next((tier for tier in plan.query_tiers if tier.get("name") == "ats_strict"), None)
    assert broad_tier is not None
    assert strict_tier is not None
    assert any('"information technology"' in query for query in broad_tier["queries"])
    assert not any(' "it" ' in query for query in broad_tier["queries"])
    assert all('("vice president" OR "vp")' not in query for query in broad_tier["queries"])
    assert any('("VP of IT" OR "vice president of information technology") "remote"' in query for query in strict_tier["queries"])


def test_parse_title_entries_preserves_legacy_vp_it_phrase():
    from services.search_plan import parse_title_entries

    parsed = parse_title_entries(
        "Vice President of IT, VP of Information Technology, Vice President, IT Operations, Technology"
    )

    assert "Vice President, IT Operations" in parsed
    assert "Vice President, Technology" in parsed
    assert "Vice President" not in parsed
    assert "Technology" not in parsed


def test_build_search_plan_respects_include_remote_false_with_locations():
    from services.search_plan import build_search_plan

    plan = build_search_plan(
        settings={
            "target_titles": "Vice President of Information Technology",
            "preferred_locations": "Dallas, TX\nFort Worth, TX",
            "include_remote": "false",
            "remote_only": "false",
            "search_strategy": "broad_recall",
        },
        use_ai_expansion=False,
    )

    assert plan.include_remote is False
    assert all("remote" not in query.lower() for query in plan.queries)
    assert any("Dallas, TX" in note or "Fort Worth, TX" in note for note in plan.notes)


def test_build_search_plan_keeps_common_vp_bundle_queries_separate():
    from services.search_plan import build_search_plan

    plan = build_search_plan(
        settings={
            "target_titles": (
                "VP of Technology\n"
                "VP of AI\n"
                "VP of ITSM\n"
                "VP of Service Delivery\n"
                "VP of Technology\n"
                "VP of Artificial Intelligence\n"
                "VP of IT Service Management\n"
                "VP of Service Delivery\n"
                "VP of Engineering\n"
                "VP of Infrastructure"
            ),
            "preferred_locations": "Dallas, TX\nPlano, TX\nFrisco, TX\nRemote",
            "include_remote": "true",
            "search_strategy": "broad_recall",
        },
        use_ai_expansion=True,
    )

    grouped_tier = next((tier for tier in plan.query_tiers if tier.get("name") == "ats_grouped"), None)

    assert plan.base_titles == [
        "VP of Technology",
        "VP of AI",
        "VP of ITSM",
        "VP of Service Delivery",
        "VP of Artificial Intelligence",
        "VP of IT Service Management",
        "VP of Engineering",
        "VP of Infrastructure",
    ]
    assert plan.title_variants == [
        "VP of Technology",
        "vice president of technology",
        "VP of AI",
        "vice president of artificial intelligence",
        "VP of ITSM",
        "vice president of itsm",
        "VP of Service Delivery",
        "vice president of service delivery",
        "VP of Artificial Intelligence",
        "VP of IT Service Management",
        "vice president of information technology service management",
    ]
    assert grouped_tier is not None
    assert len(grouped_tier["queries"]) == 3
    assert all('VP of Technology vice president of technology VP of AI' not in query for query in grouped_tier["queries"])
    assert all(query.count('"vice president') >= 5 for query in grouped_tier["queries"])
    assert any('"VP of Technology"' in query for query in grouped_tier["queries"])


def test_build_search_plan_uses_title_groups_as_compact_alias_families():
    from services.search_plan import build_search_plan

    plan = build_search_plan(
        settings={
            "target_titles": "manager of information technology\ninformation technology manager\nvice president of information technology",
            "target_title_groups": json.dumps(
                [
                    {
                        "main_title": "manager of it",
                        "variants": [
                            {"title": "IT Manager", "selected": True, "source": "ai"},
                            {"title": "Information Technology Manager", "selected": True, "source": "ai"},
                            {"title": "Mgr Information Technology", "selected": True, "source": "ai"},
                        ],
                    },
                    {
                        "main_title": "vp of it",
                        "variants": [
                            {"title": "Vice President of IT", "selected": True, "source": "ai"},
                            {"title": "VP Information Technology", "selected": True, "source": "ai"},
                            {"title": "Vice President of Information Technology", "selected": True, "source": "ai"},
                        ],
                    },
                ]
            ),
            "preferred_locations": "Remote",
            "remote_only": "true",
            "search_strategy": "broad_recall",
        },
        use_ai_expansion=False,
    )

    assert plan.base_titles == ["manager of it", "vp of it"]
    assert len(plan.title_families) == 2

    manager_family = plan.title_families[0]
    vp_family = plan.title_families[1]

    assert manager_family["aliases"] == [
        "manager of it",
        "manager of information technology",
        "IT Manager",
    ]
    assert vp_family["aliases"] == [
        "vp of it",
        "vice president of information technology",
        "Vice President of IT",
    ]

    strict_tier = next((tier for tier in plan.query_tiers if tier.get("name") == "ats_strict"), None)
    assert strict_tier is not None
    assert len(strict_tier["queries"]) == 2
    assert any('("manager of it" OR "manager of information technology" OR "IT Manager") "remote"' in query for query in strict_tier["queries"])
    assert any('("vp of it" OR "vice president of information technology" OR "Vice President of IT") "remote"' in query for query in strict_tier["queries"])
