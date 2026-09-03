# Issue #22: feat: enrich list profiles and contributor credit

**Epic:** #16

## Background & Problem Statement

Users need consistent, evidence-backed information to choose and explore lists, including original taxonomy, real content freshness, and the people maintaining them. The alpha intentionally leaves freshness and contributor counts unknown.

## Requirements

Extend list profiles with useful scope/topics, original categories and property names, observed numeric KPIs, real content freshness, public contributor promotion, contribution/source-data links and stronger list classification. Keep unknown distinct from zero and all enrichment local.

## Technical Design

Continue from completed frozen run D: 8,370 of 8,373 candidates have content observations and three source-integrity errors remain pending. Reparse verified raw inputs with a new reviewed engine generation; never rewrite engine or checkpoint identities. Content freshness uses README/source-content path history at the pinned revision, not repository push time. Contributor observations are bounded and labelled: public logins/URLs and counts only, never emails. Classifier improvements use evidence patterns, not repository allowlists. Generated README source-data attribution is linked where detected. Publish a new snapshot only after source validation, review and exact-digest acceptance.

## Business logic

- **BR-1 (rule):** Profile facts are pinned, public observations with explicit completeness/bounds; unknown is never converted to zero.
- **BR-2 (rule):** Content freshness reflects the observed list source path, not repository-wide pushes, using a documented formula/range.
- **BR-3 (rule):** Contributor promotion uses public identities/URLs and bounded contribution observations; never retain or publish email addresses.
- **BR-4 (rule):** Original taxonomy remains distinct from normalized topics; classification uses general evidence, never a repository allowlist.
- **BR-5 (rule):** Hosted UI remains read-only; every new detail/source/contributor URL and identity is schema-bound and safe.

## Acceptance criteria

### Feature-specific

- [ ] AC-1 (BR-1): List profiles expose scope, original taxonomy/properties and observed stars/forks/contributor/content KPIs with bounds.
- [ ] AC-2 (BR-2): Last content change and freshness range/index use dated path-specific evidence and a documented formula.
- [ ] AC-3 (BR-3): Public contributors and contributing/source-data links work without hosted API calls; no email enters the accepted snapshot.
- [ ] AC-4 (BR-4): High-star legitimate lists no longer stay pending for narrow wording; classification tests are general and allowlist-free.
- [ ] AC-5 (BR-5): In-list filtering and every enriched source URL remain pinned, validated and safe; unsupported content stays explicit.

## Test plan

Parser/classifier fixtures; missing/zero/bounded metrics; path-history timestamps and freshness boundaries; public contributor sanitization and truncation; generated-source attribution; safe links and source binding; three unresolved encoding cases; browser exploration across multiple real list formats; source-bound full suite and protected CI.

## Workflow classification

- **Profile:** standard
- **Risk:** medium
- **Effort:** large
- **Change surfaces:** catalogue-schema, local-crawler, public-UI, committed-snapshot
- **Collaboration:** data-contract and privacy councils; single accountable agent, explicit self-review and simulated stakeholder perspectives.

## Open questions

None. Unsupported encodings remain pending unless exact bytes can be safely decoded under the reviewed contract. GitHub rate limits may require checkpointed continuation, not reduced coverage or fabricated counts.
