# Job Application Agent — Architecture

## Overview
Job Application Agent is a local-first Streamlit application built around a view layer, a service layer, and a SQLite persistence layer.

The architecture is intentionally simple:
- Streamlit provides the application shell and interaction model
- service modules provide orchestration, storage, matching, ingestion, and operational logic
- SQLite stores app state, job data, and run history
- shell scripts provide the local install and launch path

## High-level architecture

```text
User
  ↓
Streamlit UI
  ↓
Views
  ↓
Services
  ↓
SQLite + local filesystem
```

## Main entrypoint

### `app.py`
Responsibilities:
- configure Streamlit page state
- initialize local storage once
- inject shared UI styling
- render hero and top navigation
- decide whether to show Setup Wizard
- route into top-level views

Top-level views:
- `views/new_roles.py`
- `views/applied_roles.py`
- `views/pipeline.py`
- `views/settings.py`
- `views/setup_wizard.py`

## Storage and persistence layer

### `config.py`
Defines application constants and filesystem locations, including:
- project root
- data directory
- logs directory
- backups directory
- database path
- OpenAI key file path
- manual URL file path
- storage backend constant

### `services/db.py`
Responsibilities:
- ensure data directory exists
- open SQLite connection
- enforce row factory and pragmas
- create schema
- seed initial schema migration

SQLite characteristics currently used:
- foreign keys enabled
- WAL mode
- synchronous = NORMAL

### `services/storage.py`
Responsibilities:
- initialize local storage
- initialize database
- ensure ingestion tables exist
- return database path

## Primary persistent entities

### `app_settings`
Stores user-configurable application state such as:
- target titles
- preferred locations
- include keywords
- exclude keywords
- remote only toggle
- profile and resume context
- cover letter output settings
- OpenAI validation metadata

### `jobs`
Primary job record store.
Current schema includes fields for:
- company and title
- normalized title and role family
- location and remote markers
- job posting URL and company careers URL
- ATS type and requisition identifiers
- compensation and validation fields
- fit scoring and match rationale
- workflow status and applied date
- duplicate key and active status
- cover letter path
- created and updated timestamps

### `removed_jobs`
Stores removed or excluded jobs by duplicate key and metadata.

### `import_runs`
Legacy import-run history table.

### `cover_letter_artifacts`
Tracks generated cover letter outputs.

### `ingestion_runs`
Stores ingestion run summaries, counts, timestamps, status, and details JSON.

### `ingestion_run_items`
Stores per-item run results within each ingestion run.

### `source_registry`
Stores known source roots and operational metadata including:
- source key
- source root
- hostname
- ATS type
- source type
- source trust
- source name and source detail
- example job URL
- seen count and matching job count
- first seen, last seen, and last success timestamps

## View layer

### `views/setup_wizard.py`
Purpose:
Guide first-time setup and transition the user into the actual pipeline.

Current wizard flow:
1. Welcome
2. OpenAI API
3. Profile Context
4. Search Criteria
5. AI Review

Key responsibilities:
- initialize wizard session state
- save settings progressively
- optionally save local OpenAI key
- request AI title suggestions
- trigger first pipeline run by queueing `discover_and_ingest`

### `views/pipeline.py`
Purpose:
Act as the operating console for search and ingestion.

Key responsibilities:
- render run inputs
- render search summary and fallback search links
- queue user-triggered pipeline actions
- execute pending actions through a prepare → execute pattern
- render last result, recent runs, source registry, and last run monitor

Current pipeline actions:
- `discover_and_ingest`
- `discover_only`
- `ingest_saved`
- `ingest_pasted`
- `rescore_existing_jobs`

### Other main views
- `views/new_roles.py` renders review workflow for newly found roles
- `views/applied_roles.py` renders applied-role tracking workflow
- `views/settings.py` renders configuration, health, backup, and reset tooling

## Service layer

### `services/settings.py`
Purpose:
Load and save app settings from SQLite.

Characteristics:
- starts from `DEFAULT_SETTINGS`
- normalizes aliases
- persists updates through upsert into `app_settings`

### `services/status.py`
Purpose:
Return system-level summary information for the UI.

Examples of surfaced status:
- total jobs
- new jobs
- applied jobs
- removed jobs
- latest cover letter artifact
- latest import
- latest backup
- OpenAI key state

### `services/ui_busy.py`
Purpose:
Provide simple app-level busy-state and pending-action helpers via Streamlit session state.

Pattern used:
- queue action in `prepare` phase
- move action into `execute` phase
- execute action during render cycle
- clear action and stop busy state when done

This pattern is currently central to how Pipeline and Setup Wizard trigger work.

### `services/pipeline_runtime.py`
Purpose:
Main orchestration layer for discovery, validation, scoring, enrichment, and ingestion.

Key responsibilities:
- build search preview
- discover job links
- load and ingest saved URLs
- ingest pasted URLs
- discover and ingest in one flow
- normalize and parse settings inputs
- gate probable job URLs
- apply cheap title prefilter from URL shape
- score matches against current settings
- enrich accepted payloads
- dedupe accepted items within a run

Key decision points in runtime:
- URL quality gate
- title prefilter
- fit score threshold
- location hard reject behavior
- batch dedupe preference
- run cap via `MAX_URLS_PER_RUN`

## OpenAI by user action

This app now uses OpenAI in a few distinct places. The important distinction is that some UI actions always call OpenAI, while others only call OpenAI as one optional part of a larger flow.

### Buttons that always call OpenAI

