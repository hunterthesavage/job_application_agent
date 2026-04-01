# V1 Search Decision

## Short version

For V1, we should ship on **Legacy** as the search engine.

Direct-source seeding should stay **internal-only** for now.

## Why this is the decision

We tested search in three layers:

1. Raw discovery counts
2. Common-title comparisons across a top-10 title matrix
3. Fit quality checks using fake candidate profiles scored against real discovered jobs

The combined result is clear:

- **Legacy is the most dependable path right now**
- **Direct-source is not a dead end, but it is not consistent enough yet**
- **More direct-source URLs do not reliably mean better-fit jobs**

## What we learned

### 1. Legacy is still the reliable engine

Legacy is the only mode that consistently behaves like a production search path.

It is still the best choice for:

- predictable discovery behavior
- faster iteration
- fewer surprises when testing the product end to end

### 2. Direct-source can help, but not enough yet

Direct-source seeding sometimes adds lift, but the results are mixed:

- sometimes it adds a few URLs
- sometimes it adds more volume with weak relevance
- sometimes it is worse than legacy

That means it is still an experiment, not a production default.

### 3. Fit quality matters more than raw counts

The key question is not just:

- “Did direct-source find more jobs?”

The real question is:

- “Did it find jobs that score better for realistic candidate personas?”

The answer so far is usually **no**.

In the representative real-job scoring pass:

- **Business Analyst**: legacy clearly beat direct-source on fit quality
- **Product Manager**: legacy clearly beat direct-source
- **Data Analyst**: legacy slightly beat direct-source
- **Project Manager**: both were weak; direct-source was different, but not clearly better

## Recommendation for V1

### Ship

- **Legacy** as the engine
- **Broader Search** as the default visible search strategy
- **Standard** as the narrower fallback option

### Keep internal-only

- Source Layer mode selection
- Shadow registry testing
- Direct-source seeding experiments

### Do not make this a launch story yet

- Fortune 500 / direct-source seeding
- next-gen / source-layer engine language

Those are still infrastructure and R&D, not a user-facing differentiator yet.

## What we recommend next

### 1. Focus on legacy result quality

This is the highest-value next step for V1.

Examples:

- reduce weak or adjacent matches in common titles
- improve quality on sparse searches without changing the core engine
- tighten how top results are surfaced and scored

### 2. Keep using the new benchmark workflow

When we claim search improved, we should check:

- title-matrix discovery comparison
- real-job profile scoring comparison

That gives us both:

- volume signal
- fit-quality signal

### 3. Revisit direct-source only if it earns it

Direct-source should stay internal until it can show one of these clearly:

- better recall on sparse searches
- better direct-employer quality
- better fit-quality outcomes on the same benchmark set

If it cannot show that, it should stay background infrastructure.

## Bottom line

We are no longer blocked by uncertainty.

We have enough evidence to make a clean V1 choice:

- **Legacy is the engine**
- **Direct-source is experimental**
- **Next work should improve legacy quality, not promote source-layer modes**
