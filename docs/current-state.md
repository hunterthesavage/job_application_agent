# Job Application Agent — Current State

## Purpose
Job Application Agent is a local-first Streamlit app for discovering, validating, reviewing, and managing executive-level job opportunities.

The current product is designed around a single-user workflow on a local machine, with SQLite as the primary system of record and optional OpenAI support for title suggestions and cover-letter-related workflows.

## Current release
- Version: `1.0.0`

## What is working now

### Core app shell
- Streamlit app entrypoint in `app.py`
- Main top navigation:
  - New Roles
  - Applied Roles
  - Pipeline
  - Settings
- First-run routing into Setup Wizard when the app has not been completed or dismissed and no jobs exist yet

### Setup Wizard
The current setup wizard is the canonical first-run onboarding experience.

Current steps:
1. Welcome
2. OpenAI API
3. Profile Context
4. Search Criteria
5. AI Review

The wizard saves settings progressively and can trigger the first real pipeline run by queueing a `discover_and_ingest` action.

### Pipeline
The Pipeline view is the operator console for the app.

Current capabilities:
- Edit and save run inputs
- Find and Add Jobs
- Find Job Links Only
- Add Saved Job Links
- Add Pasted Job Links
- Rescore Existing Jobs
- View search summary
- View generated search queries
- View fallback Google search links
- View source registry summary
- View recent job runs
- View last run monitor

### Discovery and ingest runtime
Current pipeline flow:
1. Build search plan and queries
2. Discover job URLs
3. Apply URL quality gate
4. Apply cheap URL title prefilter
5. Build job record from job URL
6. Score role against current settings
7. Enrich payload with source trust metadata
8. Dedupe accepted items within the run
9. Ingest accepted jobs into SQLite
10. Persist run history and source registry updates

### OpenAI-backed actions in the current UI
Current user-visible actions that can call OpenAI:
- `✍ Cover Letter`
- `Find and Add Jobs`
- `Find Job Links Only`
- `Add Saved Job Links`
- `Add Pasted Job Links`
- `Rescore Existing Jobs`

Important distinction:
- `Cover Letter` and `Rescore Existing Jobs` are direct OpenAI actions
- the Pipeline run buttons are mixed flows where OpenAI is only one part of the overall process

Current OpenAI usage in those flows:
- title expansion during discovery
- requirement-based AI job scoring for accepted jobs
- AI scrub or validation pass after scoring
- cover letter generation from Profile Context plus job data

### Local storage
The app is currently SQLite-first.

Primary persistent entities include:
- `app_settings`
- `jobs`
- `removed_jobs`
- `import_runs`
- `cover_letter_artifacts`
- `ingestion_runs`
- `ingestion_run_items`
- `source_registry`

### Local-only runtime state
These are expected to remain local and not be committed:
- `data/job_agent.db`
- `data/openai_api_key.txt`
- `data/openai_api_key.meta.json`
- `data/openai_api_state.json`
- `backups/`
- `logs/`
- `.env`

### Packaging and launch
Current install and launch path is optimized for macOS.

Install:
- `./install_mac.sh`

Run:
- `./run_app.sh`

The install flow currently:
- creates `.venv`
- upgrades `pip`
- installs `requirements.txt`
- creates local folders
- writes `.streamlit/config.toml` if missing
- makes the launcher executable

## Product model
The current product model is:
- local-first
- single-user
- portfolio-grade but functional
- optimized for iterative use by the builder
- optionally shareable with friendly testers

This is not yet intended to be a hosted multi-user product.

## Key implementation decisions already made
- SQLite is the primary backend
- Local state is preferred over cloud dependency for core workflows
- Setup Wizard and Pipeline are now aligned
- Search criteria are saved into app settings and reused across discovery actions
- Source registry and source trust are first-class operational concepts
- Job ingestion captures run history and not just final records

## What is strong right now
- The app has a clear top-level product shape
- The setup flow maps to the actual operating flow
- Pipeline actions are explicit and user-triggered
- Discovery and ingest have meaningful quality gates
- Local persistence is durable and inspectable
- Source monitoring exists, which gives the app a real operational layer
- Install and launch are simple enough for macOS testers

## What is still rough or incomplete

### Repo clarity
The repo explains what the app does, but it still needs stronger internal docs for:
- architecture boundaries
- settings reference
- action contracts
- release hardening steps

### Orchestration boundaries
The system currently spreads orchestration across:
- Streamlit session state
- view code
- runtime services
- settings persistence

This is workable, but it is one of the next scaling constraints.

### Public shareability
The repo is now shareable with trusted testers, but still feels more builder-friendly than stranger-friendly.

### Dependency and packaging cleanup
Some dependencies and legacy paths still reflect the app’s earlier evolution. The current codebase should continue to be reviewed for:
- optional vs required dependencies
- cross-platform setup expectations

## Highest-priority next steps
1. Add repo documentation for current state, architecture, and settings
2. Formalize pipeline action contracts
3. Improve install confidence for clean-clone testing
4. Tighten busy-state and run-state behavior
5. Clarify where OpenAI logic belongs in the architecture
6. Continue improving discovery quality and explainability

## Current recommendation for working style
Use the repo for code truth and use Canvas for:
- feature briefs
- architecture notes
- bug investigations
- release checklists
- UX acceptance criteria

Before any meaningful code change, define:
1. What is changing
2. Why it is changing
3. What files are in scope
4. What could break
5. How it will be tested
