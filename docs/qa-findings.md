# QA Findings Log

Use this log for real issues found during tester passes, your own acceptance runs, or ad hoc review.

The goal is to capture:

- what was wrong
- where it showed up
- what should have happened
- which part of the system likely owns the fix

## How to log a finding

For each issue, capture:

1. **Area**
   - Discovery
   - Parsing
   - Scoring
   - UI/UX
   - Packaging / Install
   - Persistence

2. **Severity**
   - Blocker
   - High
   - Medium
   - Low

3. **What happened**
4. **Expected behavior**
5. **Example URL or screenshot**
6. **Likely owner area**
7. **Status**
   - New
   - Triaged
   - In Progress
   - Fixed
   - Won't Fix

## Routing guide

### Remote jobs that are not actually remote

Usually owned by:

- `services/location_matching.py`
- `services/pipeline_runtime.py`
- `src/validate_job_url.py`

Why:

- `validate_job_url.py` extracts and infers the location string
- `location_matching.py` decides whether a location should count as remote
- `pipeline_runtime.py` applies the final hard location gate

### Wrong company name or wrong title

Usually owned by:

- `src/validate_job_url.py`
- `services/ai_job_scrub.py`

Why:

- `validate_job_url.py` is the parser-first extraction layer for title/company/location
- `ai_job_scrub.py` is the conservative AI sanity-check layer that can flag or correct clearly wrong parsed fields when the evidence is strong

### Weak or adjacent fit that should not have ranked well

Usually owned by:

- `services/job_qualifier.py`
- `services/ai_job_scoring.py`
- `views/new_roles.py`

Why:

- `job_qualifier.py` controls deterministic acceptance
- `ai_job_scoring.py` controls fit scoring and recommended action
- `new_roles.py` controls how accepted jobs are surfaced and sorted

## Current findings

## 2026-04-01

### Remote false positives are still leaking through
- Area: Discovery
- Severity: High
- What happened: some jobs are marked or surfaced as `Remote` even though the actual job posting is not truly remote.
- Expected behavior: non-remote or location-restricted jobs should fail the remote-only path and should not appear as remote matches.
- Example: capture the job URL when you see the next instance.
- Likely owner area: `services/location_matching.py`, `services/pipeline_runtime.py`, `src/validate_job_url.py`
- Status: New

### Company name and title parsing still have visible misses
- Area: Parsing
- Severity: High
- What happened: some jobs still show the wrong company name or a weak/inaccurate title.
- Expected behavior: job cards should show trustworthy company and title values pulled from the posting or corrected conservatively.
- Example: capture the job URL when you see the next instance.
- Likely owner area: `src/validate_job_url.py`, `services/ai_job_scrub.py`
- Status: New

## Recommendation

Use this log as the intake layer, then move only confirmed launch-impacting items into the active `Now` backlog lane.
