# Source Layer Contract

## Purpose

This document defines the integration contract between:

1. the **producer** repo  
   Fortune 500 career endpoint registry and validator

2. the **consumer** repo  
   Job Application Agent

The goal is to let the producer export validated employer endpoint intelligence that the consumer can safely import and use for source-layer experiments, shadow runs, and future next-gen discovery.

This contract exists so both repos can evolve without guessing about field names, allowed values, or compatibility rules.

## Integration model

This is a **file-based contract**.

The producer exports a validated employer endpoint dataset.
The consumer imports that dataset into its own local database.

This is intentionally:

- loosely coupled
- versioned
- easy to debug
- safe for staged rollout

## Contract version

Current schema version:

`1.0`

If any breaking change is made to:

- field names
- required fields
- status values
- top-level structure

then the schema version must be incremented.

## Producer responsibilities

The producer repo is responsible for:

1. validating and normalizing employer career endpoints
2. exporting data that matches this contract
3. including `schema_version`
4. keeping status values within the allowed enum sets
5. avoiding silent breaking changes

## Consumer responsibilities

The consumer repo is responsible for:

1. validating `schema_version`
2. rejecting or warning on invalid payloads
3. importing only fields and statuses supported by this contract
4. not assuming producer-only internal fields exist unless listed here

## Export format

Recommended primary format:

- JSON

Recommended filename:

- `validated_employer_endpoints.json`

Optional secondary format:

- CSV export for human review

## Top-level JSON shape

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-03-25T12:00:00Z",
  "source_repo": "fortune-500-career-pages",
  "records": []
}
```

## Record schema

Each record represents one validated or reviewable employer hiring endpoint.

Example:

```json
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
```

## Required fields

These fields must be present in every record:

1. `company_name`
2. `canonical_company_domain`
3. `careers_url`
4. `careers_url_status`
5. `review_status`
6. `ats_provider`
7. `confidence_score`
8. `last_validated_at`

## Optional fields

These fields are allowed but not required:

1. `jobs_feed_url`
2. `discovery_method`
3. `source_url`
4. `confidence_reason`
5. `is_primary_careers_url`
6. `fortune_rank`
7. `review_notes`
8. `notes`

## Field definitions

### `company_name`

Human-readable company name.

### `canonical_company_domain`

Best-known canonical employer domain, lowercased if possible.

Example:

`xapo.com`

### `careers_url`

Employer careers URL or ATS board URL that should act as the primary endpoint.

### `careers_url_status`

Machine validation status for the endpoint.

Allowed values:

- `validated`
- `candidate`
- `blocked`
- `not_found`
- `unresolved`

### `review_status`

Human review status for the row.

Allowed values:

- `approved`
- `needs_review`
- `rejected`
- `unreviewed`

### `ats_provider`

Detected ATS family or endpoint type.

Examples:

- `greenhouse`
- `ashby`
- `lever`
- `workday`
- `smartrecruiters`
- `icims`
- `custom`
- `unknown`

### `jobs_feed_url`

Optional structured feed or jobs API endpoint if known.

### `confidence_score`

Float between `0` and `1`.

### `discovery_method`

Short text describing how the endpoint was found.

Examples:

- `validated_probe`
- `manual_override`
- `search_assist`
- `candidate_resolution`

### `source_url`

Original page or source that led to the final careers URL.

### `confidence_reason`

Short explanation of why the endpoint received its score or status.

### `last_validated_at`

ISO-8601 UTC timestamp for latest successful validation attempt.

### `is_primary_careers_url`

Boolean indicating whether this should be treated as the company’s primary current careers endpoint.

### `fortune_rank`

Optional integer rank if the source universe is Fortune 500-based.

### `review_notes`

Optional human-review notes.

### `notes`

Optional general notes.

## Import guidance for consumer

The consumer may apply stricter import rules than the producer export.

Recommended initial import rule:

- import only rows where:
  - `careers_url` is present
  - `careers_url_status` is `validated` or `candidate`

Recommended trust preference:

- prefer `review_status = approved`
- allow `needs_review` or `unreviewed` only in looser or shadow modes
- exclude `rejected`

## Compatibility rules

### Non-breaking changes

These are allowed under the same schema version:

1. adding new optional fields
2. exporting more records
3. refining confidence logic without changing field meaning

### Breaking changes

These require a schema version bump:

1. renaming existing fields
2. removing required fields
3. changing allowed enum values incompatibly
4. changing top-level JSON structure

## Consumer source-layer modes

The consumer repo may use this data under different modes:

### `legacy`

Ignore imported source-layer records for visible discovery.

### `shadow`

Use imported records only for comparison, diagnostics, or silent background evaluation.

### `next_gen`

Allow imported records to influence live discovery.

The producer does not need to know which mode the consumer is using.

## Ownership

Producer repo owns:

- endpoint discovery
- endpoint validation
- ATS detection for exported records
- export generation

Consumer repo owns:

- import behavior
- source-layer mode behavior
- user-visible ranking and scoring
- shadow versus live usage of imported records

## Recommended next step

1. commit this contract into both repos
2. implement export to this contract in the producer repo
3. implement import from this contract in the consumer repo
4. begin with `shadow` mode only
