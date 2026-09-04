# List-first data contract

AwesomeAwesomeness discovers **lists**, not just projects mentioned in lists. V1's
three-source review allowlist excluded awesome-selfhosted despite discovering it
above50kstars. The new local pipeline separates discovery, classification, enrichment
and content permissions; the minimum observed star count is100.

## Discovery and honest coverage

Three queries cover the broad `awesome` keyword and `awesome`/`awesome-list` topics.
All explicitly include forks, whose repository identities remain distinct. Queries
are partitioned into non-overlapping creation-date ranges, then star ranges for dense
single dates. Every leaf is paginated. Saturated unsplittable partitions, changing
counts, empty pages and incomplete responses are reported as unresolved, never as
exhaustive coverage. GitHub search is non-transactional and not a global census.

Each repository retains its stable GitHub ID, canonical name, observed public/star
metrics, timestamp and query routes. Duplicate results merge provenance, not counts.
A star count of99 fails eligibility;100 meets the popularity threshold but still
requires evidence that the repository is a curated list.

## Classification and content

Curated-list intent and supported README content are required for `eligible`.
Awesome-named applications with documentation links are not automatically lists.
Insufficient evidence, missing formats, partial GraphQL replies and errors remain
`pending`. Explicit `excluded` decisions carry their reason. These deterministic
heuristics are an auditable baseline, not a claim of perfect semantic classification.

The crawler freezes a repository commit before reading its Markdown README. It
extracts factual item titles/URLs and original heading hierarchy from list items and
tables. Selected factual table properties, such as language or license, are retained;
descriptions are not copied. Embedded HTML and other files are outside this parser's
coverage. Counts describe parsed content, not the repository's entire contents.

Unknown licenses do not remove a list. The app uses metadata and upstream links,
with original curators credited; it does not republish complete README prose. Source
license information remains separate from this application's code license.

## Metrics and provenance

Missing metrics are null, not zero. Repository push activity is not content freshness.
Content update dates require path-specific evidence; until that enrichment completes,
freshness remains unknown. The optional derived freshness index is
`100 × 2^(-days since verified content update / 180)` and is not a quality score.
Topic labels are a transparent derived keyword mapping, additional to original
categories. No invented historical growth series is displayed.

## Local refresh and recovery

Run from the demo root using its environment:

```powershell
.venv/Scripts/python.exe -m tools.lists discover --run-id lists-YYYYMMDD
.venv/Scripts/python.exe -m tools.lists enrich --run-id lists-YYYYMMDD
.venv/Scripts/python.exe -m tools.lists profiles --run-id lists-YYYYMMDD --batch-size 8 --workers 4
.venv/Scripts/python.exe -m tools.lists stage --run-id lists-YYYYMMDD
# Review counts, coverage, permissions and the exact staged digest first:
.venv/Scripts/python.exe -m tools.lists publish --expected-digest <reviewed-digest>
.venv/Scripts/python.exe -m tools.prune_list_shards --directory data --expected-digest <reviewed-digest>
# Apply only after reviewing that dry-run and while the same index is installed:
.venv/Scripts/python.exe -m tools.prune_list_shards --directory data --expected-digest <reviewed-digest> --apply
.venv/Scripts/python.exe -m tools.lists validate
```

Page and repository checkpoints live under ignored `.agent-runs/list-crawl`. Raw
READMEs stay in ignored `data/raw/lists`. Only one CLI writer may operate; inspect
the PID in `.agent-runs/list-crawler.lock` before recovering a crashed process. Never
delete an active or unknown writer lock. A changed engine/checkpoint requires a new
reviewed run; editing its hashes to force resume is prohibited.

For a reviewed engine correction, `replay` creates a new generation from a completed
discovery checkpoint. Supply `--source-run` and its exact `--expected-digest`, plus
a new `--run-id`. It requires identical discovery queries and threshold, verifies
each reused raw input's SHA-256, reparses rather than copying classifications, and
records the source engine/digest. The source checkpoint is never modified. Resume
unfinished enrichment normally against the new generation. Replays are local
integrity checks, not cryptographic attestations from GitHub.

`--interrupt-after` injects a real local interruption after durable search pages or
enrichment batches. Resume with the same run ID without that flag. Test and actual
live interruption observations are recorded separately in the delivery journal.

Publication uses immutable digest-named detail files. Every referenced shard must
validate before the compact `data/list-index.json` pointer is atomically replaced.
A partial publication leaves the previous index usable. Existing checkpoint
generations remain available for recovery. Obsolete published shards may be removed
only by the separate digest-bound prune command after its dry-run; tracked bytes
remain recoverable from Git history and release tags.
The free Streamlit host reads these committed files only: no crawler, credentials,
AI inference or database service runs there.

