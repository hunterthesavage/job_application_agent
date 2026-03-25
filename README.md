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

### Notes for Windows users

- Windows support is still more lightly tested than Mac
- for now, use **Python x64**, not **Python ARM64**
- the most reliable first-run path is the Command Prompt flow below
- after setup, `run_app_windows.bat` is the easiest way to reopen the app

### Step 1) Install Python x64

Open Command Prompt and run:

```bat
cd /d "%USERPROFILE%\Downloads"
```

```bat
curl -L -o python-3.13.12-amd64.exe https://www.python.org/ftp/python/3.13.12/python-3.13.12-amd64.exe
```

```bat
start /wait python-3.13.12-amd64.exe
```

In the installer:
1. check `Add Python to PATH`
2. use the default install options

Then:
1. close Command Prompt
2. open a new Command Prompt window

### Step 2) Download the app in Command Prompt

Download the latest app ZIP:

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

### Step 3) Confirm you are in the right folder

You should be in the folder that contains both `app.py` and `requirements.txt`.

```bat
dir app.py
```

```bat
dir requirements.txt
```

### Step 4) Create the virtual environment

Run:

```bat
py -3 -m venv .venv
```

### Step 5) Activate the virtual environment

Run:

```bat
call .venv\Scripts\activate.bat
```

### Step 6) Confirm the active Python

Run:

```bat
python --version
```

### Step 7) Upgrade pip

Run:

```bat
python -m pip install --upgrade pip
```

### Step 8) Install requirements

Run:

```bat
python -m pip install -r requirements.txt
```

### Step 9) Launch the app

Run:

```bat
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
