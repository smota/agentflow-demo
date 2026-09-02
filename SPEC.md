# Issue #5: feat: refine the discovery experience through UX review

**Epic:** #1

## Background & Problem Statement

The initial preview needs an editorial, accessible discovery experience rather than an undifferentiated list.

## Requirements

Search, topic/source filters, sort, pagination, shareable queries, source details, freshness and delivery-story navigation. Desktop and narrow-screen visual review by a bounded UX council.

## Technical Design

Streamlit-native controls with restrained project CSS, warm paper/ink/teal palette, resource cards, clear provenance and empty/reset states. Preserve text escaping and read-only runtime.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Search, topic/source filters and sort return correct records and usable reset/empty states.
- [ ] AC-2 (BR-2): Query parameters preserve searches and source selection across a new browser session; invalid parameters are safe.
- [ ] AC-3 (BR-3): Desktop and narrow layouts expose results and keyboard-usable controls without horizontal overflow.
- [ ] AC-4 (BR-4): Source detail and story views expose provenance, limits and verified delivery evidence.

### Standard compliance

- [ ] UX council findings have explicit dispositions and screenshots.
- [ ] v0.2.0 release/deployment version verified.

## Business logic

- **BR-1 (rule):** Discovery combines literal search, topic and source filters with explicit sort and pagination.
- **BR-2 (rule):** Shareable URLs encode only validated public search state, never secrets or personal data.
- **BR-3 (rule):** Layout must remain usable on desktop and narrow screens, with accessible labels and visible focus.
- **BR-4 (rule):** Source and delivery evidence must be accessible without implying endorsement or live crawling.

## Test plan

AppTest filters, sorting, pagination, reset, query parameters and source pages. Browser keyboard and narrow layout exploration, visual inspection and regression tests for findings.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** UI, docs

## Open questions

None.
