# Next-Gen Source Layer

This document defines the recommended path for evolving the sourcing backend without splitting the product into a separate V1 and V2 app.

The goal is:

- keep one product
- keep one UI
- keep one repo
- evolve the source layer underneath it
- compare new and old sourcing paths safely before switching

## Core recommendation

Do not build a separate V2 app.

Do not keep two long-lived products in parallel.

Instead:

1. keep the current user-facing app intact
2. add a next-gen source layer behind the existing workflow
3. let old and new source layers coexist temporarily
4. compare them using controlled A/B or shadow runs
5. switch only after the new layer proves better

This is a migration strategy, not a rewrite.

## What stays shared

These areas should remain part of the single shared product:

- Setup Wizard
- Pipeline UI
- New Roles
- Applied Roles
- Settings
- Profile Context
- AI scoring
- AI scrub
- cover letters
- install and launch flow
- run history and operational diagnostics

This is important because most of the current launch work is product-level, not source-layer-specific.

## What changes underneath

The next-gen work should focus on the upstream sourcing substrate:

- employer registry
- hiring endpoints
- endpoint discovery
- endpoint validation
- ATS adapters
- raw job ingestion
- canonicalization and dedupe
- endpoint scoring
- crawl scheduling

The existing fit-scoring and user workflow should continue to sit downstream from this.

## Current V1 versus target next-gen layer

### Current V1

The current app is strongest at:

- user profile and fit evaluation
- operator workflow
- trusted-source weighting
- AI scoring and correction
- local-first execution

The main limitation is that discovery is still mostly search-first and run-triggered.

### Target next-gen layer

The target source layer should shift the system toward:

- employer-first discovery
- validated endpoint memory
- ATS family adapters
- raw-to-canonical job normalization
- scheduled freshness and health checks

That means:

- coverage is solved upstream
- relevance is solved downstream

## Recommended migration seam

The seam between old and new should be:

### Shared product layer

- onboarding
- settings
- scoring
- cover letters
- role review
- job workflow state

### Replaceable source layer

- URL discovery
- endpoint classification
- extraction strategy
- health tracking
- job ingestion path

This seam is the safest way to evolve without duplicating product work.

## Data model to add first

These should be introduced as additive tables, not a destructive rewrite of existing job storage.

### companies

- `company_id`
- `name`
- `canonical_domain`
- `careers_root_url`
- `industry`
- `size_band`
- `hq`
- `priority_tier`
- `exec_relevance_score`
- `active`
- `created_at`
- `updated_at`

### hiring_endpoints

- `endpoint_id`
- `company_id`
- `endpoint_url`
- `endpoint_type`
- `ats_vendor`
- `extraction_method`
- `discovery_source`
- `confidence_score`
- `health_score`
- `last_validated_at`
- `next_check_at`
- `active`
- `notes`

### endpoint_validation_runs

- `run_id`
- `endpoint_id`
- `checked_at`
- `http_status`
- `success`
- `jobs_found`
- `latency_ms`
- `parser_name`
- `parser_version`
- `failure_reason`
- `content_fingerprint`

### raw_jobs

- `raw_job_id`
- `endpoint_id`
- `source_job_key`
- `source_url`
- `title_raw`
- `location_raw`
- `description_raw`
- `posted_raw`
- `compensation_raw`
- `department_raw`
- `employment_type_raw`
- `fetched_at`
- `hash`

### canonical_jobs

- `canonical_job_id`
- `normalized_company`
- `normalized_title`
- `normalized_location`
- `canonical_url`
- `posted_at_estimated`
- `compensation_normalized_min`
- `compensation_normalized_max`
- `remote_type`
- `employment_type`
- `freshness_score`
- `source_trust_score`
- `active_status`
- `dedupe_cluster_id`
- `last_seen_at`

### canonical_job_sources

- `canonical_job_id`
- `raw_job_id`
- `source_rank`
- `is_primary`
- `match_confidence`

These tables can coexist with the current `jobs` table during migration.

## What gets reused from the current app

The following current strengths should be reused rather than replaced:

- source trust heuristics
- AI scoring prompt and fit logic
- AI scrub correction logic
- job-level workflow state
- local SQLite operating model
- research and diagnostics UI patterns

The next-gen source layer should feed these systems better inputs.

## First migration step with the highest leverage

The best first move is:

### Step 1: Employer registry plus endpoint validation

Build:

- `companies`
- `hiring_endpoints`
- `endpoint_validation_runs`
- endpoint fingerprinting rules
- endpoint validation worker

