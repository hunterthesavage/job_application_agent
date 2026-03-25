# Next-Gen Source Layer — Phase 1

This document defines the first implementation slice for the next-gen source layer.

The goal of Phase 1 is to create the employer-registry foundation inside `job_agent` without changing the visible V1 user experience.

This phase is intentionally narrow:

- additive data model only
- no UI rewrite
- no discovery cutover
- safe comparison path through `shadow` mode

## Phase 1 Objective

Introduce a new source-layer foundation that can:

1. import validated employer endpoints from the Fortune 500 careers project
2. store them in additive SQLite tables
3. support `legacy`, `shadow`, and `next_gen` source-layer modes
4. run `shadow` comparisons without affecting visible results

The visible product remains V1.

## What Phase 1 Includes

### New imported source asset

Import a validated endpoint export from the Fortune 500 careers repo.

Expected file:

- `validated_employer_endpoints.json`

Suggested local location:

- `data/imports/validated_employer_endpoints.json`

### New additive tables

Add:

- `companies`
- `hiring_endpoints`
- `endpoint_validation_runs`
- `source_layer_runs`

These should coexist with the current `jobs`, `ingestion_runs`, and related V1 tables.

### New internal mode control

Add:

- `source_layer_mode`

Allowed values:

- `legacy`
- `shadow`
- `next_gen`

Default:

- `legacy`

### Shadow comparison path

When `source_layer_mode = shadow`:

1. run the current V1 discovery path normally
2. run the next-gen source selection logic in the background
3. store or print comparison output only
4. do not change the visible job results

## What Phase 1 Does Not Include

This phase does **not**:

- replace current discovery
- replace current scoring
- introduce canonical jobs
- change `New Roles`
- change `Applied Roles`
- expose next-gen results as primary user-facing truth
- create a separate V2 app

## Repo Relationship

This phase assumes two repos:

### Upstream repo

Fortune 500 careers project:

- validates employer career endpoints
- detects ATS families
- maintains reviewable company-endpoint intelligence

### Downstream repo

`job_agent`:

- imports validated endpoints
- uses them for source intelligence
- keeps the user-facing product stable

The coupling should be data-contract-first, not runtime-package-first.

## Export Contract

Phase 1 expects the Fortune 500 repo to export records shaped roughly like:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-03-25T12:00:00Z",
  "source_repo": "fortune-500-career-pages",
  "records": [
    {
      "company_name": "Xapo Bank",
      "canonical_company_domain": "xapo.com",
      "careers_url": "https://job-boards.greenhouse.io/xapo61",
      "careers_url_status": "validated",
      "review_status": "approved",
      "ats_provider": "greenhouse",
      "jobs_feed_url": null,
      "confidence_score": 0.94,
      "discovery_method": "validated_probe",
      "source_url": "https://xapo.com/careers",
      "confidence_reason": "Greenhouse board detected and validated",
      "last_validated_at": "2026-03-25T11:54:00Z",
      "is_primary_careers_url": true,
      "fortune_rank": 412,
      "review_notes": "Confirmed by manual review",
      "notes": "Primary careers endpoint"
    }
  ]
}
```

### Minimum required fields

- `company_name`
- `canonical_company_domain`
- `careers_url`
- `careers_url_status`
- `review_status`
- `ats_provider`
- `confidence_score`
- `last_validated_at`

### Expected status values

`careers_url_status`

- `validated`
- `candidate`
- `blocked`
- `not_found`
- `unresolved`

`review_status`

- `approved`
- `needs_review`
- `rejected`
- `unreviewed`

## Proposed Files in `job_agent`

### New files

- `services/company_registry.py`
- `services/source_layer.py`
- `services/source_layer_import.py`
- `services/source_layer_shadow.py`
- `tests/test_source_layer_import.py`
- `tests/test_source_layer_modes.py`

### Likely touched files

- `services/db.py`
- `services/pipeline_runtime.py`
- `services/settings.py`
- `views/pipeline.py`
- `docs/next-gen-source-layer.md`

## Proposed SQLite Tables

### `companies`

```sql
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    canonical_domain TEXT,
    industry TEXT,
    size_band TEXT,
    hq TEXT,
    priority_tier TEXT,
    exec_relevance_score REAL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### `hiring_endpoints`

```sql
CREATE TABLE IF NOT EXISTS hiring_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    endpoint_url TEXT NOT NULL,
    endpoint_type TEXT NOT NULL,
    ats_vendor TEXT,
    extraction_method TEXT,
    discovery_source TEXT NOT NULL,
    confidence_score REAL DEFAULT 0,
    health_score REAL DEFAULT 0,
    review_status TEXT,
    careers_url_status TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    last_validated_at TEXT,
    next_check_at TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, endpoint_url),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);
```

### `endpoint_validation_runs`

```sql
CREATE TABLE IF NOT EXISTS endpoint_validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id INTEGER NOT NULL,
    checked_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    jobs_found INTEGER,
    latency_ms INTEGER,
    parser_name TEXT,
    parser_version TEXT,
    failure_reason TEXT,
    content_fingerprint TEXT,
    source_payload_json TEXT,
    FOREIGN KEY(endpoint_id) REFERENCES hiring_endpoints(id)
);
```

