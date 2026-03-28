# AI Scoring Calibration

This workflow is the starting point for scoring calibration in GitHub.

## Goal

Measure how the current qualifier and AI scoring behave on a small labeled set of real or representative jobs instead of tuning by feel.

## Starter dataset

The repo includes a small sample set here:

- `scripts/calibration_sets/vp_it_sample.jsonl`

Each case includes:

- `expected_label`: `yes`, `maybe`, or `no`
- job title, company, location, and description text
- search settings like `target_titles`, `preferred_locations`, and `remote_only`

## Run the calibration

Qualifier-only:

```bash
python3 scripts/run_scoring_calibration.py
```

Qualifier + AI scoring:

```bash
python3 scripts/run_scoring_calibration.py --use-ai-scoring
```

Reports are written under:

- `logs/scoring_calibration/<timestamp>_<case-file>/report.md`
- `logs/scoring_calibration/<timestamp>_<case-file>/report.json`

## How to use it

1. Start with a small labeled set for one search shape, such as `VP of IT`.
2. Review far misses first.
3. Decide whether the failure came from:
   - qualifier acceptance logic
   - AI fit scoring
   - bad inputs from discovery
4. Tune one layer at a time.

## Recommended next expansion

- add a larger `VP of IT` set using real jobs from recent discovery runs
- add a second set for adjacent searches such as `VP Infrastructure`
- track exact matches, adjacent matches, and far misses over time
