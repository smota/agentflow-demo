# Issue #20: fix: discover Awesome lists at 100 stars without a source allowlist

**Epic:** #16

## Background & Problem Statement

V1 discovered awesome-selfhosted but a three-source review allowlist incorrectly marked it and other unreviewed repositories non-lists. Discovery, eligibility and content permissions need independent states.

## Requirements

Use broad public awesome search plus awesome/awesome-list topics with at least100 observed stars, including forks explicitly and retaining their identity. Exhaust partitioned page sets within stated GitHub limitations, retain candidate decisions, and locally generate a list-first index plus immutable detail shards. Preserve live v1 until preview promotion.

## Technical Design

Pure schema/classification/parser in awesome/lists.py; local resumable tools/lists.py. Date partitions with star tie-breaks stay below1,000results; saturated unsplittable buckets remain unresolved. Page checkpoints, stable-ID dedup, observation interval and reconciliation receipts. Batch GraphQL read-only public README observations pinned to the same commit as content history; partial errors remain per-repository pending. No repository code execution or arbitrary linked URL fetching. Immutable content-addressed detail shards validate before the index pointer switches atomically. Unknown licenses permit metadata/link-only presentation, not blanket exclusion or full-text republication. Original taxonomy preserved; normalized topics additional and derived.

## Business logic

- **BR-1 (rule):** At least100 stars, public and evidence of actual curated list;99 fails. No fixed source allowlist.
- **BR-2 (rule):** Exhaust every selected partition/page or report incomplete; pending/error is not excluded or zero.
- **BR-3 (rule):** Local processing only; preserve provenance, safe links and permissions; publish validated current candidate.
- **BR-4 (rule):** Recovery preserves completed inputs, rejects changed engine/candidate and leaves last-good publication intact.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Boundary/classifier regressions pass, including selfhosted and awesome-named non-list apps, badges, tables and directory lists.
- [ ] AC-2 (BR-2): Partition/page/tie/dedup/partial-response tests pass; live query receipts reconcile without top-N or global completeness claims.
- [ ] AC-3 (BR-3): Index/detail validate observed metrics, original taxonomy, derived topics, safe source provenance and explicit missing/permission states.
- [ ] AC-4 (BR-4): Interrupted/resumed crawl is idempotent; stale engine, missing/wrong shard and stale publication rejected; v1 tests remain green.

## Test plan

Boundary/classification/Markdown/table fixtures; fake API capped/tied/incomplete/paginated results; partial GraphQL aliases; digest/atomic publication/unknown metrics/link safety; injected interruption and exact resume. Separately record actual GitHub search/enrichment observations.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** large
- **Change surfaces:** public-catalogue, local-tooling
- **Collaboration:** architecture council for public contract; single writer, read-only advice and explicit self-review. Public metadata is not sensitive user-data migration.

## Open questions

GitHub search is not transactional: expose observation interval and reconciliation discrepancies. Unsupported content remains visible with its reason. Reproduction permissions do not determine list inclusion. Keep v1 validation independent until actual v2 migration.
