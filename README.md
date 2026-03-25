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

### Step 1) Install Python in Command Prompt

Open Command Prompt and try this first:

```bat
winget install --id Python.Python.3.12 --source winget
```

Then:
1. close Command Prompt
2. open a new Command Prompt window

### Notes for Windows users

- Windows support is still more lightly tested than Mac
- if the `winget` command does not work on your PC, install Python 3 first from [python.org](https://www.python.org/downloads/windows/)
- if you install Python manually, enable `Add Python to PATH`
- the most reliable first-run path is the Command Prompt flow below
- after setup, `run_app_windows.bat` is the easiest way to reopen the app

### Step 2) Download the app in Command Prompt

In the new Command Prompt window, run these one at a time:

```bat
cd /d "%USERPROFILE%\Downloads"
```

```bat
curl -L -o job_application_agent.zip https://github.com/hunterthesavage/job_application_agent/archive/refs/heads/main.zip
```

```bat
tar -xf job_application_agent.zip
```

```bat
cd /d "%USERPROFILE%\Downloads\job_application_agent-main"
```

If you see another `job_application_agent-main` folder inside, run:

```bat
cd job_application_agent-main
```

Then confirm you are in the right place:

```bat
dir app.py
```

```bat
dir requirements.txt
```

### Step 3) Install requirements and run the app

Run these one at a time:

```bat
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python --version
python -m pip install --upgrade pip
python -m pip install pandas==3.0.1
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.headless true --server.port 8505
```

Then open:

- [http://localhost:8505](http://localhost:8505)

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