#### `New Roles` → `✍ Cover Letter`
Primary OpenAI behavior:
- calls `services.cover_letters.generate_cover_letter_for_job_id`
- builds a prompt from:
  - Settings → Profile Context
  - current job data from SQLite
  - saved cover letter voice
- sends one OpenAI `responses.create(...)` request
- writes the generated cover letter to the local filesystem
- records the output in `cover_letter_artifacts`

This is a direct AI generation action.

#### `Pipeline` → `Rescore Existing Jobs`
Primary OpenAI behavior for each selected job:
- loads the current scoring profile, preferring Settings → Profile Context
- calls `services.ai_job_scoring.score_accepted_job`
- applies requirement-based scoring into:
  - `fit_score`
  - `fit_tier`
  - `ai_priority`
  - `match_rationale`
  - `risk_flags`
  - `application_angle`
- then calls `services.ai_job_scrub.scrub_accepted_job`
- writes the updated scoring fields back into `jobs`

This is a direct AI maintenance action and can make many OpenAI calls in one batch.

### Buttons that may call OpenAI as part of a larger flow

#### `Pipeline` → `Find and Add Jobs`
Potential OpenAI behavior:
- discovery can use AI title expansion to broaden the search title list conservatively
- after jobs are accepted by heuristics, each accepted job can go through:
  - AI job scoring
  - AI scrub or validation

Non-AI work in the same flow:
- URL discovery
- URL filtering
- ATS parsing
- heuristic qualification
- source trust enrichment
- SQLite ingestion

So this button is a mixed pipeline action, not a pure AI action.

#### `Pipeline` → `Find Job Links Only`
Potential OpenAI behavior:
- discovery can use AI title expansion to broaden discovery queries

What it does not do:
- no job scoring
- no AI scrub
- no ingestion of jobs into SQLite

This is the lightest Pipeline action that can still touch OpenAI.

#### `Pipeline` → `Add Saved Job Links`
Potential OpenAI behavior:
- parses saved URLs into job records
- for accepted jobs, runs:
  - AI job scoring
  - AI scrub or validation

What it does not do:
- no discovery step
- no AI title expansion

This button is an ingest and evaluate action, not a discovery action.

#### `Pipeline` → `Add Pasted Job Links`
Potential OpenAI behavior:
- same AI path as `Add Saved Job Links`
- for accepted jobs, runs:
  - AI job scoring
  - AI scrub or validation

What it does not do:
- no discovery step
- no AI title expansion

### Buttons that do not call OpenAI

Examples:
- `Apply`
- `Mark as Applied`
- `Remove Job`
- `Save Run Inputs`
- most filter and sort controls

These are local UI or SQLite workflow actions only.

### `services/ingestion.py`
Purpose:
Handle ingestion bookkeeping and run persistence.

Key responsibilities:
- ensure ingestion tables exist
- start and finish ingestion runs
- log per-item results
- upsert jobs via `services.job_store`
- maintain source registry
- compute source yield summaries
- detect source dominance
- return recent runs and source registry summaries

## Discovery path

### Discovery inputs
The discovery system is driven by saved search criteria such as:
- target titles
- preferred locations
- include keywords
- exclude keywords
- remote only

### Discovery outputs
Discovery returns job URLs and metadata about providers and queries.

### Current ingest path
For each URL:
1. run URL quality gate
2. run cheap title prefilter
3. create job record from URL
4. compute match score
5. decide accept vs skip
6. enrich payload with source metadata
7. dedupe within run
8. ingest accepted payload

## Filesystem dependencies

### Local runtime folders
- `data/`
- `backups/`
- `logs/`
- `.streamlit/`

### Important local-only files
- `data/job_agent.db`
- `data/openai_api_key.txt`
- `job_urls.txt`
- `data/manual_urls.txt`

## Packaging model

### `install_mac.sh`
Responsibilities:
- verify Python 3 exists
- create `.venv`
- activate virtualenv
- upgrade pip
- install requirements
- create local folders
- write `.streamlit/config.toml` when needed
- make launcher executable

### `run_app.sh`
Responsibilities:
- activate `.venv`
- ensure local runtime folders exist
- launch `streamlit run app.py`

## Current architecture strengths
- clear top-level app shell
- SQLite-first local persistence
- explicit operator console in Pipeline
- better first-run path through Setup Wizard
- meaningful operational telemetry through ingestion runs and source registry
- mostly sensible separation between views and services

## Current architecture risks

### 1. Orchestration is distributed
System behavior currently depends on a mix of:
- Streamlit session state
- view-level control flow
- service orchestration
- persisted settings

This is manageable now but should be documented carefully and simplified over time.

### 2. Contracts are implicit
Some important contracts are real but not yet documented, including:
- pipeline action lifecycle
- what counts as a valid run input
- what result shapes views expect from service calls
- what state transitions are allowed for jobs and runs

### 3. Product logic and operational logic are close together
The current design is practical, but some UX flow, action management, and runtime orchestration remain tightly coupled.

## Recommended next architecture improvements
1. Document pipeline action contracts explicitly
2. Document settings and where each is consumed
3. Define canonical run states and transitions
4. Separate AI-triggering concerns more clearly from view rendering
5. Continue shrinking legacy paths and optional dependencies
6. Add a more formal testing map for critical workflows

## Suggested mental model for future changes
Before changing any behavior, answer these five questions:
1. Which view starts this action?
2. Which service owns the business logic?
3. Which tables or files change?
4. Which session-state keys are involved?
5. What is the user-visible success or failure state?
