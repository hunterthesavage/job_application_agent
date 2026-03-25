# Job Application Agent

Local-first Streamlit app for discovering, validating, reviewing, and managing executive-level job opportunities.

## Status

This project is currently **experimental**.

It is usable and actively tested, but:
- The workflow is still evolving
- AI-assisted behaviors may change between releases

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


## macOS Setup

### Step 1) Install App

Open the `Terminal` app and copy and paste this whole command:

```bash
cd ~ && ( [ -d job_application_agent/.git ] || git clone https://github.com/hunterthesavage/job_application_agent.git job_application_agent ) && cd ~/job_application_agent && chmod +x install_mac.sh run_app.sh install_mac.command run_app.command && ./install_mac.sh
```

What this does:
- downloads the app into your home folder if it is not already there
- moves into the correct project folder
- fixes launcher permissions
- installs the required packages
- prepares the app to launch locally

### Step 2) Launch App 

After setup is complete, either:

- double-click `run_app.command`

or run:

```bash
cd ~/job_application_agent
./run_app.sh
```

### If `run_app.command` is blocked later

Because this app is unsigned, macOS Gatekeeper may still warn the first time you open the launcher by double-clicking it.

If that happens:
1. In Finder, `Control`-click or right-click `run_app.command`
2. Click `Open`
3. Click `Open` again in the warning dialog


## Windows Setup

### Step 1) Install App on Windows PC

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

### Step 2) Launch App on Windows PC

1. Complete `Step 1` above so the app is on your PC.
2. Make sure Python 3 is already installed.
3. Open the `job_application_agent` folder.
4. Double-click `install_windows.bat`.
5. After setup finishes, double-click `run_app_windows.bat`.

### Notes for Windows users

- The Windows launchers are included for convenience
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

## Public repo note

This repository is designed to be safe to share publicly as a local-first app.

It does **not** expect you to commit:
- your local database
- saved OpenAI API keys
- backups or logs

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
