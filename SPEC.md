# Issue #6: feat: make local refresh and delivery recovery reliable

**Epic:** #1

## Background & Problem Statement

Local refresh and unattended delivery must survive interruption without losing the
last good catalogue or duplicating external actions.

## Requirements

Resumable local refresh, atomic publication, deterministic deduplication, pinned
provenance validation and stale-candidate rejection. Fresh-context reconstruction
from durable GitHub and checkout evidence; no heartbeat.

## Technical Design

A single-writer project-local lock and checksummed run checkpoint retain discovery,
pinned revisions and completed source results. Resume validates engine/input
identity and raw hashes. Deterministic fault injection and cached published-input
replay exercise the same processing loop without changing the live snapshot.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Interrupted refresh resumes without duplicates; errors preserve last-good catalogue.
- [ ] AC-2 (BR-2): Changed candidate/input or engine identity invalidates stale acceptance/resume.
- [ ] AC-3 (BR-3): Fresh-context read-only helper reconstructs branch, issue, commit, findings and next action without conversation history.
- [ ] AC-4 (BR-4): Concurrent writers fail closed and retry/recovery boundaries are documented.

### Standard compliance

- [ ] Real versus injected interruption is identified explicitly with commands and results.
- [ ] v0.3.0 release and public version verified.

## Business logic

- **BR-1 (rule):** Partial work never replaces published data; completed source checkpoints are replay-safe.
- **BR-2 (rule):** Publication requires the exact reviewed digest; resume requires unchanged pinned input and engine identity.
- **BR-3 (rule):** GitHub workflow evidence outranks local scratch; recovery must inspect actual checkout/remote state before action.
- **BR-4 (rule):** Only one crawler writer; transient requests retry at most three times, authorization/rate limits do not blindly retry.

## Test plan

Interrupted real cached-input replay, malformed/corrupt checkpoint and raw input,
stale digest, duplicate source processing, exclusive lock and retry regressions.
Fresh-context reconstruction from GitHub and committed documents only.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** data, tooling, docs

## Open questions

None.
