# Data schema changelog and semver policy

This document versions the **shape** of the two data files this project publishes as a versioned
data contract:

- `data/list-index.json`
- `data/catalogue.json`

It is deliberately a separate axis from two other version numbers already present in this
repository, which it does not replace:

| Version                                             | What it tracks                                                                 | Where it lives                                            | Who bumps it                                                     |
| ---------------------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------- |
| App/package version                                  | The AwesomeAwesomeness Streamlit application itself                              | `package.json` (`version`)                                 | Release PRs, per `docs/release-versioning.md`                        |
| Runtime format guard (per file)                      | The exact shape a specific file loader (`awesome/lists.py`, `awesome/catalogue.py`) will accept at all | `format_version` field inside each data file (currently `3` for `list-index.json`, `1` for `catalogue.json`) | Whoever changes the corresponding Python loader/validator; a mismatch makes the file unreadable by that code |
| **Data-shape semver (this document)**                | The external, documented *contract* a third-party consumer validates against    | This file + `schemas/list-index.schema.json` / `schemas/catalogue.schema.json` | Whoever changes either JSON Schema, following the policy below |

The data-shape semver is intentionally coarser and more conservative than the internal
`format_version` guard: a `format_version` bump always requires at least a data-shape semver entry
(the loader's compatibility contract changed), but not every data-shape semver entry requires a
`format_version` bump (e.g. adding a new optional field is a data-shape **minor** change that
existing loaders keep accepting unchanged).

## Version format

`MAJOR.MINOR.PATCH`, applied independently per file (`list-index` and `catalogue` each carry their
own version), since the two files can evolve on different schedules.

- **MAJOR** — a change that breaks a consumer written against the previous schema:
  - removing a required field, or making a previously-required field name disappear
  - changing a field's type or the set of allowed values in a way existing data no longer satisfies
    the old schema (e.g. narrowing an enum, changing a nullable field to non-nullable in a way that
    changes meaning, renaming a field)
  - changing what a `format_version` value inside the file means
  - any change to the URL layout a consumer needs to fetch the file at all (path, filename)
- **MINOR** — an additive, backwards-compatible change:
  - a new optional field on an existing object
  - a new possible (additional) enum value that old code already ignoring unknown values would
    tolerate
  - loosening a constraint (e.g. widening a numeric range, making a previously-required field
    optional)
- **PATCH** — a change to the schema or this changelog that does not change what data validates:
  - fixing a schema bug where the schema was stricter or looser than the real, already-published
    data actually is (a documentation/tooling correction, not a data-shape change)
  - clarifying descriptions, adding examples, fixing typos

A breaking (MAJOR) change must ship with:

1. a new changelog entry below explaining exactly what broke and why,
2. the updated schema file(s) in `schemas/`,
3. a note in the PR description pointing consumers at both.

An additive (MINOR) or clarifying (PATCH) change only requires the changelog entry and schema
update; no coordination is required because existing consumers are unaffected.

## Relationship to `format_version`

Each file's `format_version` integer (checked by `awesome/lists.py::validate_index` and
`awesome/catalogue.py::validate_catalogue`) is this project's own *runtime* compatibility guard —
it protects the Streamlit app and `tools/lists.py`/`tools/crawl.py` from reading a shape they don't
understand. The data-shape semver in this changelog is the *public* contract external consumers
read. They move together at a MAJOR bump (a `format_version` change is always also a data-shape
MAJOR change) but the reverse is not required: this project can add an optional field (data-shape
MINOR) without ever touching `format_version`.

## Changelog

### list-index.json

#### v1.0.0 — 2026-09-04

Initial published data-shape contract, seeded from the current committed
`data/list-index.json` (`format_version: 3`, digest
`0c9ffd50682687d0071b5e81c58b7dc18ea2b8b2d3a0482cd13daba00d0deeba`, generation `alpha.2`; see
`docs/demo/list-data.md`). Documented in `schemas/list-index.schema.json`. This is a documentation
baseline, not a claim that the shape has never changed before — see "Pre-v1.0.0 history" below for
the shape changes that already happened before this changelog existed.

Top-level fields: `format_version` (const `3`), `min_stars` (const `100`), `run_id`, `started_at`,
`generated_at`, `engine_digest`, `queries`, `replay` (nullable), `coverage`, `counts`, `lists[]`,
`digest`. Each `lists[]` record carries GitHub repository identity/metrics, a `state`
(`eligible`/`pending`/`excluded`) with `reason`, derived `topics`/`freshness`, optional
enrichment-only fields (`revision`, `readme_sha256`, `content_updated_at`, `parent`, `contributors`,
...) present only once that record has been enriched, and an optional `detail` pointer to an
immutable per-list shard file.

#### Pre-v1.0.0 history (informational — not versioned under this policy)

These are the shape changes that happened before this changelog existed, recorded here only so the
`format_version` progression is not a mystery. They are not retroactively assigned data-shape semver
numbers.

- `format_version: 1` → `2` → `3`: the discover/classify/enrich pipeline (`tools/lists.py`) was
  introduced and iterated (list-first architecture replacing an earlier three-source-only design),
  adding `state`/`reason`/`freshness`/`contributor_observation`/`detail` and the shard-publication
  model described in `docs/demo/list-data.md`.

### catalogue.json

#### v1.0.0 — 2026-09-04

Initial published data-shape contract, seeded from the current committed `data/catalogue.json`
(`format_version: 1`). Documented in `schemas/catalogue.schema.json`.

Top-level fields: `format_version` (const `1`), `generated_at`, `discovery[]`, `candidates[]`,
`coverage`, `sources[]` (the reviewed, CC0-licensed, `decision: selected` subset of `candidates[]`),
`resources[]` (deduplicated entries with `occurrences[]` back to `sources[]`), `digest`.

This file predates the list-first pipeline and reflects the original three-source CC0 preview
design; it has not changed shape since `format_version: 1` was introduced, so there is no
pre-v1.0.0 history to record for it.

## How to use this when consuming the data

1. Fetch the schema (`schemas/list-index.schema.json` or `schemas/catalogue.schema.json`) at the
   same commit/ref as the data file — see `docs/consuming-catalogue-data.md`.
2. Compare the version you last validated against to the entries above. If nothing newer than your
   last-known version has landed, your existing parsing code is safe to reuse unchanged.
3. If a new MAJOR entry exists between your last-known version and the ref you are fetching, re-read
   that entry before parsing — your existing code may reject or misread the new file.
