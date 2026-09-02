# Issue #4: feat: publish a real-data searchable preview

**Epic:** #1

## Background & Problem Statement

Awesome resources are scattered across huge lists. Readers need one searchable, attributed catalogue, and deployment viability must be established early.

## Requirements

Discover public Awesome resource-list repositories with at least 50,000 observed stars. Locally parse a licensed initial subset into a static catalogue. Publish a basic working search app on free Streamlit Cloud.

## Technical Design

Architecture council compares static JSON, SQLite and hosted crawling. Prefer a small static catalogue, deterministic local Markdown parser and Streamlit UI. Record source query, observed stars, revision and license. Freeze runtime dependencies; CI runs pytest and AppTest.

## Business logic

- **BR-1 (rule):** Only independently discovered public Awesome lists with at least 50,000 observed stars contribute resources.
- **BR-2 (rule):** Extraction runs locally and output preserves source provenance; hosted app reads only the committed snapshot.
- **BR-3 (rule):** Case-insensitive search returns matching resources and source links.
- **BR-4 (error):** Unsafe links and malformed source content must not execute or enter the published catalogue.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Discovery manifest records query, timestamps, stars and inclusion/exclusion decisions; every included source passes threshold.
- [ ] AC-2 (BR-2): Catalogue contains real extracted resources and source revision/license provenance; app runs without crawler credentials.
- [ ] AC-3 (BR-3): Search and no-result paths pass AppTest and browser smoke.
- [ ] AC-4 (BR-4): Parser and URL-negative tests pass; untrusted text is escaped.

### Standard compliance

- [ ] Architecture council objections resolved and role evidence published.
- [ ] v0.1.0 release and actual public deployment verified.

## Test plan

Unit tests for URL/Markdown parsing and threshold. Catalogue validation. AppTest search/empty state. Local and hosted browser smoke. Inspect release identity separately from CI.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** UI, data, infra

Public read-only catalogue: no user data, auth, billing or sensitive database migration. Stakeholder simulation is advisory, not real human approval.

## Open questions

None.
