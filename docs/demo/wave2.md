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

The tooling increment merged as [PR19](https://github.com/smota/agentflow-demo/pull/19),
development commit `d8bf85107011c3734bdf4b18262f32416854b590`. All required Linux
checks passed, independently confirming the exact-byte adoption/CI bootstrap.
Issue17 closed through the actual integration lifecycle; the public app stayed v1.

[Issue20](https://github.com/smota/agentflow-demo/issues/20) now implements the
list-first ingestion contract. Its architecture council added finite dense-partition
handling, per-alias partial-response states, pinned identity and index-last publication.
The initial98-test suite caught path-identity and topic-label bugs. A separate audit
then found privacy/identity race boundaries, an incomplete engine fingerprint and
incidental-phrase misclassification. All four were corrected with regressions;
105tests passed and the bounded correction audit passed. This is not yet acceptance
of live data or the UI.

A live search run deliberately stopped after two durable pages and resumed against
the same engine. Later safety fixes changed that engine. Its still-running search-only
process was explicitly identified and stopped; the confirmed-dead writer lock was
archived inside the demo. A new run `lists-20260903-b` starts under the corrected engine.
The old checkpoint is retained as historical evidence, not relabelled as current or
resumed by editing its fingerprint. No README enrichment or public replacement had
occurred in the old run.

## Recovery from a real parser edge case

Run B completed discovery with 8,373 distinct candidates: 39 partition records,
18 split and 21 reconciled, none queued or unresolved. At 1,146 completed content
observations it encountered `gege-circle/.github`. The repository name is valid;
our alphanumeric-first parser restriction was not. Regression tests now cover
leading punctuation and reject traversal, and parser rejection stays per-repository.

Rather than rewrite an engine fingerprint, a new explicit replay operation checks
the old checkpoint's exact digest and discovery scope, verifies each available raw
input, and reparses under a fresh engine. The old checkpoint remains unchanged.
An advisory review also caught equal-length text/blob mismatches; pinned Git blob
integrity is checked before source bytes are accepted. Run C exercised replay;
run D superseded it after the integrity refinement and continues enrichment.
119 tests pass at this code checkpoint. See the [durable recovery report](https://github.com/smota/agentflow-demo/issues/20#issuecomment-5522920082).

A contained UI worktree now provides a labelled, unaccepted local list-first
preview. Five offline tests cover filters, pagination, original categories, in-list
search, share links and ambiguous parameters. The browser shows selfhosted with
1,300 parsed entries and 86 categories. Content freshness and contributors remain
unknown until their dedicated observation step, not guessed from repository pushes.

Discovery code and preview code are implemented but live data/phase acceptance and
public 2.0 release remain pending. The public v1 application has not been replaced.
