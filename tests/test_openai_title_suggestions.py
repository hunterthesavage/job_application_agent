class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.text = __import__("json").dumps(payload)

    def raise_for_status(self) -> None:
        return None


def test_suggest_titles_with_openai_honors_max_titles(monkeypatch):
    import services.openai_title_suggestions as suggestions

    monkeypatch.setattr(suggestions, "get_effective_openai_api_key", lambda: "test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": __import__("json").dumps(
                                {
                                    "titles": [
                                        "Title 1",
                                        "Title 2",
                                        "Title 3",
                                        "Title 4",
                                        "Title 5",
                                        "Title 6",
                                        "Title 7",
                                        "Title 8",
                                        "Title 9",
                                        "Title 10",
                                        "Title 11",
                                    ],
                                    "notes": "test",
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(suggestions.requests, "post", fake_post)

    result = suggestions.suggest_titles_with_openai(
        current_titles="VP of IT",
        max_titles=10,
    )

    assert result["ok"] is True
    assert len(result["titles"]) == 10
    assert result["titles"][-1] == "Title 10"


def test_suggest_run_input_refinements_returns_titles_and_locations(monkeypatch):
    import services.openai_title_suggestions as suggestions

    monkeypatch.setattr(suggestions, "get_effective_openai_api_key", lambda: "test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": __import__("json").dumps(
                                {
                                    "titles": [
                                        "VP Information Technology",
                                        "Vice President, IT",
                                    ],
                                    "locations": [
                                        "Dallas, TX",
                                        "Fort Worth, TX",
                                    ],
                                    "notes": "Tightened titles and normalized the DFW locations.",
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(suggestions.requests, "post", fake_post)

    result = suggestions.suggest_run_input_refinements_with_openai(
        current_titles="VP of IT",
        preferred_locations="Dallas, DFW",
        include_remote=True,
    )

    assert result["ok"] is True
    assert result["titles"] == ["VP Information Technology", "Vice President, IT"]
    assert result["locations"] == ["Dallas, TX", "Fort Worth, TX"]


def test_suggest_title_groups_with_openai_returns_variants_per_main_title(monkeypatch):
    import services.openai_title_suggestions as suggestions

    monkeypatch.setattr(suggestions, "get_effective_openai_api_key", lambda: "test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": __import__("json").dumps(
                                {
                                    "title_groups": [
                                        {
                                            "main_title": "VP of IT",
                                            "variants": [
                                                "Vice President of IT",
                                                "VP Information Technology",
                                                "VP of IT",
                                            ],
                                        },
                                        {
                                            "main_title": "IT Manager",
                                            "variants": [
                                                "IT Mgr",
                                                "Information Technology Manager",
                                            ],
                                        },
                                    ],
                                    "notes": "Kept each title close to the original ATS wording.",
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(suggestions.requests, "post", fake_post)

    result = suggestions.suggest_title_groups_with_openai(
        main_titles=["VP of IT", "IT Manager"],
        max_variants_per_title=5,
    )

    assert result["ok"] is True
    assert result["title_groups"] == [
        {
            "main_title": "VP of IT",
            "variants": ["Vice President of IT", "VP Information Technology"],
        },
        {
            "main_title": "IT Manager",
            "variants": ["IT Mgr", "Information Technology Manager"],
        },
    ]


def test_suggest_title_groups_with_openai_filters_awkward_variants(monkeypatch):
    import services.openai_title_suggestions as suggestions

    monkeypatch.setattr(suggestions, "get_effective_openai_api_key", lambda: "test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": __import__("json").dumps(
                                {
                                    "title_groups": [
                                        {
                                            "main_title": "IT Manager",
                                            "variants": [
                                                "Manager Information Technology",
                                                "Mgr IT",
                                                "Information Technology Manager",
                                                "IT Mgr",
                                            ],
                                        },
                                        {
                                            "main_title": "VP of IT",
                                            "variants": [
                                                "Vice Pres of IT",
                                                "Vice President of IT",
                                            ],
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(suggestions.requests, "post", fake_post)

    result = suggestions.suggest_title_groups_with_openai(
        main_titles=["IT Manager", "VP of IT"],
        max_variants_per_title=5,
    )

    assert result["ok"] is True
    assert result["title_groups"] == [
        {
            "main_title": "IT Manager",
            "variants": ["Information Technology Manager", "IT Mgr"],
        },
        {
            "main_title": "VP of IT",
            "variants": ["Vice President of IT"],
        },
    ]
