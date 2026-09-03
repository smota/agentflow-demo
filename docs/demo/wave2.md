# AwesomeAwesomeness 2.0 — delivery journal

Goal: help people discover, understand, compare and explore Awesome lists themselves.
User activated the approved plan on 2026-09-03. [Epic #16](https://github.com/smota/agentflow-demo/issues/16)
is the durable scope; this chapter extends, not rewrites, the [v1 story](story.md).

## Preserved boundaries

All project-controlled local writes stay inside the demo folder. Crawling and any
application AI processing remain local; Streamlit reads a validated published
snapshot. Free hosting, no credentials in the hosted app, no global installation,
no heartbeat. The source repositories must be public, have at least100 observed
stars, and actually be curated lists. Discovery, eligibility, enrichment and content
permissions are separate. Unknown metadata is not zero; unfinished work is visible.

## Baseline and planned increments

Baseline application v1.0.0 commit2505e38c81d29296fa649cb3ccd88fe9e575efac was clean;
72 tests passed at activation. Planned increments: latest SDLC transition; partitioned
discovery correction; early list-first public preview; taxonomy/content/contributors;
comparison/dashboard/mobile refinement; recovery/RC/stable2.0.0. Version and public
claims are recorded only after actual checks. Current app remains v1 until promotion.

## Latest SDLC, not a fictional release

The upstream latest tag is still v1.0.0. We deliberately adopted merged development
revision60a0e800dc4d4ce9476c72231a0b853998131213, [PR220](https://github.com/smota/agentflow-sdlc/pull/220),
whose six OS/Node product checks passed. `agentflow-source.json` pins this unreleased
integration revision. CLI/CI use the same exact project-local source checkout.

The newer protocol separates attempts, collector observations and accepted delivery;
it adds typed bilateral acceptance, current-candidate gates and recoverable runs.
Helpers remain read-only; councils advise the accountable owner. Simulated personas
are not humans, and same-platform contexts are not cross-platform role alternation.

## Explicit legacy retirement and fresh adoption

[Issue17](https://github.com/smota/agentflow-demo/issues/17) began with a real rejected
adoption preview: the files/merged legacy lock is unsupported. Upstream ADR006 and
the breaking-change policy explicitly require reviewed retirement and fresh adoption.
The new `--storage project` option resolves the previous outside-folder receipt conflict.

A read-only migration advisor checked335 old managed files: all matched their lock;
there were no authored or merged collisions. Retirement plan digest:
`177095e9f3f718354e663e0b416bcd9622bc9b17c12c5acf271b564627ad3e9b`.
Exact old bytes and lock were moved to ignored `.agent-runs/legacy-retirement/`:
146 obsolete files retired;171 still-needed integration-support files refreshed from
the pinned source;18 overlaps vacated for official adoption. The171 support files
are explicitly project-maintained, not claimed managed by the new profile. Application,
data, Git history and authored configuration were preserved. Root CODEX now routes to
`skills/orchestrator/SKILL.md`; old orchestration skills were retired.

Official fresh adoption used github profile, project storage and current plan token
`f1b1e6c8998d08b1221eb2a1719dfdbea9f3feccf9c7e7d13b43980f4f37fe4c`.
It created133 managed files, preserved three seeds and wrote a real v2 lock last.
Contained receipt: `.agentflow/transactions/c848f879-4e40-4718-bbe1-088d1b18a39b/receipt.json`.
Current installation, configuration authority, branch and routing checks pass.

The independent migration audit initially returned FAIL:38 managed JSON files had
Windows checkout line endings that would not survive Git/Linux normalization, and
the active runbook still pointed to v1. Both required correction. The pinned runtime
was materialized from exact Git object bytes, then the official adoption update
replaced those38 files and regenerated its own lock. No hashes were hand-edited.
The runtime verifier now compares all453 tracked source blobs with the pinned Git
tree. JSON Git attributes preserve bytes; the current runbook uses the new pin and
contained receipt path. Linux CI is a separate required proof, not inferred here.

## A real rollback defect, with a verified bounded alternative

The isolated fixture's official contained rollback CLI failed because it reads
`receipt.transactionId`, but the signed receipt contains `receiptPath` instead.
We did not alter the receipt, bypass the digest check or patch upstream. The exported
official `rollbackAdoption` API accepted the original signed receipt, checked its
target/digest/file state and restored the fixture. A second fresh fixture repeated
apply/API-rollback successfully: authored bytes exact, installation lock absent again.
This is tested adoption rollback, not application/deployment rollback.

`scripts/adoption-rollback.mjs` is a project-owned, contained-path adapter to that API.
It preserves signed receipt bytes and delegates all mutation-state checks upstream.
The CLI defect remains disclosed. Before rollback, inspect drift and the exact receipt;
never restore a real checkout over later application work.

## Tool bootstrap and verification

From the demo root, clone the source into `.tooling/agentflow-next` if absent, then
checkout the exact `agentflow-source.json` revision. Do not update an existing source
checkout with local edits. No npm install is needed for these dependency-free CLI paths.
Run `node scripts/check-framework.mjs` and the project-local Python test suite.
Managed edits fail the adoption-current check. Source checkout and transaction receipts
are ignored; lock, pin, project integration and product changes are reviewed in Git.

## Remaining delivery

At this checkpoint, discovery/UI2.0 and public release are not implemented or accepted.
The live application has not been replaced. Subsequent receipts belong to the epic and
child issue handovers; no test, deployment or recovery claim should be inferred from this plan.
