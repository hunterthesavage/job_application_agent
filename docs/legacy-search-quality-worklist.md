# Legacy Search Quality Worklist

## Goal

Improve the quality of what users actually see in V1 without changing the decision that **Legacy is the engine**.

This worklist is ordered by expected V1 payoff, not by technical novelty.

## Priority 1: Surface the best jobs first

### What to improve

- Make sure the default review order emphasizes fit, not recency.
- Reduce the chance that obviously better-fit jobs are buried below merely newer ones.

### Why it matters

We already have evidence that some searches produce useful jobs, but the user experience is still heavily shaped by what appears first in `New Roles`.

If strong-fit jobs are present but not surfaced first, the search experience still feels weaker than it really is.

### Fastest move

- Default new review queues to **Highest Fit Score** instead of **Newest First**

## Priority 2: Reduce weak adjacent matches for common titles

### What to improve

- Tighten how generic searches such as `Project Manager`, `Business Analyst`, and `Data Analyst` accept or surface adjacent-but-wrong roles.
- Focus on niche domain or specialty variants that technically overlap but are weak fits for a broad title search.

### Why it matters

The title-matrix and real-job scoring runs show that some weak matches still pass because they share broad title language but are not actually strong generic matches.

### Likely leverage points

- qualifier title-overlap rules
- keyword handling for broad searches
- downstream fit-based ordering

## Priority 3: Clean up extraction metadata that hurts trust

### What to improve

- Fix generic or placeholder metadata such as `page_title`
- Keep company/title parsing clean enough that users trust the cards they see

### Why it matters

Bad metadata does not always break acceptance, but it lowers confidence and makes good results look sloppy or suspicious.

### Fastest move

- reject generic company placeholders when a better fallback company is available

## Priority 4: Improve sparse-search behavior without changing engines

### What to improve

- Keep improving low-result legacy searches such as executive remote tech titles
- Focus on better recall and better acceptance only inside the legacy path

### Why it matters

This is still the main quality gap for the searches closest to your own use case.

### Constraint

- do not promote direct-source for this
- use it only as an internal benchmark and research lane

## Priority 5: Keep benchmarking instead of tuning by feel

### What to keep using

- title-matrix runner
- fake-profile calibration pack
- real-job profile scoring bridge

### Why it matters

These now give us three useful views of quality:

- discovery volume
- raw result shape
- persona-fit quality

## Recommended next execution order

1. Fit-first default review order
2. Generic-title adjacent-match reduction
3. Metadata cleanup
4. Sparse legacy search improvements
5. Re-run benchmarks after each meaningful change
