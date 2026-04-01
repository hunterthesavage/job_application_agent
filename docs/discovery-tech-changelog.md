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

## 2026-04-01

### Added a prioritized legacy search quality worklist and cleaned generic company placeholders
- Summary: added a plain-language legacy search quality worklist for the next V1 discovery cycle and taught company extraction to ignore generic placeholder labels like `page_title` when a better fallback brand is available.
- Why: we had enough evidence to stop debating the engine choice and needed a concrete improvement order for legacy, while also fixing a visible metadata trust issue surfaced by the matrix comparisons.
- Validation: `python3 -m py_compile src/validate_job_url.py tests/test_smoke_regression.py`; `.venv/bin/python -m pytest -q tests/test_smoke_regression.py`; new regression covers fallback from `page_title` to `Figma`.
- Files: `docs/legacy-search-quality-worklist.md`, `src/validate_job_url.py`, `tests/test_smoke_regression.py`, `docs/discovery-tech-changelog.md`

### Documented the V1 search decision and recommendation
- Summary: added a plain-language V1 search decision document that explains why legacy remains the production engine, why direct-source stays internal-only, and what discovery work should happen next.
- Why: after the title-matrix and real-job profile scoring passes, we had enough evidence to stop treating source-layer mode as an open product question and needed one clear decision document to align future work.
- Validation: reviewed against the live comparison outputs in `logs/discovery_debug/*matrix*` and `logs/scoring_calibration/20260401-122246_real_job_profiles/report.md`; recommendation matches the current measured outcome that legacy remains more dependable and usually higher-fit.
- Files: `docs/v1-search-decision.md`, `docs/discovery-tech-changelog.md`

### Reframed next-gen as a bounded direct-source seeding experiment
- Summary: tightened `next_gen` into a smaller direct-source seed lane by capping seed selection at 12 endpoints, lowering per-company seeded URL cap to 2, updating runtime/shadow/status messaging to say `direct-source`, and making the source-layer smoke parser understand both old `Next-gen ...` notes and new `Direct-source ...` notes.
- Why: the old `next_gen` name was obscuring what the mode actually does, and the wider seed batches were slow without showing enough lift. We needed clearer internal diagnostics plus a cheaper experiment before deciding whether this path is worth more V1 time.
- Validation: `python3 -m py_compile services/pipeline_runtime.py services/source_layer_shadow.py services/source_layer_status_smoke.py views/settings.py tests/test_pipeline_runtime.py tests/test_source_layer_status_smoke.py tests/test_source_layer_shadow.py`; `.venv/bin/python -m pytest -q tests/test_pipeline_runtime.py tests/test_source_layer_status_smoke.py tests/test_source_layer_shadow.py`; local debug comparisons showed `VP of IT` remote stayed `0` URLs in both modes while direct-source scanned `24` seeds, and `Director of IT` remote improved only from `0` legacy URLs to `1` direct-source-seeded URL (`Associate Director - Global Compliance Platform` at Amgen), which is still too weak to graduate beyond internal use.
- Files: `services/pipeline_runtime.py`, `services/source_layer_shadow.py`, `services/source_layer_status_smoke.py`, `views/settings.py`, `tests/test_pipeline_runtime.py`, `tests/test_source_layer_status_smoke.py`, `tests/test_source_layer_shadow.py`, `docs/discovery-tech-changelog.md`

### Added a repeatable title-matrix comparison runner
- Summary: added a source-layer title matrix runner that executes paired `legacy` vs `next_gen` debug runs across a default top-10 title set and writes markdown, JSON, and CSV summaries into `logs/discovery_debug_suites`.
- Why: we needed a broader representative comparison than only executive tech titles so we can judge whether direct-source seeding helps across common roles like Business Analyst and Project Manager, not just the searches you personally care about.
- Validation: `python3 -m py_compile scripts/run_source_layer_title_matrix.py`
- Files: `scripts/run_source_layer_title_matrix.py`, `docs/discovery-tech-changelog.md`

## 2026-03-28

### Preferred validated seed pool now leads next-gen shadow selection
- Summary: populated the local shadow registry from the legacy validated endpoint export and updated next-gen shadow selection so it prefers seedable, validated, high-confidence, primary endpoints before backfilling from the broader imported pool.
- Why: next-gen was finally operational after shadow import, but it was still choosing from the entire imported registry too evenly, which let weak or off-target seeds crowd out the more trustworthy ATS roots we actually want to test first.
- Validation: `python3 -m services.source_layer_legacy_smoke`; `python3 -m services.source_layer_shadow_populate`; `python3 -m services.source_layer_status_smoke`; `python3 -m py_compile services/source_layer_shadow.py tests/test_source_layer_shadow.py`; `.venv/bin/python -m pytest -q tests/test_source_layer_shadow.py`; live selector output now reports `Preferred next-gen seed pool: 114` and `Preferred next-gen candidates selected: 25`.
- Files: `services/source_layer_shadow.py`, `tests/test_source_layer_shadow.py`, `docs/discovery-tech-changelog.md`

### Made Workday seeds search title-aware before broad fallback
- Summary: Workday next-gen seed discovery now queries the Workday jobs API with the normalized seed title first, falls back to the broad job catalog only when needed, and uses structured posting title/location fields to reject obvious off-target or foreign-remote results before building detail URLs.
- Why: Workday extraction itself is healthy, but broad catalog paging was pulling too many irrelevant postings, and the cheap remote gate was still letting explicit non-U.S. remote hints slip through in sparse senior-tech runs.
- Validation: `python3 -m py_compile services/pipeline_runtime.py tests/test_pipeline_runtime.py`; `.venv/bin/python -m pytest -q tests/test_pipeline_runtime.py`; local `VP of IT` debug run produced `next_gen_seed_url_count=4` instead of zero in `logs/discovery_debug/20260328-173854_vp-of-it-remote/summary.json`
- Files: `services/pipeline_runtime.py`, `tests/test_pipeline_runtime.py`

## 2026-03-27

### Removed duplicate next-gen seed roots from shadow selection
- Summary: next-gen shadow selection now avoids selecting the same endpoint URL more than once, even when multiple companies map to that shared ATS root.
- Why: duplicate selected roots were wasting limited seed slots, especially in Workday-heavy sparse senior-tech runs.
- Validation: `.venv/bin/python -m pytest -q tests/test_source_layer_shadow.py`; targeted `VP of IT` next-gen seed discovery improved from `2` seeded URLs to `5`.
- Files: `services/source_layer_shadow.py`, `tests/test_source_layer_shadow.py`

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
