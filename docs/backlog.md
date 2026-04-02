# Backlog

Current soft-launch estimate: **91%**

This backlog is intentionally launch-focused and ranked by ROI, not by feature novelty.

## Now

These are the items we should actively work against and reference going forward.

### Run one external friend test without hand-holding
Use the current Windows package and README flow, then watch for where the tester gets stuck without extra explanation.

### Complete the with-AI acceptance pass
Run the first-time flow with a real OpenAI key and confirm title expansion, scoring, scrub, and cover letters all work end to end.

### Fix only launch blockers from real-user feedback
Use the next tester and acceptance passes to close broken install steps, confusing UI, persistence issues, and obvious workflow gaps before adding new product scope.

### Improve legacy search quality with the new benchmarks
Treat Legacy as the V1 engine and use the title matrix plus real-job profile scoring to reduce weak adjacent matches and improve what appears first in `New Roles`.

### Review long-run busy and reset behavior
Double-check how discovery and rescoring communicate progress, long waits, and recovery when a run takes longer than expected.

## Next

These matter, but they should follow the active launch-validation loop above.

### Clarify combined AI toggle behavior in Pipeline
The single run-level AI toggle is simpler, but the page still needs clearer wording for actions like `Find Job Links Only` that only use part of it.

### Match the Setup Wizard Profile Context flow to Settings
Bring the same step-driven 1-2-3 visual treatment into the wizard so profile setup feels consistent everywhere.

### Decide whether environment-key fallback should stay
The app now explains saved versus environment keys clearly, but public users may still benefit from an even simpler saved-local-key-only model.

### Validate the Windows package on one more real machine
The packaging path is much healthier now, but one more real-machine pass would further de-risk broader sharing.

### Prefer the Windows installer over the portable zip
Once the desktop wrapper installer is stable, promote the one-file Windows setup `.exe` as the main handoff and keep the zip only as fallback.

## Later

These are worth keeping, but they are not the best V1 use of time right now.

### Sign and notarize the Mac desktop package
Use Apple Developer ID signing, notarization, and stapling so the desktop app stops showing the unidentified developer/security friction on first launch.

### Surface OpenAI usage, token, and cost visibility
Add a read-only app view that shows OpenAI usage for the configured key, including token consumption, cost, and links back to billing or usage pages.

### Add a Fortune 500 career-site registry and filter
Use the curated registry as a trusted seed lane and optional ranking/filter signal only after V1 search quality is stable.

### Expand discovery beyond the Fortune 500 seed set
Build broader employer and ATS endpoint coverage once the V1 engine and review experience are stable enough to benefit from more source expansion.

### Add direct API integrations for more discovery sources
Evaluate API-based discovery expansion only after the shipped legacy path is validated and the ROI is clearer than it is today.

### Tighten internal docs after launch hardening
Refresh architecture, current-state, and settings-reference docs so they reflect the current app instead of earlier build phases.

### Clean up remaining packaging and dependency rough edges
Keep reviewing setup assumptions, optional dependencies, and platform notes after the soft-launch path is proven.

### Revisit orchestration boundaries after soft launch
Session state, view code, and runtime services still carry some operator complexity that is acceptable now but will be a future scaling constraint.

## Done / Stale

### Fix inaccurate duration timing in run results
This appears addressed already and should no longer be treated as active launch work unless new evidence shows the Duration display is still wrong.

### Decide the V1 search engine
Settled: `Legacy` is the engine for V1, while direct-source stays internal-only.

## Recently Completed

- Documented the V1 search decision and moved direct-source to internal-only status
- Added the title-matrix and real-job profile scoring benchmarks
- Defaulted `New Roles` review ordering to `Highest Fit Score`
- Recovered and clarified the Windows installer path with screenshot-driven README guidance
- Made `Broader Search` the default visible search strategy
