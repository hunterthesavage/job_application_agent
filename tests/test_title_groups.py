def test_load_title_groups_from_settings_falls_back_to_legacy_titles():
    from services.title_groups import build_effective_title_list, load_title_groups_from_settings

    groups = load_title_groups_from_settings(
        {
            "target_titles": "VP of IT\nDirector of Infrastructure",
            "target_title_groups": "",
        }
    )

    assert [group["main_title"] for group in groups] == ["VP of IT", "Director of Infrastructure"]
    assert build_effective_title_list(groups) == ["VP of IT", "Director of Infrastructure"]


def test_merge_ai_variants_preserves_existing_selection_state():
    from services.title_groups import merge_ai_variants_into_groups

    merged = merge_ai_variants_into_groups(
        [
            {
                "id": "group-1",
                "main_title": "VP of IT",
                "variants": [
                    {"title": "Vice President of IT", "selected": False, "source": "ai"},
                    {"title": "VP Information Technology", "selected": True, "source": "ai"},
                ],
            }
        ],
        {
            "VP of IT": [
                "Vice President of IT",
                "VP Information Technology",
                "Vice President, Information Technology",
            ]
        },
    )

    assert merged == [
        {
            "id": "group-1",
            "main_title": "VP of IT",
            "variants": [
                {"title": "Vice President of IT", "selected": False, "source": "ai"},
                {"title": "VP Information Technology", "selected": True, "source": "ai"},
                {"title": "Vice President, Information Technology", "selected": True, "source": "ai"},
            ],
        }
    ]


def test_build_effective_titles_text_uses_selected_variants_only():
    from services.title_groups import build_effective_titles_text

    text = build_effective_titles_text(
        [
            {
                "main_title": "IT Manager",
                "variants": [
                    {"title": "IT Mgr", "selected": True, "source": "ai"},
                    {"title": "Information Technology Manager", "selected": False, "source": "ai"},
                ],
            }
        ]
    )

    assert text == "IT Manager\nIT Mgr"


def test_build_search_titles_text_canonicalizes_grouped_variants_for_backend_search():
    from services.title_groups import build_search_titles_text

    text = build_search_titles_text(
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
                ],
            },
        ]
    )

    assert text == "\n".join(
        [
            "manager of information technology",
            "information technology manager",
            "vice president of information technology",
        ]
    )
