# Acceptance evidence index

This index separates verified capability from final publication, whose immutable
receipt belongs in the [final issue](https://github.com/smota/agentflow-demo/issues/7).
Candidate/stable closeout is not inferred from historical screenshots or tests.

| Goal | Evidence |
| --- | --- |
| DATA | [Source review](source-review.md), pinned catalogue, threshold/URL/provenance/parser tests; 39 discovered candidates, 3 qualified CC0 lists, 3,037 resources. |
| APP | Unit/AppTest suite and [exploratory checks](exploratory-qa.md): search, combined source/topic, sort, pagination, reset, generated-share roundtrip and provenance. |
| UX | [UX council](ux-decisions.md), real desktop/mobile images; [release council](release-council.md) and matched-occurrence regression. |
| LOCAL | Hosted entrypoint imports only read-only modules; offline socket-denied AppTest. [Recovery](recovery-results.md) preserves lastgood and resumes without duplicates. |
| SDLC | [Epic](https://github.com/smota/agentflow-demo/issues/1), signed phase handovers, issue-scoped commits, protected PRs, releases; real review/CI returns in [story](story.md). |
| COUNCIL | Architecture (2 seats), UX (2 seats), release (3 seats); all actual fresh-context, same-platform Codex advisors with explicit simulated-persona disclosure. |
| HARNESS | Pinned stable installation versus newer-source boundary, npm fallback, capability resolution, deployment-setting guard, stale engine/candidate rejection; [story](story.md). |
| RECOVERY | [Five-field reconstruction](recovery-results.md) matched exact frozen commit without prior turns/scratch; no duplicate external mutation or second writer. |
| STORY | [Illustrated execution story](story.md), [runbook](runbook.md), license notices and linked releases. |
| PUBLIC | v0.1–v0.3 actual hosted version/digest checks; final v1.0 receipt is recorded after public smoke in issue #7 and the release. |

## Final verification contract

72 automated tests currently pass. Workflow validators and all 335 managed
framework files pass doctor; 44 installed packages are compatible. The canonical
catalogue digest remains
`6765f04bb900eaf6d868e070613d7800faf2d0bec5d5d0577a65d23dc894d5f3`.
Before stable closeout, repeat the checks on the final commit, verify tag/release
targets and hosted version, stop the local server, exercise public search, and
confirm all goal issues closed and the tracked worktree clean.

## Deliberate limits

This is selected coverage, not every qualifying Awesome list. Counts/stars are
snapshot facts, not live observations. Linked destinations are not crawled or
security-certified. No accounts, user-data persistence or AI enrichment. Free
hosting has no availability guarantee. Recovery used fault injection and cached
real inputs, not power loss; rollback is documented, not executed. No heartbeat.
