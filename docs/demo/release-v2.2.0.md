# v2.2.0 — From lists to intelligence

AwesomeAwesomeness 2.2 extends list-first discovery with a project-level layer built on top of it,
and keeps the delivery running without anyone watching it overnight.

The catalogue adds:

- **cross-list project search** — search once and see matching projects from any eligible list,
  ranked by text relevance. Citation counts, when shown, are a disclosed, honestly labeled fact,
  never a trust score — a validation spike found that raw citation counts are mostly copy-lineage
  between related lists, not independent curation, and the design changed before it shipped;
- **project profiles** with a liveness gate (last commit, release cadence, archived status), a
  real-usage signal sourced from public package registries, and "see alternatives" drawn from the
  same heading a project already sits under in the lists that cite it;
- **list similarity and near-duplicate detection**, plus an opt-in network exploration view for
  browsing a list's neighborhood — additive to, never replacing, list-first browsing;
- **community curation intake**: structured issue templates to propose a list or flag an item, and
  a batch process that resolves the deterministic majority automatically, without requiring anyone
  to triage daily;
- a **versioned JSON Schema and changelog** for the published catalogue data, so third parties can
  consume the committed snapshot directly;
- an **unattended local pipeline**, scheduled weekly on the maintainer's own machine, with no
  server, hosted CI, or external dependency; and
- a **scoped, opt-in headless-CLI interpretation layer** for the handful of cases deterministic
  rules can't resolve alone — cached, digest-linked, and never a live dependency of the hosted app.

None of this changes what the hosted Streamlit app requires: no API key, no model, no runtime
crawling. Two stories in this release — community intake's public-write surface and the unattended
pipeline's auto-publish step — were classified high-assurance by the Architect phase and were held
for actual human review before merge, per this project's own review policy; every other story
merged autonomously with a disclosed self-review.

Issue: [#92](https://github.com/smota/agentflow-demo/issues/92) · Epics:
[#47](https://github.com/smota/agentflow-demo/issues/47)–[#54](https://github.com/smota/agentflow-demo/issues/54)
