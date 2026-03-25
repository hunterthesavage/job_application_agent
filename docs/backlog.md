# Backlog

Current soft-launch estimate: **91%**

This backlog is intentionally launch-focused. It reflects what is still worth doing after the recent scoring, setup, installer, and UI cleanup work.

## High Priority

### Validate Windows install on a real machine
The Windows launchers exist, but they still need a real runtime install and launch pass instead of only code review.

### Complete the with-AI acceptance pass
Run a full first-time flow with a real OpenAI key and confirm title expansion, scoring, scrub, and cover letters all behave as expected.

### Run one external friend test without hand-holding
Have one tester install, onboard, run discovery, review roles, and report confusion points without extra explanation.

### Fix only launch blockers from real-user feedback
Use the next tester pass to close confusion loops, persistence bugs, or broken install steps instead of adding new product scope.

## Medium Priority

### Match the Setup Wizard Profile Context flow to Settings
Bring the same step-driven 1-2-3 visual treatment into the wizard so profile setup feels consistent everywhere.

### Review long-run busy and reset behavior
Double-check how discovery and rescoring communicate progress, long waits, and recovery when a run takes longer than expected.

### Clarify combined AI toggle behavior in Pipeline
The single run-level AI toggle is simpler, but the page may still need clearer wording for actions like `Find Job Links Only` that only use part of it.

### Fix inaccurate duration timing in run results
The Duration timer is not always reflecting real elapsed time. This should be tightened so Pipeline results and status views feel trustworthy.

### Add a Fortune 500 career-site registry and filter
Integrate a curated Fortune 500 URL list for company career sites, use it as a higher-signal discovery source similar to ATS seed sources, and add a filter so users can choose to surface only jobs from those Fortune 500 URLs.

### Add direct API integrations for more discovery sources
Evaluate direct API integrations that can pull additional job URLs into the pipeline so the app can score more high-quality roles without depending only on search and current ATS-source coverage.

### Decide whether environment-key fallback should stay
The app now explains saved versus environment keys clearly, but public users may still benefit from an even simpler saved-local-key-only model.

## Low Priority

### Tighten internal docs after launch hardening
Refresh architecture, current-state, and settings-reference docs so they reflect the current app instead of earlier build phases.

### Clean up remaining packaging and dependency rough edges
Keep reviewing setup assumptions, optional dependencies, and platform notes after the soft-launch path is proven.

### Revisit orchestration boundaries after soft launch
Session state, view code, and runtime services still carry some operator complexity that is acceptable now but will be a future scaling constraint.

## Recently Completed

- Public experimental repo prep and README install cleanup
- Pipeline split into calmer subpages with clearer run, results, and research flows
- Settings cleanup with a dedicated System Status section
- Resume-driven Profile Context generation with AI gating
- Improved API key source handling for saved local keys versus environment keys
- AI scrub visibility, correction summaries, and rescore improvements
