# Issue #21: feat: publish early list-first AwesomeAwesomeness preview

**Epic:** #16

## Background & Problem Statement

The public v1 interface indexes linked projects. Users need to discover and explore the lists themselves, using the new auditable catalogue without hosted processing.

## Requirements

Ship a polished list-first alpha: list cards/table, scope/topic/search/star filters, detail with original taxonomy and in-list search, public source access, honest metrics/coverage and shareable state. Preserve freehosting/localprocessing constraints. Publish actual2.0.0-alpha.1 only after protected CI and independent public verification.

## Technical Design

Contained codex/list-preview worktree isolates UI code from the root crawler. One agent performs one formal phase at a time; issue20 waits on its approved procedural datajob while UI phases proceed. Pure awesome/explore.py handles filter/state/share logic; awesome/list_ui.py renders native Streamlit controls and escaped editorial HTML. Main app switches only after local preview checks. Compact index and lazy digest-verified detail shards, bounded caches, no ingestion imports/network. Localpreview uses an explicitly labelled read-only snapshot under .cache, never committed as accepted data. Integrate accepted issue20 generation before alpha promotion.

## Business logic

- **BR-1 (rule):** Lists are the primary entity; filters operate over the whole observed catalogue, minimum100stars.
- **BR-2 (rule):** Preserve unknown/pending/coverage semantics, original taxonomy and exact source provenance.
- **BR-3 (rule):** Hosted UI only reads validated published files; localpreview data is labelled and never silently promoted.
- **BR-4 (rule):** Keyboard/mobile/share/reset work; alpha identity and behavior require public verification, not local inference.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Users find selfhosted and100-star lists, open profiles, search/filter/reset and paginate all results.
- [ ] AC-2 (BR-2): Metrics label unknowns and parsed scope; original taxonomy and in-list links work; coverage visible.
- [ ] AC-3 (BR-3): Offline AppTest passes without credentials/network; accepted index/shards bound to released candidate.
- [ ] AC-4 (BR-4): Mobile/keyboard/share QA passes; exact alpha tag/release/live version/digest and behavior verified with localserver stopped.

## Test plan

Pure filter/state/share tests, offline AppTest and detail cases, hostile/repeated URL inputs, browser390px/desktop screenshots and exploration; then exact protectedCI/tag/release/public deployment checks.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** large
- **Change surfaces:** public-UI, local-preview, hosting
- **Collaboration:** public-contract and UX councils; single accountable agent, explicit self-review and agent-simulated stakeholders.

## Open questions

Issue20 dataset acceptance remains a promotion dependency. UI preparation may proceed against labelled cached observations; do not infer complete classification, content metrics or contributor enrichment.
