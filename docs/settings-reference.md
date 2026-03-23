# Job Application Agent — Settings Reference

## Purpose
This document explains the app settings currently stored in SQLite, what they control, where they are surfaced, and where they are consumed in the current product.

The main source of truth for settings persistence is `services/settings.py`, which loads defaults from `DEFAULT_SETTINGS` and stores values in the `app_settings` table.

## How settings work

### Persistence model
- Settings are stored in the SQLite `app_settings` table.
- `services/settings.py` starts from a `DEFAULT_SETTINGS` dictionary and overlays database values.
- `save_settings()` performs upsert-style writes by key.

### Main access patterns
Settings are most commonly used through:
- `load_settings()` for reading the full current settings set
- `save_settings()` for writing updates

### Important note about defaults
Some settings are true user-facing defaults, while others are internal or system-managed metadata.

## Settings by category

---

## 1. Search and discovery settings
These settings directly affect discovery behavior, filtering, and first-run configuration.

### `target_titles`
**Purpose**
Comma-separated role targets used to shape discovery and matching.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Search Criteria
- Pipeline → Run Inputs

**Where it is used**
- Discovery query generation
- URL title prefiltering
- title match scoring
- blank-location title override logic

**Examples**
- `VP Technology, CIO, Head of Platform`
- `CTO, Chief Information Officer`

---

### `preferred_locations`
**Purpose**
Primary location preferences used for discovery and match gating.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Search Criteria
- Pipeline → Run Inputs

**Where it is used**
- location parsing
- location filter evaluation
- remote vs location match scoring
- hard reject behavior for non-matching locations

**Format**
Usually one location per line in the UI.

**Examples**
- `Dallas, TX`
- `Miami, FL`
- `London, UK`

---

### `include_keywords`
**Purpose**
Optional positive keywords that boost fit or help shape search behavior.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Search Criteria
- Pipeline → Run Inputs

**Where it is used**
- include keyword scoring
- OpenAI title suggestion context during setup
- discovery intent shaping where applicable

**Examples**
- `AI, transformation, enterprise software`

---

### `exclude_keywords`
**Purpose**
Optional negative keywords that heavily penalize or exclude roles.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Search Criteria
- Pipeline → Run Inputs

**Where it is used**
- exclude keyword penalty during match scoring

**Examples**
- `contract, consultant, intern`

---

### `remote_only`
**Purpose**
Controls whether the search and scoring logic should prefer or require remote-friendly roles.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Search Criteria
- Pipeline → Run Inputs
- influences default filter state in New Roles

**Where it is used**
- location filter evaluation
- remote preference scoring
- location hard reject logic
- default on-screen filtering behavior for new roles

**Stored values**
- `true`
- `false`

---

### `minimum_compensation`
**Purpose**
Stores a user-entered minimum compensation threshold for future or partial filtering use.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Search Criteria

**Where it is used currently**
- captured and persisted during setup
- not currently presented as a primary live Pipeline run control

**Status**
Partially active, but not yet a major live control in the current Pipeline UI.

---

## 2. Page behavior defaults
These settings affect how data is presented in the UI.

### `default_min_fit_score`
**Purpose**
Default fit-score threshold for filtering roles in the UI.

**User-facing**
Yes.

**Where it appears**
- Settings → Configuration → Page Defaults

**Where it is used**
- initialization of on-screen filter state in New Roles
- configuration defaults applied into session state

**Common values**
- `Any`
- `60`
- `70`
- `75`
- `80`
- `85`
- `90`

---

### `default_jobs_per_page`
**Purpose**
Default pagination size for role views.

**User-facing**
Yes.

**Where it appears**
- Settings → Configuration → Page Defaults

**Where it is used**
- default page size initialization for New Roles
- default page size initialization for Applied Roles
- configuration defaults applied into session state

**Common values**
- `5`
- `10`
- `20`
- `500`

---

### `default_new_roles_sort`
**Purpose**
Default sort mode for the New Roles page.

**User-facing**
Yes.

**Where it appears**
- Settings → Configuration → Page Defaults

**Where it is used**
- initialization of New Roles sort state

**Common values**
- `Newest First`
- `Highest Fit Score`
- `Highest Compensation`
- `Highest Source Trust`
- `Company A-Z`

---

## 3. Cover letter output settings
These settings affect local cover letter output behavior.

### `cover_letter_output_folder`
**Purpose**
Local folder path where generated cover letters should be saved.

**User-facing**
Yes.

**Where it appears**
- Settings → Configuration → Cover Letter Output

**Where it is used**
- cover letter generation output path logic
- folder picker and saved output behavior

