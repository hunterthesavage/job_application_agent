# Job Application Agent

A local-first job application workflow app for discovering, validating, reviewing, and managing executive-level job opportunities.

This project is currently designed as a Streamlit-based local application with SQLite as the primary data store. Google Sheets remains available only for legacy import and compatibility workflows.

## Current state

The app currently supports:

- Streamlit UI
- SQLite-first storage model
- Local OpenAI API key handling
- Backup and health tooling
- Basic pytest coverage with isolated local test state
- Legacy Google Sheets import support

## Architecture

Top-level structure:

- `app.py` - main Streamlit entrypoint
- `views/` - Streamlit page/view modules
- `services/` - business logic and local services
- `ui/` - UI components and styling helpers
- `src/` - utility scripts and support workflows
- `tests/` - test suite
- `run_job_agent.command` - Mac launcher
- `run_agent.py` - Python launcher/helper
- `config.py` - project configuration

## Storage model

This app is local-first.

Primary local state includes:

- SQLite database in `data/job_agent.db`
- OpenAI API key file in `data/openai_api_key.txt`
- local backups in `backups/`

These files are intentionally ignored from Git and should not be committed.

## Important safety notes

This repo is configured to avoid committing local user data, secrets, logs, and generated runtime artifacts.

Tests are designed to use temporary paths for:

- SQLite database files
- backup directories
- OpenAI key test state

Tests should not mutate real local user data when run from the project virtual environment.

## Requirements

- Python 3.11+ recommended
- macOS or another environment that can run Streamlit and SQLite locally

## Setup

Clone the repo:

```bash
git clone https://github.com/YOUR_USERNAME/job_application_agent.git
cd job_application_agent
