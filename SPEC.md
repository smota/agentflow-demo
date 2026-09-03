# Issue #17: chore: transition demo to current Agentflow delivery contracts

**Epic:** #16

## Background & Problem Statement

The legacy Agentflow installation must be explicitly retired before supported fresh adoption of the current merged delivery revision.

## Requirements

Preserve the application, history and project ownership. Pin upstream60a0e800dc4d4ce9476c72231a0b853998131213; use current roles, skills and validation, project-contained receipts and no global/outside-folder writes.

## Technical Design

Reviewed digest177095e9f3f718354e663e0b416bcd9622bc9b17c12c5acf271b564627ad3e9b covers335 pristine managed files:171 refreshed project-support files,146 retired obsolete files,18 retired overlaps for fresh133-file github-profile adoption. Archive exact prior bytes and lock in ignored project-local storage. Official adopt plan/apply writes the v2 lock and contained receipt. Replace CI/adapter entrypoints deliberately. Verify installation and fixture rollback separately.

## Business logic

- **BR-1 (rule):** Preserve application/data/history and authored configuration; no fabricated ownership or bypassed guards.
- **BR-2 (rule):** Bind fresh adoption to its current preview and store receipts in the demo folder.
- **BR-3 (rule):** Latest means the verified merged source revision, not a new published release claim.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Hashed retirement inventory and recoverable original bytes match; application regressions pass.
- [ ] AC-2 (BR-2): Official fresh adoption and contained receipt verified, no current conflicts, rollback exercised in a fixture.
- [ ] AC-3 (BR-3): Current role/skill/configuration/CI entrypoints and source identity are documented and validated.

## Test plan

Ownership inventory, official adoption preview/apply/verify, contained fixture rollback, configuration/workflow checks,72 baseline app tests and independent migration audit.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** tooling, docs

## Open questions

None: supported explicit retirement/fresh adoption confirmed in upstream breaking-change policy and migration council. Actual acceptance waits for validation.