## Early snapshot versus completed enrichment

The first accepted list-first generation is intentionally partial: 8,373 discovered
candidates, 1,510 eligible lists, 6,503 pending, 360 excluded, and 5,326 still awaiting
content enrichment. Its digest is
`9ab420eac2c8922dee53147030a5272bd92616baa23a8e60db13ff4b78c23796`.
Fifteen eligible records were observed at exactly 100 stars. Eligibility can change
with better content evidence; it is not inferred from membership in a source allowlist.
That alpha.1 snapshot remains the public rollback reference for issue22.

The reviewed alpha.2 candidate completes local profile observation for all 6,377
eligible lists while retaining 1,431 pending and 565 explicitly excluded records.
Its digest is
`0c9ffd50682687d0071b5e81c58b7dc18ea2b8b2d3a0482cd13daba00d0deeba`.
Every eligible list has a pinned README content-update observation and a bounded
public-contributor status. Contributor identities come only from at most 100 commits
touching that path; displayed contributor objects contain login, public profile URL
and observed contribution count—never email fields. Original list content can itself
refer to email software or contain `@` in titles/URLs; that is source-content fidelity,
not contributor contact collection. Three raw inputs with unavailable pinned UTF-8
content remain pending rather than being lossily decoded.

At every promotion, validate the whole generation locally. The hosted app lazily
validates the selected shard against the index's repository name, revision, README
path and SHA-256, and binds category/entry source links to that exact source. A JSON
digest alone does not make arbitrary links or inconsistent provenance acceptable.

## Project-level dedup structure (`data/project-index.json`)

A sibling offline stage, `tools/derive_projects.py`, reads the published `list-index.json` and its
`eligible` detail shards and deduplicates every parsed entry by canonical URL, producing one record
per distinct project with the set of eligible lists that cite it. Run it the same way as the list
pipeline, from the demo root:

```powershell
.venv/Scripts/python.exe -m tools.derive_projects stage
# Review counts and the exact staged digest first:
.venv/Scripts/python.exe -m tools.derive_projects publish --expected-digest <reviewed-digest>
.venv/Scripts/python.exe -m tools.derive_projects validate
```

Sharded the same way `data/lists/` is, and for the same reason: at this catalogue's scale
(932,511 distinct projects in the current generation) even a summary-only row per project would
exceed GitHub's 100 MB single-file limit, so `data/project-index.json` itself stays tiny — counts
plus a `prefix -> shard digest` map (256 buckets, keyed by the first two hex characters of each
project's id) — and every actual project field lives in `data/projects/<2-hex-prefix>.json`. A
sha256-derived id is close to uniformly distributed, so no shard concentrates a meaningful share of
the total (observed: 256 shards, largest ~3.2 MB).

Each project record carries `list_count` (the number of **distinct** eligible lists citing the URL)
separately from `occurrence_count` (the raw number of parsed entries, which can exceed `list_count`
when one list cites the same URL more than once — for example under two categories). Collapsing
that distinction would silently let one list's internal repetition look like cross-list agreement.
Every occurrence keeps that citing list's own title/category/source link — never a merged or
invented description.

`list_count`/`occurrence_count` are **factual counts, not a validated trust or quality signal.** A
sampled validation of whether cross-list co-occurrence reflects independent curator judgment found
it does not, predominantly: of 60 sampled projects with `list_count >= 2` (30 highest-occurrence,
30 stratified-random), 54 (90%) showed copy-lineage signals (near-identical entry text across lists,
including same-owner sibling lists and forked/derivative lists) and only 6 (10%) showed genuinely
independent-curation signals. This holds even when controlling for the confound that extremely
famous, short-named projects are expected to have identical citation text regardless of copying
(a harder longer-title subset, less subject to that confound, showed the same 90/10 split). This
structure is therefore published as a factual cross-reference only; it is not presented in the app
as a consensus/trust cue, and any future UI use of `list_count` for ranking must account for this
finding rather than treat raw occurrence count as validated agreement.

## Data contract for third parties

`data/list-index.json` and `data/catalogue.json` are also a published, versioned data contract, not
only this app's internal state: `../consuming-catalogue-data.md` shows an external consumer how to
fetch and validate the committed snapshot directly from `raw.githubusercontent.com` with no new
endpoint and no credentials, `../../schemas/list-index.schema.json` and
`../../schemas/catalogue.schema.json` are the formal JSON Schemas for each file, and
`../data-schema-changelog.md` tracks the data *shape's* own semantic version — separate from both
`package.json`'s app version and each file's internal `format_version` guard.
