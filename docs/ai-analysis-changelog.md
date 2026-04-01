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

## 2026-04-01

### Added real-job profile scoring bridge for discovery mode comparisons
- Summary: added a runner that takes real discovered job URLs from discovery debug reports, parses them into job payloads, scores them against the fake profile pack, and writes markdown/JSON/CSV summaries for side-by-side legacy vs direct-source comparisons.
- Why: raw URL counts were not enough to judge whether discovery modes were surfacing better jobs, and we needed a way to connect real discovered jobs to persona-fit scoring before recommending the next search strategy move.
- Validation: `python3 -m py_compile scripts/run_real_job_profile_scoring.py`; live run `python3 scripts/run_real_job_profile_scoring.py --report-dir logs/discovery_debug/20260401-114141_matrix-business-analyst-legacy --report-dir logs/discovery_debug/20260401-114309_matrix-business-analyst-next-gen --report-dir logs/discovery_debug/20260401-114439_matrix-project-manager-legacy --report-dir logs/discovery_debug/20260401-114605_matrix-project-manager-next-gen --report-dir logs/discovery_debug/20260401-114754_matrix-product-manager-legacy --report-dir logs/discovery_debug/20260401-114920_matrix-product-manager-next-gen --report-dir logs/discovery_debug/20260401-115051_matrix-data-analyst-legacy --report-dir logs/discovery_debug/20260401-115154_matrix-data-analyst-next-gen --max-urls 1` wrote reports under `logs/scoring_calibration/20260401-122246_real_job_profiles` and showed legacy top jobs outscoring direct-source top jobs on `Business Analyst`, `Product Manager`, and `Data Analyst`, while `Project Manager` remained weak in both modes.
- Files: `scripts/run_real_job_profile_scoring.py`, `docs/ai-analysis-changelog.md`, `docs/ai-scoring-calibration.md`

### Added fake-profile calibration pack for cross-persona scoring checks
- Summary: added four representative fake resume/profile packs with labeled case sets plus a runner that executes scoring calibration across all profiles and writes per-profile reports and a consolidated summary.
- Why: discovery comparisons alone were not enough to judge whether the scoring layer understands different candidate personas, and we needed a reusable way to test analyst, product/program, GTM, and executive IT profiles against the same scoring pipeline.
- Validation: `python3 -m py_compile scripts/run_fake_resume_calibration.py`; live run `python3 scripts/run_fake_resume_calibration.py --use-ai-scoring` wrote reports under `logs/scoring_calibration/20260401-120202_fake_resume_profiles`; AI scoring matched all 5 cases for `Executive IT Leader` and `Business & Data Analyst`, 4/5 for `Product & Program Generalist`, and 4/5 plus 1 adjacent for `GTM / Marketing Ops`.
- Files: `scripts/run_fake_resume_calibration.py`, `scripts/fake_profiles/executive_it_leader.txt`, `scripts/fake_profiles/product_program_generalist.txt`, `scripts/fake_profiles/business_data_analyst.txt`, `scripts/fake_profiles/gtm_marketing_ops.txt`, `scripts/calibration_sets/fake_resume_executive_it_leader.jsonl`, `scripts/calibration_sets/fake_resume_product_program_generalist.jsonl`, `scripts/calibration_sets/fake_resume_business_data_analyst.jsonl`, `scripts/calibration_sets/fake_resume_gtm_marketing_ops.jsonl`, `docs/ai-analysis-changelog.md`

## 2026-03-28

### Aligned qualifier title overlap with search-safe title variants
- Summary: updated the deterministic qualifier to score against the same search-safe title variants used in discovery, so shorthand targets like `VP of IT` now match explicit titles like `Vice President, Information Technology`.
- Why: the first calibration run exposed an exact-fit false reject caused by literal title overlap logic in the qualifier.
- Validation: `python3 -m py_compile services/job_qualifier.py services/scoring_calibration.py scripts/run_scoring_calibration.py tests/test_job_qualifier.py tests/test_scoring_calibration.py`; `.venv/bin/python -m pytest -q tests/test_job_qualifier.py tests/test_scoring_calibration.py tests/test_ai_job_scoring.py`; starter calibration report moved from `qualifier_exact=2 / far_misses=1` to `qualifier_exact=3 / far_misses=0`
- Files: `services/job_qualifier.py`, `tests/test_job_qualifier.py`, `services/scoring_calibration.py`, `tests/test_scoring_calibration.py`

### Added a repeatable scoring calibration harness
- Summary: added a reusable calibration service, CLI runner, starter labeled `VP of IT` sample set, and tests so qualifier and AI scoring behavior can be compared against expected `yes / maybe / no` outcomes.
- Why: scoring was stable enough to move forward, but there was no evidence-driven workflow to measure false rejects, weak accepts, or AI over-scoring before tuning in GitHub.
- Validation: `python3 -m py_compile services/scoring_calibration.py scripts/run_scoring_calibration.py tests/test_scoring_calibration.py`; `.venv/bin/python -m pytest -q tests/test_scoring_calibration.py tests/test_ai_job_scoring.py`
- Files: `services/scoring_calibration.py`, `scripts/run_scoring_calibration.py`, `scripts/calibration_sets/vp_it_sample.jsonl`, `tests/test_scoring_calibration.py`, `docs/ai-scoring-calibration.md`

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
