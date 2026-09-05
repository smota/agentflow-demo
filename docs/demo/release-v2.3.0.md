# v2.3.0 — The story writes itself

AwesomeAwesomeness 2.3 changes how the Delivery Story page gets written. It no longer relies on
someone hand-editing prose after the fact — it reads live from an incremental, schema-validated
ledger that any AI coding harness contributing to this repository already feeds automatically.

What's new:

- **A session-record ledger** (`data/sessions/`): one structured, schema-validated record per
  merged pull request, generated from the same `## Agent review` manifest every PR is already
  required to carry — no new authoring step, no harness-specific integration;
- a **live delivery timeline**, filterable by wave, showing every contributing session with its
  harness, workflow profile, and a visible flag whenever a change required actual human review
  before merge;
- a **per-session deep-dive**: decisions made, real defects found only by running the full system,
  and every piece of supporting evidence, one click away;
- **harness-comparison and SDLC-conformance views**: how sessions, findings, and high-assurance
  gates break down across every coding agent that has touched this repository, not just the most
  recent one;
- validation wired into the existing PR check — a session record can't claim evidence its own pull
  request didn't declare.

Twenty-four historical sessions — spanning both Codex's original builds and Claude's most recent
wave — were migrated into the ledger so the timeline starts complete, not empty. Nothing about the
hosted app's data contract changes: still no API key, no model, and no runtime crawling.

Issue: [#95](https://github.com/smota/agentflow-demo/issues/95)
