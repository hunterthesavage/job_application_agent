from types import SimpleNamespace


def test_discover_google_style_urls_logs_rejected_search_result_diagnostics(monkeypatch):
    import src.discover_job_urls as discover

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query, max_results=10):
            return [
                {
                    "href": "https://example.com/search?q=vp+of+it",
                    "title": "Search Result",
                }
            ]

    monkeypatch.setattr(discover, "DDGS", FakeDDGS)
    monkeypatch.setattr(
        discover,
        "build_structured_search_plan",
        lambda settings, use_ai_expansion=True: SimpleNamespace(
            notes=[],
            query_tiers=[
                {
                    "name": "ats_broad",
                    "label": "ATS broad recall",
                    "queries": ['("vice president" OR "vp") "it" "remote"'],
                }
            ],
        ),
    )

    log_lines: list[str] = []
    discovered = discover.discover_google_style_urls({}, log_lines=log_lines, use_ai_expansion=False)

    assert discovered == []
    assert any(
        "Rejected search result [ats_broad]: no_preferred_or_detail_candidate" in line
        for line in log_lines
    )
    assert any("raw=https://example.com/search?q=vp+of+it" in line for line in log_lines)
    assert any("Tier rejected search results [ats_broad]:" in line for line in log_lines)


def test_discover_google_style_urls_treats_no_results_as_empty_query(monkeypatch):
    import src.discover_job_urls as discover

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query, max_results=10):
            if '"VP of IT"' in query:
                raise Exception("No results found.")
            return [
                {
                    "href": "https://jobs.lever.co/example/12345",
                    "title": "Example VP IT role",
                }
            ]

    monkeypatch.setattr(discover, "DDGS", FakeDDGS)
    monkeypatch.setattr(
        discover,
        "build_structured_search_plan",
        lambda settings, use_ai_expansion=True: SimpleNamespace(
            notes=[],
            query_tiers=[
                {
                    "name": "ats_strict",
                    "label": "ATS strict",
                    "queries": ['"VP of IT" "remote"'],
                },
                {
                    "name": "career_web",
                    "label": "Career web",
                    "queries": ['"Vice President of Information Technology" "remote"'],
                },
            ],
        ),
    )

    log_lines: list[str] = []
    discovered = discover.discover_google_style_urls({}, log_lines=log_lines, use_ai_expansion=False)

    assert discovered == ["https://jobs.lever.co/example/12345"]
    assert any("Search results returned [ats_strict]: 0" == line for line in log_lines)
    assert any("Search results returned [career_web]: 1" == line for line in log_lines)
    assert not any("Web discovery unavailable" in line for line in log_lines)


def test_discover_google_style_urls_retries_transient_search_failure(monkeypatch):
    import src.discover_job_urls as discover

    calls = {"count": 0}

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query, max_results=10):
            calls["count"] += 1
            if calls["count"] == 1:
                raise Exception("DecodeError: Body collection error")
            return [
                {
                    "href": "https://jobs.lever.co/example/12345",
                    "title": "Example VP IT role",
                }
            ]

    monkeypatch.setattr(discover, "DDGS", FakeDDGS)
    monkeypatch.setattr(
        discover,
        "build_structured_search_plan",
        lambda settings, use_ai_expansion=True: SimpleNamespace(
            notes=[],
            query_tiers=[
                {
                    "name": "ats_strict",
                    "label": "ATS strict",
                    "queries": ['"VP of IT" "remote"'],
                },
            ],
        ),
    )

    log_lines: list[str] = []
    discovered = discover.discover_google_style_urls({}, log_lines=log_lines, use_ai_expansion=False)

    assert discovered == ["https://jobs.lever.co/example/12345"]
    assert calls["count"] == 2
    assert any("Search retry [ats_strict] after transient failure" in line for line in log_lines)
    assert any("Search retry [ats_strict] succeeded on attempt 2." in line for line in log_lines)
