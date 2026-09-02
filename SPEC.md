# Issue #7: qa: verify publication and the complete delivery story

**Epic:** #1

## Background & Problem Statement

Completion requires both a usable public application and an honest, reproducible
execution story. Current feature slices are complete; final release acceptance remains.

## Requirements

Audit the goal matrix, run a bounded QA/operations/evidence release council, resolve
blocking findings, finish illustrated documentation and rollback instructions,
publish a release candidate then stable release, and verify public identity.

## Technical Design

Keep the validated catalogue and dependency lock unchanged. Create a tagged
1.0.0-rc.1 candidate on the feature branch after tests/review/CI; do not merge
that candidate as stable. The readiness gate returns to implementation for the
stable version/notes, reruns checks, then promotes through development to main.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Every goal matrix item maps to concrete current evidence.
- [ ] AC-2 (BR-2): Release council objections are resolved or explicitly deferred as follow-up issues.
- [ ] AC-3 (BR-3): Illustrated story and install/run/refresh/recovery/rollback instructions are accurate.
- [ ] AC-4 (BR-4): Candidate and stable releases exist; final main commit, catalogue and public app agree.
- [ ] AC-5 (BR-5): Goal issues have verified closeout; local tracked worktree is clean.

### Standard compliance

- [ ] Full workflow, unit, AppTest, catalogue and public browser checks pass.
- [ ] Simulated stakeholders and untested limitations remain explicit; no heartbeat.

## Business logic

- **BR-1 (rule):** Planned or historical checks do not establish current final acceptance.
- **BR-2 (rule):** Councils advise; standard-profile self-review stays explicit and no human gate is fabricated.
- **BR-3 (rule):** Documentation describes supported project-local commands, evidence and rollback boundaries.
- **BR-4 (rule):** Publication identity requires separate tag, release, commit and actual hosted UI checks.
- **BR-5 (rule):** Closeout follows verified publication, preserving unrelated work and all user folder constraints.

## Test plan

Full automated suite and validators; actual browser search/filter/share/source/story,
keyboard and responsive checks. Review release/tag refs, immutable catalogue digest
and public version with local server stopped. Verify clean tracked checkout.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** UI, docs, release

## Open questions

None.