**Notes**
- local machine path
- intentionally machine-specific

---

### `cover_letter_filename_pattern`
**Purpose**
Filename template for generated cover letters.

**User-facing**
Yes.

**Where it appears**
- Settings → Configuration → Cover Letter Output

**Where it is used**
- cover letter filename generation logic

**Supported placeholders currently described in UI**
- `{company}`
- `{title}`
- `{date}`

**Example**
- `CL_{company}.txt`

---

## 4. Profile context settings
These settings improve AI-assisted content generation.

### `resume_text`
**Purpose**
Resume body text stored locally for stronger cover letter generation and contextual prompting.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Profile Context
- Settings → Profile Context

**Where it is used**
- OpenAI title suggestion context during setup
- cover letter and AI-assisted content generation flows

---

### `profile_summary`
**Purpose**
Short executive summary or leadership bio used for AI context.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Profile Context
- Settings → Profile Context

**Where it is used**
- OpenAI title suggestion context during setup
- AI-assisted content framing

**Alias support**
- legacy alias: `executive_summary`

---

### `strengths_to_highlight`
**Purpose**
Specific strengths or differentiators the user wants reflected in generated content.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Profile Context
- Settings → Profile Context

**Where it is used**
- cover letter and AI-assisted content generation flows

**Examples**
- `AI transformation`
- `enterprise IT leadership`
- `ServiceNow`

---

### `cover_letter_voice`
**Purpose**
Tone guidance for generated cover letters.

**User-facing**
Yes.

**Where it appears**
- Setup Wizard → Profile Context
- Settings → Profile Context

**Where it is used**
- cover letter generation style and framing

**Examples**
- `Confident, concise, executive`
- `Warm, strategic, direct`

---

## 5. OpenAI validation metadata
These settings are system-managed and not primary user inputs.

### `openai_api_key_validated`
**Purpose**
Stores whether the saved OpenAI key has been validated.

**User-facing**
Indirectly.

**Where it appears**
- used as internal metadata for OpenAI key state

**Where it is used**
- key validation state and UI signaling

---

### `openai_api_key_last_validated_at`
**Purpose**
Timestamp for the last successful OpenAI key validation.

**User-facing**
Mostly internal.

**Where it appears**
- internal metadata

**Where it is used**
- OpenAI key validation state tracking

---

### `openai_api_key_validated_hash`
**Purpose**
Stores a hash associated with the validated key state.

**User-facing**
No.

**Where it appears**
- internal metadata only

**Where it is used**
- validation state management

---

## 6. Legacy or compatibility behavior

### Key aliases
The current settings layer supports a small alias map:
- `executive_summary` → `profile_summary`
- `default_minimum_fit_score` → `default_min_fit_score`

This helps preserve compatibility with earlier iterations.

### Ignored legacy setting
The loader explicitly ignores:
- `require_mark_as_applied`

This indicates older app behavior or earlier design assumptions that are no longer active.

---

## Settings by screen

### Setup Wizard
Uses or writes:
- `target_titles`
- `preferred_locations`
- `include_keywords`
- `exclude_keywords`
- `remote_only`
- `minimum_compensation`
- `resume_text`
- `profile_summary`
- `strengths_to_highlight`
- `cover_letter_voice`
- setup completion and dismissal flags stored separately in settings writes

### Pipeline
Uses or writes:
- `target_titles`
- `preferred_locations`
- `include_keywords`
- `exclude_keywords`
- `remote_only`

### Settings → Configuration
Uses or writes:
- `cover_letter_output_folder`
- `cover_letter_filename_pattern`
- `default_min_fit_score`
- `default_jobs_per_page`
- `default_new_roles_sort`

### Settings → Profile Context
Uses or writes:
- `resume_text`
- `profile_summary`
- `strengths_to_highlight`
- `cover_letter_voice`

### New Roles
Reads:
- `default_min_fit_score`
- `default_jobs_per_page`
- `default_new_roles_sort`
- `remote_only`

---

## Recommendations for future cleanup
1. Separate user-facing settings from internal metadata in docs and possibly in code.
2. Decide whether `minimum_compensation` should become a true live Pipeline control or remain setup-only.
3. Consider adding a `settings-category` or `settings schema` layer for stronger validation.
4. Document any additional settings-like values currently living only in Streamlit session state.
5. Keep aliases minimal and remove dead compatibility paths when safe.

## Suggested rule for future changes
Whenever a new setting is added, update three places together:
1. `DEFAULT_SETTINGS` in `services/settings.py`
2. the relevant UI surface where the user edits it
3. this settings reference document
