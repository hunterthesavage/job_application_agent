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

## 2026-03-29

### Made fit-first review ordering the default for new queues
- Summary: changed the default `New Roles` review sort from `Newest First` to `Highest Fit Score` and aligned the Settings defaults UI with that fit-first behavior.
- Why: current V1 search quality is better judged by surfacing the strongest-fit jobs first, and recency-first ordering was burying better matches that were already in the queue.
- Validation: `python3 -m py_compile services/settings.py views/settings.py views/new_roles.py`
- Files: `services/settings.py`, `views/settings.py`, `views/new_roles.py`, `docs/ui-ux-changelog.md`

### Simplified V1 search controls while keeping Source Layer available for testing
- Summary: renamed the public Pipeline search strategies to `Standard` and `Broader Search`, added a light-results nudge back to Run Jobs when broader search may help, and hid the internal `Source Layer` Settings subtab behind a new `Show Internal Search Tools` toggle.
- Why: V1 needs a cleaner search surface for normal users, but you still need a deliberate way to expose Source Layer diagnostics when testing discovery behavior.
- Validation: `python3 -m py_compile views/pipeline.py views/settings.py services/settings.py src/discover_job_urls.py`
- Files: `views/pipeline.py`, `views/settings.py`, `services/settings.py`, `src/discover_job_urls.py`, `docs/ui-ux-changelog.md`

### Made Broader Search the default V1 path and moved Backlog behind the internal reveal
- Summary: switched the default stored search strategy to `broad_recall`, reordered the Pipeline search choices so `Broader Search` appears first, updated the helper copy to position it as the recommended default, and hid `Backlog` behind the same internal reveal toggle as `Source Layer`.
- Why: test runs showed `Broader Search` was giving better recall without obvious junk, so treating it as the normal V1 path is clearer than presenting it like an exceptional mode. The public Settings surface also stays cleaner when backlog stays internal-only.
- Validation: `python3 -m py_compile views/pipeline.py views/settings.py services/settings.py src/discover_job_urls.py`
- Files: `views/pipeline.py`, `views/settings.py`, `services/settings.py`, `docs/ui-ux-changelog.md`

### Promoted the newer Windows package to the primary live download
- Summary: updated the Windows docs so the newer portable package is treated as the current live Windows install, while the older known-good recovery zip remains linked as the fallback option.
- Why: the newer package is now the preferred friend-test path, and continuing to describe it as a test package creates confusion once it becomes the package we actually want people to use first.
- Validation: reviewed the Windows README and build notes so the primary/fallback roles now match the intended release flow.
- Files: `README.md`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

### Included the current UI files in the Windows package overlay
- Summary: expanded the Windows package builder so it now overlays `ui/components.py` and `ui/styles.py` in addition to the existing narrow app updates.
- Why: the latest close-button and OpenAI badge changes were present on `main` but missing from the Windows package because the builder was not copying those UI files into the packaged app.
- Validation: reviewed the builder overlay list against the files changed by the recent UI pass and confirmed the missing UI modules are now explicitly copied into the package.
- Files: `scripts/build_windows_portable.ps1`, `docs/ui-ux-changelog.md`

### Promoted the Windows test package to the primary README download
- Summary: updated the Windows README section so the `Test Link` is now the recommended download for friend testing, while the older known-good recovery zip stays visible as the fallback option.
- Why: the newer package has the cleaner setup and worked in current testing, so the README should point testers at the package we actually want them to try first without hiding the fallback path.
- Validation: reviewed the Windows README flow to keep the screenshot placeholder order and install steps unchanged while swapping the primary/fallback download emphasis.
- Files: `README.md`, `docs/ui-ux-changelog.md`

### Replaced the Windows README placeholders with real friend-test screenshots
- Summary: added the actual Windows screenshots for downloading the zip, extracting it, opening the extracted folder, and handling the two launch prompts so the README now mirrors the real tester flow.
- Why: the placeholders were ready, and swapping in the real screenshots makes it much easier for a non-technical tester to follow the install path without guessing.
- Validation: matched each screenshot to the existing Step 1-4 order and updated the Step 4 wording so it lines up with the actual `Run` and `Allow` prompts shown in Windows.
- Files: `README.md`, `docs/assets/windows-step-1-download.png`, `docs/assets/windows-step-2-extract.png`, `docs/assets/windows-step-3-open-folder.png`, `docs/assets/windows-step-4-run-warning.png`, `docs/assets/windows-step-4-firewall.png`, `docs/ui-ux-changelog.md`

