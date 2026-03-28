# Discovery Tech Changelog

This file is the running changelog for Discovery Tech work only.

Rules:
- Update this file every time a Discovery Tech change is made.
- Keep entries short and concrete.
- Focus on discovery pipeline behavior, diagnostics, ATS extraction, seed selection, filtering, and related tests.
- Do not mix in unrelated UI, product copy, or general repo housekeeping.

Entry format:

## YYYY-MM-DD

### Short change title
- Summary: what changed.
- Why: the bottleneck, bug, or reason for the change.
- Validation: tests run, live checks, or observed outcome.
- Files: relevant files only.

---

## 2026-03-27

### Added local discovery debug harness and next-gen seed diagnostics
- Summary: added a repeatable local discovery debug runner, comparison suite tooling, rejected-search-result diagnostics, normalized seed-query generation, diversified next-gen ATS family selection, fallback deduping, and seed-shape ranking improvements across Workday, iCIMS, SuccessFactors, and Taleo.
- Why: sparse senior-tech searches like `VP of IT` were still returning zero discovered URLs, and the discovery loop was too manual and too opaque to debug efficiently.
- Validation: `python3 -m py_compile scripts/run_local_discovery_debug.py scripts/compare_discovery_debug_reports.py scripts/run_discovery_debug_suite.py services/pipeline_runtime.py services/search_plan.py services/source_layer_shadow.py services/url_resolution.py src/discover_job_urls.py`; `.venv/bin/python -m pytest -q tests/test_source_layer_shadow.py tests/test_pipeline_runtime.py tests/test_search_plan.py tests/test_discover_job_urls.py tests/test_openai_title_suggestions.py tests/test_settings.py`; live reruns showed healthier next-gen ATS-family mix and no duplicate fallback seed scans.
- Files: `scripts/run_local_discovery_debug.py`, `scripts/compare_discovery_debug_reports.py`, `scripts/run_discovery_debug_suite.py`, `scripts/debug_profiles/vp_it_remote_next_gen.json`, `scripts/debug_profiles/vice_president_information_technology_remote_next_gen.json`, `scripts/debug_profiles/vp_infrastructure_remote_next_gen.json`, `services/pipeline_runtime.py`, `services/search_plan.py`, `services/source_layer_shadow.py`, `services/url_resolution.py`, `src/discover_job_urls.py`, `tests/test_pipeline_runtime.py`, `tests/test_source_layer_shadow.py`, `tests/test_search_plan.py`, `tests/test_discover_job_urls.py`

### Improved next-gen seed extraction across ATS families
- Summary: added broader next-gen seed extraction support across iCIMS, SuccessFactors, and Workday, plus a public `record_source_layer_run()` export for cleaner pipeline runtime integration.
- Why: next-gen seeded URL discovery was underperforming because several ATS families were returning zero extracted URLs despite reasonable seed roots.
- Validation: `pytest tests/test_pipeline_runtime.py tests/test_source_layer_import.py -q`
- Files: `services/pipeline_runtime.py`, `services/source_layer_import.py`, `tests/test_pipeline_runtime.py`

### Fixed iCIMS and branded-site seed extraction
- Summary: iCIMS seed discovery now tolerates failing `/jobs` fallback probes, supports no-title browse flows, parses relative job links, and follows TalentBrew-style `/search-jobs` pages.
- Why: selected iCIMS seeds were logging zero discovered URLs or hard failures before title/location filtering could help.
- Validation: live next-gen rerun moved seeded URLs from `0` to `33`.
- Files: `services/pipeline_runtime.py`, `tests/test_pipeline_runtime.py`

### Fixed SuccessFactors browse-mode seed extraction
- Summary: branded SuccessFactors sites can now enumerate `/search/` results without requiring a title query, with generic `/job/` link fallback.
- Why: sparse searches were failing at extraction time because the old code required a title and assumed one narrow result shape.
- Validation: live next-gen rerun produced seeded URLs from multiple SuccessFactors roots including Brighthouse, CMS Energy, Dover, HF Sinclair, Lear, Mohawk, Paramount, and UGI.
- Files: `services/pipeline_runtime.py`, `tests/test_pipeline_runtime.py`

### Fixed Workday sparse-search extraction path
- Summary: `_discover_workday_jobs()` now pages through Workday CXS results and returns raw detail URLs instead of filtering internally on the first page.
- Why: Workday metadata and endpoint derivation were valid, but sparse senior-tech searches like `VP of IT` were failing because internal filtering ran too early and too narrowly.
- Validation: direct probes showed real raw/kept results for representative Workday seeds such as Allstate and Centene under sparse senior-tech settings.
- Files: `services/pipeline_runtime.py`, `tests/test_pipeline_runtime.py`
