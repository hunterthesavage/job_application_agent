# Job Application Agent

Local-first Streamlit app for discovering, validating, reviewing, and managing executive-level job opportunities.

## Status

This project is currently **experimental**.

It is usable and actively tested, but:
- the workflow is still evolving
- AI-assisted behaviors may change between releases
- legacy Google Sheets tooling is optional and not part of the main local-first setup path

## Version

Current release: **1.0.0**

## What it does

- Setup Wizard for first-time onboarding
- Pipeline view for run inputs and job discovery actions
- New Roles review workflow with sorting and filtering
- Applied Roles tracking
- SQLite-first local storage
- Local OpenAI key handling
- Backup, health, and reset tooling
- Optional legacy Google Sheets import support

## Repo structure

- `app.py` - main Streamlit entrypoint
- `views/` - Streamlit views
- `services/` - business logic
- `ui/` - shared UI helpers
- `src/` - utility scripts
- `tests/` - test suite
- `config.py` - shared config and paths

## Local-only state

These files and folders are local runtime state and should not be committed:

- `data/job_agent.db`
- `data/openai_api_key.txt`
- `data/openai_api_key.meta.json`
- `data/openai_api_state.json`
- `backups/`
- `logs/`
- `.env`
- `service_account.json`

## Mac Setup

### Step 1: Get the app onto your Mac

Choose one of these options.

#### Option A: Download the ZIP file

1. Open the GitHub page for this project.
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Open the downloaded ZIP file.
5. Open the unzipped `job_application_agent` folder.

#### Option B: Clone it with Terminal

1. Open the `Terminal` app.
2. Copy and paste this block:

```bash
cd ~
git clone https://github.com/hunterthesavage/job_application_agent.git
cd job_application_agent
```

### Easiest option

1. Complete `Step 1` above so the app is on your Mac.
2. Open the `job_application_agent` folder.
3. Double-click `install_mac.command`.
4. After setup finishes, double-click `run_app.command`.

What this does:
- creates the app's private Python environment
- installs the required packages
- starts the app locally on your Mac

### If macOS blocks `install_mac.command`

Because this app is unsigned, macOS Gatekeeper may show a warning the first time.

If that happens:
1. In Finder, `Control`-click or right-click `install_mac.command`
2. Click `Open`
3. Click `Open` again in the warning dialog

After that first approval, you should be able to use the launcher normally.

### Terminal option for Mac

If you prefer Terminal, make sure you are **inside the project folder** before running install commands.

Copy and paste this whole block:

```bash
chmod +x install_mac.sh run_app.sh install_mac.command run_app.command
./install_mac.sh
```

Important:
- `Step 1` must already be completed
- `cd job_application_agent` is required if you used Terminal to download the app
- if you stay in `~` instead of the project folder, the install files will not be found

### Launch later on Mac

After setup is complete:

- double-click `run_app.command`

Or from Terminal:

```bash
cd ~/job_application_agent
source .venv/bin/activate
./run_app.sh
```

## Windows Setup

### Step 1: Get the app onto your Windows PC

Choose one of these options.

#### Option A: Download the ZIP file

1. Open the GitHub page for this project.
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Open the downloaded ZIP file.
5. Open the unzipped `job_application_agent` folder.

#### Option B: Clone it with Terminal

1. Open Command Prompt or PowerShell.
2. Copy and paste this block:

```bat
cd %USERPROFILE%
git clone https://github.com/hunterthesavage/job_application_agent.git
cd job_application_agent
```

### Easiest option

1. Complete `Step 1` above so the app is on your PC.
2. Make sure Python 3 is already installed.
3. Open the `job_application_agent` folder.
4. Double-click `install_windows.bat`.
5. After setup finishes, double-click `run_app_windows.bat`.

### Notes for Windows users

- the Windows launchers are included for convenience
- Windows support is still more lightly tested than Mac
- if Python 3 is missing, install it first from [python.org](https://www.python.org/downloads/windows/)

### Terminal option for Windows

If you prefer a terminal install, open Command Prompt or PowerShell, move into the project folder, and run:

```bat
cd %USERPROFILE%\job_application_agent
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
run_app_windows.bat
```



## First launch

On first launch, the app should open to the Setup Wizard when there are no jobs and setup has not been completed.

## Public repo note

This repository is designed to be safe to share publicly as a local-first app.

It does **not** expect you to commit:
- your local database
- saved OpenAI API keys
- backups or logs
- `service_account.json`

Legacy Google Sheets support is optional. If you do not use that path, you can ignore `service_account.json` and the related import scripts.

## Release Candidate Validation

For a soft-launch checkpoint, run the release checks:

```bash
source .venv/bin/activate
./scripts/run_release_checks.sh
```

Use the full checklist in:

- `docs/soft-launch-checklist.md`

## Clean reset

Use:
- **Settings → Configuration → Reset App / Remove All Data**

That resets local app state and returns the app to Setup Wizard.

## Troubleshooting

### App launches but crashes with a SQLite column error

That usually means the local database is older than the current code. Because the app is local-first, the simplest fix is to remove the local runtime DB and let the app recreate it:

```bash
rm -f data/job_agent.db jobs.db
```

Then relaunch:

```bash
./run_app.sh
```

### Streamlit command not found

Make sure the virtual environment is active or use the launcher:

```bash
./run_app.sh
```

### Fresh install proof

A clean GitHub clone test is the best way to validate install behavior before sharing the repo more broadly.
