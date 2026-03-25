import json


def test_generate_profile_context_from_resume_requires_resume_text(monkeypatch):
    import services.profile_context_templates as templates

    monkeypatch.setattr(templates, "get_effective_openai_api_key", lambda: "sk-test")

    result = templates.generate_profile_context_from_resume("")

    assert result["ok"] is False
    assert "Paste resume text first" in result["error"]


def test_generate_profile_context_from_resume_requires_api_key(monkeypatch):
    import services.profile_context_templates as templates

    monkeypatch.setattr(templates, "get_effective_openai_api_key", lambda: "")

    result = templates.generate_profile_context_from_resume("Led enterprise transformation.")

    assert result["ok"] is False
    assert "No OpenAI API key is available" in result["error"]


def test_generate_profile_context_from_resume_parses_openai_json(monkeypatch):
    import services.profile_context_templates as templates

    monkeypatch.setattr(templates, "get_effective_openai_api_key", lambda: "sk-test")

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "profile_summary": "Executive technology leader.",
                                    "strengths_to_highlight": "AI transformation\nPlatform modernization",
                                    "cover_letter_voice": "Direct and executive.",
                                }
                            )
                        }
                    }
                ]
            }
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(templates.urllib.request, "urlopen", lambda request, timeout=60: _Response())

    result = templates.generate_profile_context_from_resume("Led enterprise transformation.")

    assert result["ok"] is True
    assert result["profile_summary"] == "Executive technology leader."
    assert "AI transformation" in result["strengths_to_highlight"]
    assert result["cover_letter_voice"] == "Direct and executive."