### Moved the close control into the hero and simplified OpenAI status colors
- Summary: moved `Close Application` into the upper-right hero stack, changed it to a more explicit `✕ Close Application` control, and simplified the OpenAI badge so it shows green when active and red when inactive.
- Why: the floating close button was too easy to mistake for a normal workflow action, and the prior OpenAI badge colors did not make the active/not-active state obvious enough during local UI review.
- Validation: `python3 -m py_compile app.py ui/components.py ui/styles.py`
- Files: `app.py`, `ui/components.py`, `ui/styles.py`, `docs/ui-ux-changelog.md`

### Increased the visual separation between action buttons and info surfaces
- Summary: gave primary and secondary Streamlit buttons stronger control styling with clearer borders, depth, and hover/focus states so they read more like actions instead of looking like the dark information cards and bubbles around them.
- Why: local review showed the buttons were blending into passive UI surfaces, especially in the hero and navigation areas, which made the interface feel less legible and less intentionally interactive.
- Validation: `python3 -m py_compile ui/styles.py`
- Files: `ui/styles.py`, `docs/ui-ux-changelog.md`

### Replaced the close-action blank page with a branded shutdown screen
- Summary: updated the browser-close handoff so the fallback page now shows a styled “You can close this tab now” shutdown message instead of dropping to a blank screen if the browser refuses to close automatically.
- Why: the blank shutdown page felt broken and abrupt during local UI review, especially when the browser kept the tab open after the app process had already stopped.
- Validation: `python3 -m py_compile app.py`
- Files: `app.py`, `docs/ui-ux-changelog.md`

### Switched the shutdown handoff to navigate directly to the fallback page
- Summary: converted the close flow into a two-step shutdown state so the app first rerenders a dedicated shutdown screen, then navigates the browser to a static fallback page and only after that delay shuts down the backend.
- Why: the earlier handoff still let Streamlit’s disconnect behavior interfere, so the safer sequence is to leave the live app page first and stop the backend second.
- Validation: `python3 -m py_compile app.py`
- Files: `app.py`, `docs/ui-ux-changelog.md`

### Trimmed Windows packaging merge scope to the proven path
- Summary: removed the flaky dedicated lab release workflow from the packaging branch, kept the Windows smoke coverage, and documented that the lab tester zip is refreshed manually from the latest passing smoke artifact instead of through a second automation path.
- Why: the packaging branch was otherwise ready to merge, but every push still showed a failing no-job Actions run from the extra release workflow, which created noise and made the merge look less trustworthy than the actual tested package state.
- Validation: reviewed the latest lab branch Actions runs, confirmed the newest Windows smoke run passed, and updated the maintainer docs to match the slimmer release process before merging back to `main`.
- Files: `.github/workflows/windows-portable-release.yml`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

### Made the in-app close action swap to a shutdown page before attempting tab close
- Summary: changed the `Close Application` flow to replace the current page with a lightweight shutdown screen and then attempt to close that page, instead of trying to close the live Streamlit view directly.
- Why: browsers are more willing to close a blank or minimal replacement page than an active app page, so this improves the odds that the tab closes cleanly after the local app process stops.
- Validation: reviewed the existing shutdown handler in `app.py` and replaced the direct `about:blank`/`window.close()` attempt with a shutdown-page handoff while keeping the same background-process shutdown path.
- Files: `app.py`, `docs/ui-ux-changelog.md`
### Added a dedicated Windows test link next to the known-good package
- Summary: updated the Windows README section to include a separate `Test Link` right next to the known-good package link, pointing at the current `windows-portable-lab` release asset.
- Why: using a single stable link and a single current test link side by side makes it much easier to tell whether a Windows test is using the frozen recovery package or the latest lab package.
- Validation: verified the live `windows-portable-lab` release asset URL and inserted it directly into the README next to the known-good download link.
- Files: `README.md`, `docs/ui-ux-changelog.md`

### Locked the Windows recovery package as the known-good baseline
- Summary: updated the Windows docs to point at the exact GitHub release zip recovered from the working Windows machine, documented its size and SHA256, and clarified that this baseline uses the legacy `INSTALL JAA.bat` plus visible Command Prompt flow rather than the later shutdown experiments.
- Why: Windows packaging changes had drifted away from the last package that actually worked in friend testing, so the repo needed a clearly documented fallback baseline before any more installer work continued.
- Validation: verified the live release asset matches the recovered zip byte-for-byte at `142,376,536` bytes with SHA256 `b1058358dfce16c9c58a52ec5c32ae1a08f0caefa1da2633887365901d7ba2a8`, then aligned the docs to the exact package contents.
- Files: `README.md`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

