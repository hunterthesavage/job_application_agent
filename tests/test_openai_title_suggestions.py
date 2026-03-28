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
