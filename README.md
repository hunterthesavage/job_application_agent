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

## MAC OS

### Option 1: one-time install script

From the repo root:

```bash
chmod +x install_mac.sh run_app.sh install_mac.command run_app.command
./install_mac.sh
```

The install script will:
- create `.venv`
- upgrade `pip`
- install requirements
- create local data folders
- create placeholder `.gitkeep` files where helpful
- make the launcher executable

### Option 2: macOS double-click launchers

If you do not want to use Terminal commands every time:

- double-click `install_mac.command` for first-time setup
- double-click `run_app.command` after setup to start the app

The first time you open a `.command` file, macOS may ask you to confirm that you want to run it.


##  Windows PC

### Option 1: Windows launchers

For Windows users:

- run `install_windows.bat` for first-time setup
- run `run_app_windows.bat` after setup to start the app

These launchers expect Python 3 to already be installed on Windows.

### Option 2: manual install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p data backups logs
[ -f data/.gitkeep ] || touch data/.gitkeep
[ -f backups/.gitkeep ] || touch backups/.gitkeep
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