### Restored the hidden Streamlit chrome settings and matched the shutdown button style
- Summary: updated the lab package builder to write the same `.streamlit/config.toml` settings the old working Windows launcher created at first run, and changed the in-app `Close Application` control to use the existing tertiary button styling instead of the default white Streamlit button.
- Why: the lab package reintroduced the top-right Streamlit chrome because the hidden launcher no longer generated the old config file, and the new shutdown button looked out of place because it was rendering with Streamlit's default button style.
- Validation: compared the exact working zip launcher to the lab launcher, confirmed the missing config creation path, and aligned the close button with the current CSS hook used by the existing shell styling.
- Files: `app.py`, `scripts/build_windows_portable.ps1`, `docs/ui-ux-changelog.md`

### Restored the Close Application control during setup
- Summary: rendered the existing `Close Application` button during the setup wizard, not just after the main top navigation shell loads.
- Why: the lab package already had the shutdown action wired up, but the setup wizard returned too early for that button to appear, which made it look missing during first-run testing.
- Validation: reviewed the app shell flow in `app.py` and moved the same button path into the wizard branch so the UI now exposes shutdown before setup is finished.
- Files: `app.py`, `docs/ui-ux-changelog.md`

### Switched lab Windows packaging to patch the known-good baseline
- Summary: changed the lab portable-package builder to start from the exact known-good Windows release zip, strip `._...` ghost files, overlay only the narrow shutdown files needed for the in-app close flow, replace the old foreground launcher with the hidden launch helper, add `STOP JAA.bat`, and prune safe non-runtime Python clutter instead of rebuilding the app from repo source.
- Why: rebuilding the package from scratch introduced UI regressions, so future Windows packaging work needs to preserve the working app shell and only change the packaging layer on the lab branch.
- Validation: verified the exact baseline zip contents, confirmed the ghost-file count and safe Python clutter targets locally, updated the lab release workflow defaults so future packaging experiments publish to `windows-portable-lab`, expanded the Windows smoke workflow so the lab branch now gets automated Windows validation too, and fixed the stop-script cleanup path after the smoke run exposed a PowerShell `$PID` name collision.
- Files: `scripts/build_windows_portable.ps1`, `app.py`, `config.py`, `services/app_control.py`, `.github/workflows/windows-portable-release.yml`, `.github/workflows/windows-smoke.yml`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

## 2026-03-28

### Hid the packaged console and added cleaner app shutdown controls
- Summary: changed the Windows portable package to start the app through hidden PowerShell helpers, added `STOP JAA.bat`, bound the packaged server to `127.0.0.1`, disabled usage-stat prompts, and added a `Close Application` button in the main UI that shuts the local app down.
- Why: friend testing showed that the visible command window sticking around after launch felt broken and that closing the browser tab alone did not clearly stop the app.
- Validation: `python3 -m py_compile app.py config.py services/app_control.py tests/test_app_control.py`; `.venv/bin/python -m pytest -q tests/test_app_control.py`
- Files: `app.py`, `config.py`, `services/app_control.py`, `tests/test_app_control.py`, `scripts/build_windows_portable.ps1`, `README.md`, `docs/windows-portable-build.md`, `docs/ui-ux-changelog.md`

### Corrected the Windows zip-extraction step for Windows 11
- Summary: updated the README extraction instructions to match Windows 11 behavior by pointing testers to the File Explorer `Extract all` button or the `Show more options` menu path instead of assuming `Extract All...` appears in the first right-click menu.
- Why: a tester screenshot showed that the previous wording did not match the actual Windows context menu, which made the install guide misleading at a critical step.
- Validation: compared the updated README wording against the provided Windows screenshot and adjusted the step order to reflect what is actually visible in File Explorer.
- Files: `README.md`, `docs/ui-ux-changelog.md`

### Replaced Windows install mockups with screenshot placeholders
- Summary: removed the temporary SVG mockups from the Windows README section, replaced them with `(PLACEHOLDER FOR SCREENSHOT)`, and simplified the extracted-folder step copy.
- Why: the install guide is ready for real tester screenshots, and placeholder text is less misleading than polished mock visuals before those captures exist.
- Validation: reviewed the Windows README flow after the change to keep the step order intact while removing the interim image assets from the instructions.
- Files: `README.md`, `docs/ui-ux-changelog.md`

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