### `source_layer_runs`

```sql
CREATE TABLE IF NOT EXISTS source_layer_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT NOT NULL,
    import_file_path TEXT,
    imported_records INTEGER DEFAULT 0,
    selected_endpoints INTEGER DEFAULT 0,
    discovered_urls INTEGER DEFAULT 0,
    accepted_jobs INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    notes TEXT
);
```

## Import Mapping

The first import should map exported records into:

### `companies`

- `name` <- `company_name`
- `canonical_domain` <- `canonical_company_domain`
- `active` <- `1`
- `created_at` / `updated_at` <- import timestamp

### `hiring_endpoints`

- `company_id` <- matched company row
- `endpoint_url` <- `careers_url`
- `endpoint_type` <- `careers_page`
- `ats_vendor` <- `ats_provider`
- `extraction_method` <- derived from `ats_provider`
- `discovery_source` <- `fortune500_registry_import`
- `confidence_score` <- `confidence_score`
- `health_score` <- initial copy of `confidence_score`
- `review_status` <- `review_status`
- `careers_url_status` <- `careers_url_status`
- `is_primary` <- `is_primary_careers_url`
- `last_validated_at` <- `last_validated_at`
- `active` <- derived from import policy
- `notes` <- merged from confidence and review notes

## First-Pass Import Policy

For Phase 1, import only rows where:

- `careers_url` is present
- `careers_url_status` is `validated` or `candidate`

Set `active = 1` for:

- `review_status` in `approved`, `needs_review`, `unreviewed`

Set `active = 0` for:

- `review_status = rejected`

This keeps the import useful without making Phase 1 depend on perfect human review coverage.

## New Services

### `services/source_layer_import.py`

Main function:

```python
def import_employer_endpoints(file_path: str | Path) -> dict:
    ...
```

Responsibilities:

1. load JSON
2. validate schema version
3. validate required fields
4. normalize rows
5. upsert companies
6. upsert hiring endpoints
7. return summary:
   - imported
   - updated
   - skipped
   - invalid

### `services/source_layer.py`

Main functions:

```python
def get_source_layer_mode() -> str:
    ...

def set_source_layer_mode(value: str) -> None:
    ...

def load_candidate_endpoints(limit: int | None = None) -> list[dict]:
    ...
```

Responsibilities:

- hold the current source-layer mode
- expose active imported endpoints
- centralize mode validation

### `services/source_layer_shadow.py`

Main function:

```python
def run_shadow_endpoint_selection(settings: dict[str, str]) -> dict:
    ...
```

Responsibilities:

1. select likely relevant endpoints for the current user search
2. summarize how many usable endpoints exist
3. estimate which ATS families are available
4. produce comparison output only

Phase 1 shadow mode should not alter visible results.

## Mode Semantics

### `legacy`

- current V1 discovery only
- imported endpoints may exist in the DB but are not used in live sourcing

### `shadow`

- current V1 discovery remains the visible truth
- next-gen endpoint selection runs in the background
- write comparison output only

### `next_gen`

- reserved for internal testing only in Phase 1
- may later use imported endpoints as extra seeds
- should remain hidden from normal users for now

## Pipeline Integration

Phase 1 integration point:

- `services/pipeline_runtime.py`

Recommended behavior:

1. read `source_layer_mode`
2. if `legacy`
   - run current discovery path only
3. if `shadow`
   - run current discovery path
   - run shadow endpoint analysis
   - append comparison notes to run output
4. if `next_gen`
   - keep gated and internal-only
   - do not fully replace discovery yet

## UI Exposure

Phase 1 should not expose next-gen controls broadly.

Recommended first approach:

- hidden internal-only control
- or local environment flag
- or a hidden advanced section in `Pipeline -> Research`

Default user experience should remain:

- `legacy`

## Success Metrics

Phase 1 is successful if:

1. the import runs cleanly without duplicate explosion
2. companies and endpoints are stored correctly
3. `shadow` mode produces stable comparison output
4. visible discovery behavior does not regress
5. the imported registry becomes useful as a trusted source asset

## Test Plan

### Import tests

- valid file imports expected records
- invalid records are skipped safely
- repeated import updates existing rows cleanly

### Mode tests

- `legacy` leaves current behavior unchanged
- `shadow` writes comparison output
- `next_gen` remains gated and does not accidentally become default

### Pipeline regression tests

- current discovery behavior still passes in `legacy`
- current scoring path is unchanged

## Recommended Build Order

1. add table DDL
2. add import service
3. add source-layer mode setting
4. add shadow summary service
5. wire shadow output into pipeline logs
6. add optional hidden internal control

## Non-Goals for Phase 1

Do not add yet:

- canonical jobs
- endpoint scheduler
- full ATS adapter layer
- user-facing result switching
- new frontend pages dedicated to next-gen mode

These belong to later phases after the source registry foundation is proven.

## Recommendation

Phase 1 should be implemented behind the current product, not beside it.

The product remains V1.

The new source layer starts as:

- imported registry
- internal source intelligence
- shadow comparison only

This is the safest way to learn from the Fortune 500 careers project without creating a second app or a long-lived branch split.
