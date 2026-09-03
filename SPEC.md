# Issue #24: chore: verify recovery and publish AwesomeAwesomeness 2.0

**Epic:** #16

## Background & Problem Statement

The catalogue, list profiles and insights dashboard are live as prereleases, but the
2.0 release is not complete until its delivery can survive interruption, be resumed
from durable evidence by a fresh executor and be promoted from an exact publicly
accepted candidate. The final story must distinguish observed behavior from claims and
must not treat local scratch state, a passing check or a tag as deployment proof.

## Requirements

Exercise the latest installed Agentflow GitHub-backed run contract against this issue.
Demonstrate a fenced writer handoff after a recorded interruption, idempotent external
publication and fail-closed stale evidence. Reconstruct the next safe action in a fresh
Codex process using only repository and durable GitHub evidence. Publish and validate a
2.0.0 release candidate, cold-start the hosted app, then promote the exact accepted
content to stable 2.0.0 through protected branches. Extend the illustrated SDLC story
and operator runbook with real evidence, limitations and recovery instructions.

## Business logic

- **BR-1 (rule):** Durable GitHub run state, product Git history and public deployment are separate evidence domains; local `.agent-runs/` files remain disposable scratch.
- **BR-2 (rule):** Recovery changes writer identity and generation only through a digest-confirmed plan; obsolete writers, changed preconditions and unresolved operations fail closed.
- **BR-3 (rule):** Repeating an authorized external projection reconciles its operation and never creates a duplicate issue comment.
- **BR-4 (rule):** A fresh executor can name the exact issue, branch/candidate identity, current gate, findings and next safe action without conversation history or unpublished code.
- **BR-5 (rule):** RC and stable acceptance separately resolve commit, checks, tag, GitHub release and cold hosted behavior with local Streamlit ports stopped.
- **BR-6 (rule):** The final story uses real screenshots and auditable phase, council, review/rework, harness and recovery evidence; simulated review is never represented as independent or human review.
- **BR-7 (rule):** Stable promotion contains the same accepted application/data tree as the RC except reviewed version and release-story metadata, and leaves the scoped checkout clean.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): A GitHub-backed Agentflow run for issue #24 is readable after local scratch evidence is hidden, with source and product identities reported separately.
- [ ] AC-2 (BR-2): An interruption/checkpoint/pause/resume exercise transfers to a replacement writer generation; the old writer and a stale recovery plan are rejected and the last-good public app remains available.
- [ ] AC-3 (BR-3): Two publication attempts resolve to one durable workflow-status comment, with operation reconciliation recorded.
- [ ] AC-4 (BR-4): A transcript-free fresh Codex process reconstructs the exact current state and next safe action from committed policy plus GitHub evidence, and its report is checked against an expected manifest.
- [ ] AC-5 (BR-5): Full tests, recovery negatives, desktop/mobile browser acceptance and exact remote reconciliation pass for RC and stable with ports 8501/8502 stopped.
- [ ] AC-6 (BR-6): The illustrated story and runbook link actual screenshots, failed/reworked paths, advisory councils, harness events, test evidence and limitations.
- [ ] AC-7 (BR-7): Protected PRs, exact tags/releases and final public footer agree on 2.0.0; repository status is clean and secret/copyright/attribution scans pass.

## Test plan

Use the installed run CLI for GitHub source planning, start, context, checkpoint,
pause, digest-confirmed resume and idempotent publish. Add a deterministic project
harness that verifies the recorded recovery transcript, duplicate-write count, stale
generation/plan rejection and fresh-context manifest. Run the complete Python and
workflow suites, catalogue validation, secret/copyright/attribution scans, local
desktop/mobile exploratory acceptance, protected GitHub checks and cold public
desktop/mobile acceptance. Resolve commit, check, tag, release and deployment evidence
independently for RC and stable.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** Agentflow delivery configuration, recovery evidence harness, tests, release metadata, SDLC story/runbook and public deployment
- **Collaboration:** recovery/integrity, release/operations and documentation/UX advisory council; single accountable executor; simulated review disclosed as self-review

## Open questions

None. v2.0.0-alpha.3 is the last-good public rollback until the release candidate passes cold hosted acceptance.
