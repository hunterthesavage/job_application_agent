# AI Analysis Changelog

This file is the running changelog for AI Analysis work only.

Rules:
- Update this file every time an AI Analysis change is made.
- Keep entries short and concrete.
- Focus on scoring, qualification, ranking, AI prompts, rationale generation, profile interpretation, and related tests.
- Do not mix in Discovery Tech, UI/UX, or general repo housekeeping.

Entry format:

## YYYY-MM-DD

### Short change title
- Summary: what changed.
- Why: the bottleneck, bug, or reason for the change.
- Validation: tests run, live checks, or observed outcome.
- Files: relevant files only.

---

## 2026-03-27

### Resume-generation API key normalization
- Summary: Normalized pasted OpenAI API keys by stripping wrapping straight/smart quotes before saving or loading, which prevents fresh-install resume generation from failing on Unicode quote characters in the Authorization header.
- Why: Fresh UI testing exposed `Generate from Resume` failing with a `latin-1` encoding error when the saved key contained smart quotes copied from formatted text.
- Validation: Ran `.venv/bin/pytest tests/test_openai_key.py tests/test_profile_context_templates.py -q` and directly verified that saving `“sk-test123”` now resolves to `sk-test123`.
- Files: `services/openai_key.py`, `tests/test_openai_key.py`

### Initialized AI Analysis changelog
- Summary: created the dedicated running changelog for AI Analysis work.
- Why: to keep AI Analysis changes easy to track separately from Discovery Tech and UI/UX work.
- Validation: file created in repo docs.
- Files: `docs/ai-analysis-changelog.md`
