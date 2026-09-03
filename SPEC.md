# Issue #23: feat: add list comparison dashboards and responsive exploration

**Epic:** #16

## Background & Problem Statement

The list-profile snapshot is complete, but users still have to inspect lists one at a
time. They need an honest overview of the catalogue and an easy way to compare a small
set of lists without inventing time series or loading thousands of detail shards.

## Requirements

Add a first-class insights dashboard with population-labelled KPIs, topic and freshness
distributions, stars-versus-indexed-content analysis and ranked list access. Let users
compare two to four eligible lists across observed stars, forks, entries, categories,
contributors and freshness. Keep controls keyboard accessible, responsive, URL-shareable
and bounded for Streamlit Community Cloud. Derive everything from the loaded index only.

## Business logic

- **BR-1 (rule):** Dashboard denominators and unknown counts are explicit; no historical trend is inferred.
- **BR-2 (rule):** Comparison accepts at most four current eligible lists and preserves metric units/observation meaning.
- **BR-3 (rule):** Dashboard filters and comparison selections normalize safely, survive share/reopen and reset predictably.
- **BR-4 (rule):** Aggregate rendering uses the index only; detail shards remain lazy and no hosted network/AI processing is added.
- **BR-5 (rule):** Desktop and 390px mobile layouts retain readable labels, keyboard access, contrast and bounded chart density.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): KPIs and topic/freshness charts show their population, known/unknown coverage and observation date.
- [ ] AC-2 (BR-2): Two-to-four-list comparison renders an accessible equivalent table plus bounded metric charts.
- [ ] AC-3 (BR-3): Dashboard filters, comparisons, reset and shared URLs round-trip with malformed/extreme input tests.
- [ ] AC-4 (BR-4): AppTest proves dashboard/profile navigation is offline and benchmark evidence fits free hosting.
- [ ] AC-5 (BR-5): Browser acceptance passes desktop and 390px mobile without horizontal overflow or hidden controls.

## Test plan

Pure aggregation/filter/normalization tests; AppTest for dashboard, comparison, empty and reset/share states; complete
suite and source-bound Agentflow observation; measured index/load/render memory and time; fresh local browser desktop/mobile
checks followed by exact hosted acceptance after protected promotion.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** public UI, URL state, index analytics, tests, release/story documentation
- **Collaboration:** chief-designer/UX, data-honesty and performance advisory council; single accountable executor.

## Open questions

None. Alpha.2 remains the last-good public rollback until this increment passes hosted acceptance.
