# ADR 001 — Local ingestion, static public catalogue

Status: accepted for preview, 2026-09-02. Issue #4.

## Decision

Local Python discovers GitHub candidates, fetches pinned README/license bytes and
extracts Markdown list-item links into versioned JSON. Streamlit imports only the
read-only catalogue/search module. It never launches the crawler or a model.

Initial reviewed scope: sindresorhus/awesome, sindresorhus/awesome-nodejs and
rust-unofficial/awesome-rust, contingent on fresh search qualification and pinned
CC0 license verification. Other candidates remain explicitly excluded from this
preview, not classified as unlicensed or low quality. Nested linked lists are not
recursively ingested. This is a selected index, not an exhaustive Awesome mirror.

## Options and council

Two fresh-context, read-only Codex helpers advised the parent architect:
architecture_data (data/risk) and architecture_delivery (implementation/testability).
The parent retained implementation and gate ownership. Same-platform advice is not
cross-platform role alternation or human approval. Common brief: architecture-brief.md.

| Option | Decision |
| --- | --- |
| Static JSON | Accepted: transparent diffs, simple rollback, small read-only runtime |
| SQLite | Deferred design alternative: no measured scale need for a binary index |
| Hosted live crawler | Rejected: violates the local-only processing contract |

All blocking objections accepted as requirements: actual license-content review at
pinned revision; HTML-disabled token extraction; safe URL boundary independent of
parser defaults; all source occurrences retained; explicit parser coverage and caps.
The objection that a selected corpus cannot satisfy preview scope was rejected:
coverage is disclosed and discovery decisions are retained.

## Data and safety contract

- Query names/descriptions and Awesome topics; paginate completely or fail the run.
- Record query, time, completeness, repo identity, visibility, stars and selection reason.
- Require integer stars >=50,000, reviewed list suitability and CC0 license evidence.
- Pin commit before README/license retrieval; record exact paths and SHA-256 hashes.
- Extract first substantive link per Markdown list item, including nested/reference links.
  Ignore image links, navigation anchors, code fences and HTML-only/table-only records.
  Additional links remain part of the source text but are not separate primary resources.
- Do not render source Markdown/HTML, fetch resource destinations or load external images.
- Accept absolute HTTP(S) only; reject controls, credentials, backslashes, malformed
  hosts and nonpublic IP literals. Preserve path case, queries and fragments.
- Deduplicate canonical URLs, retaining every source occurrence and original context.
- Caps: 2 MiB per README, 10,000 unique resources, 10 MiB catalogue, 200-character
  search input, 24 visible records per page. Fail generation on size overflow.
- Literal casefolded search, deterministic ordering, atomically replace only validated data.

## Validation and consequences

Pure-function tests cover parsing/URLs/threshold/dedup/search. AppTest covers actual
Streamlit behavior with networking denied; browser checks remain separately required.
Pinned inputs rebuild deterministic resource content; observation timestamps legitimately
change across new discoveries. Record extraction and observation times separately.

One root requirements.txt governs hosted dependencies. Local/CI/hosting target Python
3.11. No Docker or external AI provider is necessary. Hosting is best-effort free tier,
not a promised SLA. [Deployment documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

Future scale needs may revisit SQLite, but are not required work for this demo.