Why this first:

- no user-facing rewrite required
- gives compounding infrastructure
- improves source trust over time
- creates a real asset instead of another one-off parser

This step can start entirely behind the existing UI.

## Recommended build phases

### Phase A: Employer graph foundation

Deliverables:

- company registry
- hiring endpoint table
- validation history
- ATS fingerprint rules
- basic health scoring

User-facing impact:

- mostly Research or Status enrichment
- no major discovery change yet

### Phase B: First-class adapters

Recommended order:

1. Greenhouse
2. Ashby
3. generic JSON-LD / JobPosting
4. Workday
5. Lever

User-facing impact:

- better source quality
- more structured extraction
- fewer brittle parse failures

### Phase C: Canonicalization

Deliverables:

- raw-to-canonical job mapping
- dedupe clusters
- canonical source rank
- active versus inactive logic

User-facing impact:

- fewer duplicates
- cleaner top-of-list results

### Phase D: Scheduler

Deliverables:

- endpoint check cadence
- yield-aware refresh
- high-priority company checks

User-facing impact:

- fresher jobs
- faster query-time response
- less wasted crawl budget

## A/B testing recommendation

Yes, A/B testing is possible, and it should be done in a way that does not fork the product.

The right model is:

### One frontend

- same Setup Wizard
- same Pipeline
- same New Roles view
- same scoring and fit logic

### Two source modes underneath

- `legacy`
- `next_gen`

And optionally:

- `shadow`

## Recommended source-layer modes

### 1. Legacy mode

Use the current V1 sourcing path only.

Purpose:

- safe default
- benchmark for comparison

### 2. Shadow mode

Run the next-gen source layer in parallel, but do not show its results to the user as the primary truth.

Purpose:

- compare coverage
- compare endpoint quality
- compare duplicate rate
- compare high-fit yield
- compare latency and cost

This is the safest way to validate the backend using the V1 frontend before switching anything.

### 3. Next-gen mode

Use the next-gen source layer as the visible source of truth for selected actions.

Purpose:

- controlled rollout
- opt-in evaluation
- eventual cutover path

## Best A/B testing strategy

The safest rollout path is:

### Stage 1: Internal shadow mode only

For a run:

1. V1 sourcing produces visible results
2. next-gen sourcing runs in the background
3. compare:
   - number of valid jobs
   - top-fit yield
   - duplicate rate
   - source trust
   - latency

No frontend change required beyond diagnostics.

### Stage 2: Selectable internal compare mode

Add an operator-only control in Pipeline or Research:

- `Source Layer: Legacy / Shadow / Next-gen`

This lets you compare the same search using the same frontend.

### Stage 3: Controlled cutover

Use next-gen mode only for:

- selected adapter families
- selected companies
- selected searches

This avoids a risky all-at-once switch.

## What to measure during A/B testing

The comparison should not just be “did it find more jobs.”

Use:

- accepted jobs count
- top-20 fit quality
- duplicate count
- parse success rate
- compensation presence rate
- endpoint freshness
- source trust mix
- rediscovery quality
- user action quality:
  - cover letters generated
  - marked applied
  - kept versus removed

The real question is:

Does the next-gen source layer improve the top of the funnel, not just the volume?

## Suggested internal feature flags

These do not need to be user-facing at first.

- `source_layer_mode = legacy | shadow | next_gen`
- `next_gen_endpoint_validation_enabled = true|false`
- `next_gen_adapter_greenhouse_enabled = true|false`
- `next_gen_adapter_ashby_enabled = true|false`
- `next_gen_canonicalization_enabled = true|false`

This lets you evolve one subsystem at a time.

## Why this is better than branching the whole product

If you branch the product into V1 and V2:

- bug fixes split
- UI diverges
- onboarding diverges
- install issues duplicate
- validation becomes noisy

If you keep one product and migrate the source layer:

- fixes compound
- testing stays focused
- the frontend stays stable
- you can compare backend quality directly

That is the safer and more scalable path.

## Recommendation

Do not branch into a separate V2 product.

Do this instead:

1. keep V1 as the launchable product
2. add the next-gen source layer behind the same app
3. validate it in shadow mode first
4. expose a controlled compare mode later
5. switch piece by piece, not all at once

## Current next step

The highest-leverage architecture step is:

### Build the employer registry and endpoint validator first

That gives you:

- reusable endpoint intelligence
- a compounding source asset
- the foundation for safe A/B validation
- a real path toward better discovery without splitting the product
