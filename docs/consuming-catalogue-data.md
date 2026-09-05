# Consuming the catalogue data as a third party

AwesomeAwesomeness publishes its underlying dataset as **committed, versioned files in this public
GitHub repository** — not as a hosted API. The free Streamlit deployment itself only reads these
same committed files (`docs/demo/list-data.md`): "The free Streamlit host reads these committed
files only: no crawler, credentials, AI inference or database service runs there." Anything that can
issue an HTTPS `GET` request can fetch and use this data directly, with **no new endpoint, no API
key, and no credentials of any kind**.

This page is for an external consumer of the data — not a contributor to this repository. If you
are looking for how the data is produced or locally refreshed, see `docs/demo/list-data.md` instead.

## What you can fetch

| File                    | Contents                                                                 | Schema                                    |
| ------------------------ | --------------------------------------------------------------------------- | -------------------------------------------- |
| `data/list-index.json`   | The full list-first discovery/classification index (~8k observed repositories, `eligible`/`pending`/`excluded`) | `schemas/list-index.schema.json`             |
| `data/catalogue.json`    | The three-source CC0 preview catalogue of deduplicated resource entries     | `schemas/catalogue.schema.json`              |

Both files are plain JSON over HTTPS, served by GitHub's raw content host — no rate-limited or
authenticated GitHub API call is required to read them.

## Fetching a snapshot

Use `raw.githubusercontent.com` with this URL shape:

```text
https://raw.githubusercontent.com/smota/agentflow-demo/<ref>/data/<file>.json
```

`<ref>` is any Git ref that exists in this public repository: a branch name (`main`), a tag
(`v2.1.0`), or a full commit SHA. **Prefer pinning to a commit SHA or release tag** rather than a
moving branch name if you want a stable, reproducible snapshot — `main` will change over time as new
data is published.

This exact command was run against the live repository while writing this document and returned a
real, current file:

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}  size=%{size_download} bytes\n" \
  "https://raw.githubusercontent.com/smota/agentflow-demo/main/data/catalogue.json"
# HTTP 200  size=1601749 bytes
```

The same pattern works for `list-index.json` and for a pinned commit SHA instead of `main`:

```bash
# Latest on the default branch
curl -sS "https://raw.githubusercontent.com/smota/agentflow-demo/main/data/list-index.json" \
  -o list-index.json

# Pinned to an exact, reproducible commit
curl -sS "https://raw.githubusercontent.com/smota/agentflow-demo/540d466f6e39f94ae79aeea8a280d8bc86117378/data/catalogue.json" \
  -o catalogue.json
```

No `Authorization` header, cookie, or token is sent or required by either command. If you are
scripting a recurring fetch, respect GitHub's normal, unauthenticated rate limits for raw content
requests; this project does not offer a higher-throughput or authenticated alternative, by design
(see Epic #49 — "no new server, database, or paid infrastructure").

## Validating what you fetched

Before parsing a fetched file, validate it against the published JSON Schema for that file
(`schemas/list-index.schema.json` / `schemas/catalogue.schema.json`, fetched the same way as the
data file above, at the same ref). For example, with Python's `jsonschema` package:

```python
import json
import urllib.request
from jsonschema import Draft202012Validator

ref = "main"  # or a pinned commit SHA / tag
base = f"https://raw.githubusercontent.com/smota/agentflow-demo/{ref}/"

schema = json.load(urllib.request.urlopen(base + "schemas/list-index.schema.json"))
data = json.load(urllib.request.urlopen(base + "data/list-index.json"))

Draft202012Validator(schema).validate(data)  # raises jsonschema.ValidationError on a mismatch
```

Any language with a JSON Schema (2020-12) implementation works the same way — the schema is not
Python-specific.

## Before consuming a new publication

Data-shape changes are tracked separately from the app version in
`docs/data-schema-changelog.md`. Before pointing an existing integration at a newer ref:

1. Check whether a new **major** entry has landed in the changelog since the version you last
   validated against — that indicates a breaking change to the shape.
2. If only **minor**/**patch** entries have landed, your existing parsing code can keep working
   unchanged; new, optional fields may simply appear.

## What this is not

- Not a hosted API: there is no query endpoint, no pagination service, and no server-side
  filtering. You fetch the whole committed file and filter locally.
- Not authenticated: no API key or OAuth token is issued, needed, or accepted for this workflow.
- Not guaranteed available at every historical ref forever: GitHub raw content is served from
  whatever refs still exist in the repository; a release tag is the most durable ref to depend on
  long-term.
