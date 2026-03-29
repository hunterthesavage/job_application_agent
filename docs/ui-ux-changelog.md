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

## 2026-03-28

### Simplified Windows install guide and renamed the launcher
- Summary: reduced the Windows README section to a tester-only step-by-step flow, added visual install panels, and renamed the packaged launcher from `Launch Job Application Agent.bat` to `INSTALL JAA.bat`.
- Why: the old wording still created confusion during friend testing, and the launcher name needed to be shorter and more obvious once the folder was extracted.
- Validation: reviewed the README against the portable package structure and updated the build/release docs so the packaged launcher name now matches the install steps.
- Files: `README.md`, `scripts/build_windows_portable.ps1`, `docs/windows-portable-build.md`, `.github/workflows/windows-portable-release.yml`, `docs/assets/windows-install-step-1-download.svg`, `docs/assets/windows-install-step-2-extract.svg`, `docs/assets/windows-install-step-3-launch.svg`, `docs/ui-ux-changelog.md`

### Added a direct Windows release link and extraction checklist
- Summary: updated the README to include the exact portable zip release link, clearer post-download steps, a folder-content check for `Launch Job Application Agent.bat` plus the `app` and `python` folders, and an explicit warning not to run the launcher from inside the zip preview.
- Why: a tester hit a confusing Windows path error because the prior README still was not concrete enough about extracting the zip fully before launching.
- Validation: reviewed the live release asset name and matched the README instructions to the actual packaged folder structure.
- Files: `README.md`, `docs/ui-ux-changelog.md`

### Added a release-based Windows download path for testers
- Summary: added a GitHub workflow that builds the portable Windows package and publishes `JobApplicationAgent-windows-portable.zip` as a release asset, then rewrote the README to send testers to Releases instead of Actions artifacts.
- Why: Actions artifacts were too hidden and confusing for friend testers, even after the portable installer itself was working.
- Validation: reviewed the release workflow inputs, asset path, and README install steps together so the tester path now points at a normal GitHub release download.
- Files: `.github/workflows/windows-portable-release.yml`, `README.md`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

### Aligned GitHub Windows artifact flow with README install steps
- Summary: changed the portable-package GitHub workflow to upload the unpacked `JobApplicationAgent` folder and tightened the README/docs wording so the Actions download path now matches the actual tester extraction flow.
- Why: the previous setup produced a nested zip experience that did not cleanly match the README’s “download, extract, open folder, launch” instructions.
- Validation: reviewed the portable build output, workflow artifact path, and README steps together to ensure the GitHub Actions artifact now unpacks directly to the launcher folder.
- Files: `.github/workflows/windows-portable.yml`, `README.md`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

### Clarified Windows tester install directions in README
- Summary: rewrote the Windows portable-install section so testers are explicitly told not to use the normal source zip, where to find the portable artifact, and exactly which launcher to double-click after extraction.
- Why: the earlier README still left too much room for confusion even after the portable package work landed, especially for friend testers downloading from GitHub.
- Validation: reviewed the updated README flow end to end against the GitHub artifact path and the packaged launcher name.
- Files: `README.md`, `docs/ui-ux-changelog.md`

### Added automated Windows smoke coverage for tester installs
- Summary: added a GitHub Actions Windows smoke workflow that checks the Python 3.9 compatibility files from the tester crash and verifies the portable package can build and boot on a Windows runner.
- Why: the new Windows install path needed real Windows validation before handing it to friend testers, especially after a Python-version-specific startup failure.
- Validation: workflow definition added for `windows-latest` with a Python 3.9 compile check and a portable-package launch health check against Streamlit.
- Files: `.github/workflows/windows-smoke.yml`, `docs/ui-ux-changelog.md`

## 2026-03-27

### Added a portable Windows install path for testers
- Summary: added a maintainer build script for a bundled Windows portable package, a manual GitHub workflow to produce the package artifact, and README guidance that now recommends the no-Python double-click install path first.
- Why: friend-tester setup was too fragile and confusing when it depended on installing Python, creating a virtual environment, and launching Streamlit manually.
- Validation: reviewed the generated packaging flow, added the Windows artifact workflow, and prepared targeted compatibility checks for the Python 3.9 fallback path.
- Files: `scripts/build_windows_portable.ps1`, `.github/workflows/windows-portable.yml`, `docs/windows-portable-build.md`, `README.md`, `docs/ui-ux-changelog.md`

### Run-input save button no longer gets stuck disabled
- Summary: Removed the disabled-state trap from the Pipeline run-input form so `Save Run Inputs` remains clickable after edits inside the Streamlit form.
- Why: Fresh UI testing showed that changing fields like `Target Titles` did not enable the save button because Streamlit forms do not rerender the button's disabled state while typing.
- Validation: Ran `.venv/bin/python -m py_compile views/pipeline.py services/openai_key.py`.
- Files: `views/pipeline.py`

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
