# Soft Launch Checklist

Current estimate: **91% to soft launch**

Use this checklist to track launch readiness and avoid adding more features before the core experience is validated.

## Progress Milestones

### 80%
- Fresh clone installs cleanly
- Setup Wizard is understandable without explanation
- First `Find and Add Jobs` run completes
- `New Roles` loads and is usable

### 85%
- Cover letter generation works end to end
- Mark as Applied flow works cleanly
- Rescore works without confusing regressions
- Settings persist across reruns and navigation
- Release checks pass

### 90%
- One real external friend test is completed
- Their confusion points are documented
- Only minor polish issues remain

### 100%
- External feedback is addressed
- No known launch-blocking bugs remain
- Repo is clean and published

## Release Candidate Validation

### 1. Fresh Clone Install
- Clone from GitHub into a new folder
- Create `.venv`
- Install requirements
- Launch Streamlit
- Confirm the app opens to Setup Wizard when there are no jobs yet

### 2. Setup Wizard
- OpenAI API step is understandable
- Profile Context starter template is usable
- Search Criteria step is understandable
- AI Review step is understandable
- First run starts without confusion

### 3. First Run
- Successful first discovery lands in `New Roles`
- Zero-result first discovery lands in `Pipeline`
- Success and warning states feel clear

### 4. New Roles Review
- Cards feel trustworthy
- `AI Fit Detail` is understandable
- `AI corrections` make sense when present
- Filters and sorting are clear

### 5. Cover Letter
- Output folder persists
- Generation succeeds
- File is saved in the expected location

### 6. Applied Flow
- Job moves from `New Roles` to `Applied Roles`
- Applied page remains understandable

### 7. Rescore
- Small rescore batch completes
- Older jobs refresh cleanly
- Metadata and scoring changes remain understandable

### 8. Settings Persistence
- Cover letter output folder persists
- Profile Context persists
- Preferred job levels persist
- OpenAI key status is clear

### 9. Release Checks
Run:

```bash
./scripts/run_release_checks.sh
```

Expected:
- release checks pass without failures

## Current Highest-Leverage Remaining Work

1. Complete the end-to-end release candidate pass from a true fresh clone
2. Run one external friend test without hand-holding
3. Fix only launch blockers, confusion points, or persistence issues
