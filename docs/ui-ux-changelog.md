# UI/UX Changelog

This file is the running changelog for UI/UX work only.

Rules:
- Update this file every time a UI/UX change is made.
- Keep entries short and concrete.
- Focus on interface behavior, layout, styling, interaction changes, usability improvements, and related tests.
- Do not mix in Discovery Tech, AI Analysis, or general repo housekeeping.

Entry format:

## YYYY-MM-DD

### Short change title
- Summary: what changed.
- Why: the bottleneck, bug, or reason for the change.
- Validation: tests run, visual checks, or observed outcome.
- Files: relevant files only.

---

## 2026-03-27

### Tightened Pipeline run inputs and last-run duration display
- Summary: added Pipeline search-strategy controls, AI title-suggestion selection after saving run inputs, reliable local copy behavior for saved results, and a last-run Duration display that prefers the exact stored pipeline seconds over coarse timestamp diffs.
- Why: Pipeline experiments needed faster run-input iteration and trustworthy result feedback, especially when sub-minute runs were showing `00:00:00` despite non-zero pipeline time.
- Validation: `python3 -m py_compile views/pipeline.py services/pipeline_runtime.py tests/test_pipeline_runtime.py`; `.venv/bin/python -m pytest -q tests/test_pipeline_runtime.py tests/test_openai_title_suggestions.py tests/test_settings.py`; live check confirmed Duration now follows the `Total pipeline seconds` value from the last run.
- Files: `views/pipeline.py`, `services/openai_title_suggestions.py`, `services/pipeline_runtime.py`, `services/settings.py`, `tests/test_pipeline_runtime.py`, `tests/test_openai_title_suggestions.py`

### Streamlined New Roles page hierarchy
- Summary: removed duplicate "New Roles" headings, renamed the queue/list header and KPI copy for clearer hierarchy, tightened the filter and action layouts, removed extra card dividers, and merged the AI fit plus source expanders into one `More Details` panel.
- Why: the page repeated the same label too many times and stacked secondary details in a way that made the review flow feel noisy and fragmented.
- Validation: `python3 -m py_compile views/new_roles.py ui/components.py ui/styles.py`; visual check against the provided page screenshot and requested follow-up adjustment.
- Files: `views/new_roles.py`, `ui/components.py`, `ui/styles.py`, `docs/ui-ux-changelog.md`

### Initialized UI/UX changelog
- Summary: created the dedicated running changelog for UI/UX work.
- Why: to keep UI/UX changes easy to track separately from Discovery Tech and AI Analysis work.
- Validation: file created in repo docs.
- Files: `docs/ui-ux-changelog.md`
