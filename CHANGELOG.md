# Changelog

All notable changes to this project should be tracked here.

This project follows semantic versioning:
- `MAJOR` for product-shape changes or major architectural shifts
- `MINOR` for meaningful new capabilities that keep the product recognizably the same
- `PATCH` for bug fixes, polish, install improvements, and small workflow refinements

## [1.0.6] - 2026-04-06

- Tightened AI lane detection so `AI` executive titles survive ATS prefiltering without broadly loosening unrelated job pages.
- Kept ATS detail filtering narrow while improving recall for AI and technology leadership searches.
- Rebuilt macOS auto-run setup around the installed app bundle so LaunchAgent scheduling points at the packaged runner script.

## [1.0.5] - 2026-04-06

- Fixed macOS automatic-run packaging so the `.dmg` now includes the scheduled runner script inside the app bundle.
- Made the desktop wrapper honor scheduled-run invocations by running `run_scheduled_jobs.py` when launchd passes it in.
- Hardened Mac auto-run configuration so it prefers the installed `/Applications` bundle instead of a translocated app path.

## [1.0.4] - 2026-04-03

- Simplified Pipeline down to `Find Roles` and `Search Results` so the main search path is easier to understand.
- Removed the extra internal-facing Pipeline sections and debated link-only import actions from the main user flow.
- Simplified Settings `System Status` down to health, backups, restore, and reset.
- Switched `Configuration` to auto-save so settings changes persist immediately without a separate save step.
- Changed the default `New Roles` sort to `Newest First`.

## [1.0.3] - 2026-04-03

- Fixed the Source Layer tab crash caused by a missing `os` import in Settings.
- Fixed `Save Run Inputs` so manually added target titles are preserved and AI variants append instead of replacing them.
- Improved legacy Workday parsing by recovering job titles from Workday URL slugs when pages render as JavaScript shells.
- Tightened location scoring so Dallas-style locations embedded in broader U.S. labels do not get penalized as false mismatches.

## [1.0.2] - 2026-04-02

- Fixed the Setup Wizard `Suggest Relevant Updates` crash caused by writing back into live widget state during the same render cycle.
- Continued desktop wrapper hardening for Windows and Mac test builds, including versioned package filenames for easier tester tracking.

## [1.0.1] - 2026-04-01

Current friend-test release.

Highlights:
- unified `Run Jobs` flow with existing-job refresh/rescore built in
- automatic run scheduling in Settings
- cleaner Pipeline layout and improved `Save Run Inputs` behavior
- line-based title/location inputs plus explicit `Include Remote`
- improved hybrid/location parsing for jobs that were being mislabeled as remote
- `Run Jobs` now routes directly to `New Roles` when jobs are found

## [1.0.0] - 2026-03-26

Initial soft-launch baseline.

Highlights:
- local-first Streamlit app with Setup Wizard, Pipeline, New Roles, Applied Roles, and Settings
- OpenAI-assisted title suggestions, scoring, scrub, and cover letters
- backup, health check, reset, and local key management
- friend-test-ready onboarding on macOS and a validated Windows path
