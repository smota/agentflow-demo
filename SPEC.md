# Issue #42: docs: publish live AgentFlow delivery story

## Background & Problem Statement

The public Delivery view is a pair of links rather than an inspectable demonstration of
AgentFlow. Replace it with an evidence-backed interactive story covering all three completed
build episodes. The narrative climax is a fresh-context executor reconstructing the exact
delivery position, demonstrating consistency across agents and sessions.

The implementation was prepared locally after editorial approval. Issue #42 activates the
governed publication path for the exact v2.1.0 candidate; it does not retroactively claim that
the pre-issue local edits were produced under an active issue gate.

## Requirements

Render the complete AgentFlow-first story inside Streamlit. Illustrate roles, deterministic
commands, decisions, handovers, candidate-bound evidence, recovery and reconciliation. Derive
product metrics from the current list snapshot and process metrics from a checked versioned
manifest. Link public GitHub evidence, omit private Codex session links, watermark every story
screenshot with the Move the Needle logo and visible `movetheneedle.info` text, and publish the
exact accepted result as v2.1.0.

## Business logic

- **BR-1 (rule):** AgentFlow roles, deterministic commands, decisions, handovers and recovery are the primary story; AwesomeAwesomeness is the shipped case.
- **BR-2 (rule):** The three completed build episodes form one coherent lifecycle and link only to durable public evidence; private `codex://` sessions are not linked.
- **BR-3 (rule):** Process statistics come from a versioned evidence manifest and product statistics from the current versioned list snapshot; unknown values and historical checkpoints remain explicit.
- **BR-4 (rule):** Cross-session consistency is demonstrated field by field without an invented aggregate score.
- **BR-5 (rule):** Every screenshot displayed by the story includes a visible Move the Needle logo and `movetheneedle.info` watermark.
- **BR-6 (rule):** Same-platform advisors, cooperative recovery, local checks, GitHub state, releases and deployment retain their stated evidence boundaries.
- **BR-7 (rule):** v2.1.0 is accepted only after the exact commit, checks, tag, GitHub Release and cold public Streamlit behavior are reconciled separately.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): Delivery renders an AgentFlow-first narrative with role flow, deterministic command rail and governed decision replay.
- [ ] AC-2 (BR-2): Build 1, Build 2 and Build 3 are represented; no public page or manifest contains a `codex://` link.
- [ ] AC-3 (BR-3): The page renders live snapshot metrics and accessible charts/tables from checked data.
- [ ] AC-4 (BR-4): The recovery climax compares recorded and fresh-context state across the required fields and retains the rejected partial attempt.
- [ ] AC-5 (BR-5): All story screenshots are rendered through a tested watermark function with logo and visible site text on desktop and 390px mobile.
- [ ] AC-6 (BR-6): Evidence-boundary disclosure and GitHub evidence explorer are present and accurate.
- [ ] AC-7 (BR-7): Full tests, workflow checks, data validation, protected PRs, v2.1.0 release and cold hosted acceptance pass for the exact candidate.

## Test plan

Run the delivery manifest/watermark tests, complete Python suite, AgentFlow workflow checks,
catalogue validation and `git diff --check`. Inspect the rendered story at desktop and a true
390px viewport, including the watermark and interactive selectors. Promote through protected
integration and `main` PRs. Reconcile the exact commit, checks, tag and GitHub Release, then
cold-load the public Streamlit app and verify v2.1.0, story metrics, command rail, consistency
matrix, public evidence links and visible watermark independently.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** medium
- **Change surfaces:** Streamlit Delivery UI, versioned story manifest, charts, branded screenshots, tests, release metadata and public deployment
- **Collaboration:** previously completed product-storytelling, information-architecture and UX advisory review; one accountable Codex executor; same-platform advice is not human approval

## Open questions

None. The user authorized publication as v2.1.0 in `smota/agentflow-demo` and deployment to
`awesomeawesomeness.streamlit.app` on 2026-09-04.
