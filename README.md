# Job Application Agent

A local-first job application workflow app for discovering, validating, reviewing, and managing executive-level job opportunities.

## Current state

- Streamlit UI
- SQLite-first storage
- Local OpenAI API key handling
- Backup and health tooling
- Pytest coverage with isolated local test state
- Legacy Google Sheets import support

## Main files

- `app.py` - main Streamlit entrypoint
- `views/` - Streamlit views
- `services/` - business logic
- `ui/` - UI components and styles
- `src/` - utility scripts
- `tests/` - test suite
- `config.py` - configuration
- `run_job_agent.command` - Mac launcher

## Local state

The app stores local state in ignored folders/files such as:

- `data/job_agent.db`
- `data/openai_api_key.txt`
- `backups/`

These should not be committed.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
