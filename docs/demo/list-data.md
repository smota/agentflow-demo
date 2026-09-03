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
.venv/Scripts/python.exe -m tools.lists stage --run-id lists-YYYYMMDD
# Review counts, coverage, permissions and the exact staged digest first:
.venv/Scripts/python.exe -m tools.lists publish --expected-digest <reviewed-digest>
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
A partial publication leaves the previous index usable. Existing generations remain
available for recovery; cleanup requires a separate referenced-generation review.
The free Streamlit host reads these committed files only: no crawler, credentials,
AI inference or database service runs there.
