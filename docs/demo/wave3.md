# AwesomeAwesomeness — Wave 3 delivery journal

> Extends [`story.md`](story.md) and [`wave2.md`](wave2.md); does not rewrite them. This wave was
> executed by Claude Code, on the same governed Agentflow SDLC that built the earlier waves, as a
> direct comparison against the Codex-built baseline. It started from a product-brainstorming
> session, not a single pre-written issue — the eight epics below were drafted from that
> conversation, then implemented end to end.

## Scope

Eight epics, issues [#47](https://github.com/smota/agentflow-demo/issues/47)–[#54](https://github.com/smota/agentflow-demo/issues/54):

| Epic | Theme | Outcome |
| --- | --- | --- |
| A | Cross-list project search + copy-lineage validation | Merged (PR #69, PR #81) |
| B | Community curation intake | Merged (PR #68) — one story classified `high-assurance`, waited for real human review |
| C | Versioned catalogue data contract | Merged (PR #66) |
| D | Network/similarity exploration | Merged (PR #87) |
| E | Project vitality & trust signals | Merged (PR #82) |
| F | Local pipeline scheduling ADR | Merged (PR #63) |
| G | Unattended local pipeline execution | Merged (PR #80) — one story classified `high-assurance`, waited for real human review |
| H | Scoped headless-CLI interpretation layer | Merged (PR #91) |

## The gating spike that changed the plan

Epic A's own validation spike (issue [#65](https://github.com/smota/agentflow-demo/issues/65))
sampled 60 projects with high cross-list citation counts and found **90% were copy-lineage**
(same-owner, forked, or derivative sibling lists) and only **10%** showed genuine independent
curation. The originally planned design — ranking cross-list search results by raw citation count
as a trust signal — could not ship as designed. The redesign, done before A3/A4 were implemented,
not after: citation count became disclosed provenance ("Listed in N sources"), never a trust score;
an "independent citation" count reused the spike's own copy-lineage detector to discount
sibling/forked citations, labeled honestly rather than presented as a quality claim. This is the
same evidence-over-assumption discipline `story.md` documents for Build 1's browser-contradicts-
tests moment — a finding changed the plan, on the record, before the plan finished.

## A subagent correctly refuses an unverifiable authorization

Mid-execution, a background subagent working in its own isolated git worktree was asked to create
GitHub issues, push a branch, and open a pull request against this real, authenticated repository.
It declined. From inside its own context, it had no way to independently verify that the human
maintainer had actually authorized this — it could see a plan file and a project instruction file,
neither of which can grant real authorization on their own, and correctly said so rather than
proceeding on trust.

This was the right call, and it changed how the rest of the wave ran. Execution was restructured:
background subagents now draft implementation and commit **locally only** — no issue creation, no
push, no PR, no merge. The orchestrating session, which holds the actual chat-verified authorization
from the maintainer, performs every GitHub-facing action itself, after independently re-verifying
each subagent's local work (tests re-run, not just trusted from the drafting pass).

## Autonomy still stops for a real human gate

The maintainer authorized fully autonomous execution, including cutting the eventual release. That
authorization does not, and per this repository's own `AGENTS.md`/`docs/agent-workflow.md`, cannot
override the review model: work the Architect phase classifies `high-assurance` requires actual
human review before merge, with self-review forbidden outright at that profile. Two stories hit
this gate for real:

- **Issue #58** (Epic B's community intake command): it writes autonomously to public GitHub issues
  from anonymous, internet-sourced content, and makes outbound HTTP requests to submitter-chosen
  URLs to check for dead links — an SSRF-adjacent surface.
- **Issue #77** (Epic G's unattended digest confirmation): it auto-publishes catalogue data the
  live Streamlit app reads directly, with nobody watching — a stronger case than #58's, since it is
  a production-deployment escalation, not just a public write.

Both pull requests (#68, #80) opened, ran full CI, and waited. The maintainer reviewed and merged
both directly.

## Real defects found only by running things for real

Several agents in this wave found and fixed genuine bugs by testing against the real, full-scale
catalogue (932,511 deduplicated projects, 6,377 eligible lists) instead of small fixtures alone:

- A `list_count` aggregation bug that counted raw entry occurrences instead of distinct citing
  lists (Epic A).
- A first publish attempt at ~722MB that GitHub's 100MB push limit rejected outright, requiring a
  redesign to shard the new artifact the same way `data/lists/` already does (Epic A).
- An O(n²) heading-sort in the alternatives pipeline that took over 45 minutes and 2GB of RAM on
  the full catalogue before being fixed to sort once per heading (Epic E).
- `st.html()`'s DOMPurify sanitizer silently stripping raw `<svg>` markup — discovered only by
  actually rendering the new network view in a browser, not by unit tests (Epic D).

None of these were visible from small-scale local testing; they only surfaced by running the real
pipeline against the real, published data.

## Verification

409 tests passing (1 deliberately opt-in real-CLI integration test skipped, matching this repo's
no-network-by-default convention) at the close of this wave, up from 158 at the start. Every merge
ran `pytest`, the relevant `tools.*` data validators against the real published catalogue, and the
Agentflow evidence validators (`validate-sdlc-role-pass.mjs`, `validate-pr-manifest.mjs`,
`verify-agent-workflow.mjs`) before landing.

## Follow-up work, not silent scope drift

- [#67](https://github.com/smota/agentflow-demo/issues/67) — document the new intake/changelog commands
- [#79](https://github.com/smota/agentflow-demo/issues/79) — a pre-existing worktree tooling gap, found in passing
- [#86](https://github.com/smota/agentflow-demo/issues/86) — Epic D's stretch item (community-detection clustering), deliberately deferred

## What this wave did not attempt

Fresh, newly captured, watermarked screenshots of the new views for this delivery story page. The
new functionality was verified live in a browser (cross-list search returning real, honestly
labeled results; the network view rendering a real hub list's neighborhood) — that verification is
real and is what gated each merge — but no new image file was added to the story's screenshot
gallery in this pass. Recorded here rather than left unstated.
