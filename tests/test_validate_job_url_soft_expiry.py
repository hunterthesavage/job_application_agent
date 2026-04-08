from types import SimpleNamespace


def test_parse_page_raises_for_soft_expired_job_page(monkeypatch):
    from src import validate_job_url as validator

    html = """
    <html>
      <head><title>Vantage Data Centers Careers</title></head>
      <body>
        <h1>The page you are looking for doesn't exist.</h1>
        <a href="/search">Search for Jobs</a>
      </body>
    </html>
    """

    monkeypatch.setattr(
        validator.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(
            text=html,
            url="https://vantagedatacenters.wd1.myworkdayjobs.com/en-US/Careers/job/example",
            raise_for_status=lambda: None,
        ),
    )

    try:
        validator.parse_page("https://vantagedatacenters.wd1.myworkdayjobs.com/en-US/Careers/job/example")
    except validator.ExpiredJobPageError as exc:
        assert "doesn't exist" in str(exc).lower()
    else:
        raise AssertionError("Expected soft-expired ATS page to raise ExpiredJobPageError")
