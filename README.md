# Job Application Agent

Local-first Streamlit app for discovering, validating, reviewing, and managing executive-level job opportunities.

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
- Legacy Google Sheets import support

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

## Quick install on macOS

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

### macOS double-click launchers

If you do not want to use Terminal commands every time:

- double-click `install_mac.command` for first-time setup
- double-click `run_app.command` after setup to start the app

The first time you open a `.command` file, macOS may ask you to confirm that you want to run it.

### Windows launchers

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

## Fresh install for a new Mac user

Use these steps if you are starting from scratch and are not already familiar with Terminal commands.

### Step 1: Open Terminal

On Mac, open the `Terminal` app.

### Step 2: Go to your home folder

This command moves you to your user home folder:

```bash
cd ~
```

### Step 3: Download the app from GitHub

This command makes a local copy of the project on your Mac:

```bash
git clone https://github.com/hunterthesavage/job_application_agent.git
cd job_application_agent
```

After this, you should be inside the project folder.

### Step 4: Create the app's private Python environment

This creates a local Python environment just for this app, so it does not interfere with other Python tools on your Mac:

```bash
python3 -m venv .venv
```

### Step 5: Turn that environment on

This tells Terminal to use the app's private Python environment:

```bash
source .venv/bin/activate
```

When this works, you should usually see `(.venv)` at the start of the Terminal prompt.

### Step 6: Install what the app needs

These commands update the Python installer tools and then install the app's required packages:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 7: Start the app

This launches the Streamlit app locally on your Mac:

```bash
streamlit run app.py --server.headless true --server.port 8505
```

### Step 8: Open the app in your browser

Go to:

- [http://localhost:8505](http://localhost:8505)

### Step 9: Complete the first-run setup

Suggested first run:

1. On the `OpenAI API` step, enter a valid API key if you want AI features enabled.
2. On `Profile Context`, click `Use Starter Template`.
3. On `Search Criteria`, try:
   - title: `VP of Technology`
   - location: `Dallas`
4. Finish the wizard and run the first search.

Expected behavior:

- If jobs are found, the app should take you to `New Roles`.
- If no jobs are found, the app should keep you in `Pipeline`.

### Step 10: Stop the app when you are done

Go back to the Terminal window running the app and press:

- `Ctrl+C`

### Faster option for Mac users

After cloning the repo, you can also use the double-click launchers:

1. double-click `install_mac.command` for first-time setup
2. double-click `run_app.command` to start the app later

## Run the app

From the repo root:

```bash
./run_app.sh
```

Or manually:

```bash
source .venv/bin/activate
streamlit run app.py
```

## First launch

On first launch, the app should open to the Setup Wizard when there are no jobs and setup has not been completed.

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
