"""Pure real-usage signal schema, validation and shard helpers; no networking or runtime writes.

Epic E / #72. A deduplicated project's actual usage, distinct from and never blended with stars or
cross-list citation count (#65). This catalogue has no authoritative project -> package mapping, so
`tools/derive_usage.py` uses a disclosed heuristic (the GitHub repo name as a candidate package
name) and only accepts a match when the registry's own metadata cross-references back to the
project's GitHub `owner/repo` -- a false "usage" record is worse than a missing one, so every
accepted source records exactly how it was verified in `matched_via`.

Three public, unauthenticated registries are in scope, per the maintainer's explicit no-new-
credentials constraint:

- **npm** (`registry.npmjs.org` + `api.npmjs.org`): accepted only when the package's own
  `repository.url` metadata resolves to the same GitHub `owner/repo` -- a strong cross-check.
- **PyPI** (`pypi.org` + `pypistats.org`): accepted only when the package's own `project_urls` or
  `home_page` metadata resolves to the same GitHub `owner/repo` -- a strong cross-check.
- **Docker Hub** (`hub.docker.com` public v2 API): Docker Hub's public API exposes no field that
  independently links a repository back to its GitHub source, so this source is accepted only on a
  weaker `namespace/name == owner/repo` (case-insensitive) heuristic, and is always labelled as such
  -- disclosed as materially less reliable than the npm/PyPI cross-checks, never presented with the
  same confidence.

GitHub's own "used by" dependents count has no public, unauthenticated, non-scraping API as of this
writing (`dependencyGraphManifests` describes a repository's own manifest files, not who depends on
it network-wide) -- see `tools/derive_usage.py`'s module docstring and #72 for the disclosed finding.
This module only defines the record shape and its validation; `tools/derive_usage.py` owns the
outbound HTTP calls and only ever runs offline.
"""
from __future__ import annotations

import re

from awesome.catalogue import digest, safe_url
from awesome.projects import project_id

FORMAT = 1
REGISTRIES = ("npm", "pypi", "docker")
CONTENT_POLICY = ("Usage is only published for GitHub-hosted projects with at least one registry "
                   "match verified by the registry's own metadata cross-referencing the project's "
                   "GitHub owner/repo (npm, PyPI), or a same-name heuristic disclosed as weaker "
                   "(Docker Hub, whose public API has no independent cross-check field). Download/"
                   "pull counts are observed registry facts, never blended with stars or cross-list "
                   "citation count, and never converted into a synthesized score. A project absent "
                   "from this artifact has not been computed yet, is not GitHub-hosted, or published "
                   "no package this pipeline could verify -- absence is never presented as 'unused'.")


def shard_path(prefix: str) -> str:
    return f"usage/{prefix}.json"


def validate_source(source: dict) -> None:
    if source.get("registry") not in REGISTRIES:
        raise ValueError("Unsupported usage source registry")
    if not source.get("package"):
        raise ValueError("Usage source missing package identifier")
    if not source.get("matched_via"):
        raise ValueError("Usage source missing match disclosure")
    count = source.get("count")
    if not isinstance(count, int) or count < 0:
        raise ValueError("Usage source count must be a non-negative observed integer")
    if not source.get("metric"):
        raise ValueError("Usage source missing metric label (e.g. downloads_last_month, pulls_total)")


def validate_record(record: dict, prefix: str) -> None:
    url = record.get("url")
    if not safe_url(url) or "github.com/" not in (url or ""):
        raise ValueError("Usage record URL is not a GitHub project URL")
    if record.get("id") != project_id(url) or not record["id"].startswith(prefix):
        raise ValueError("Usage record identity or shard placement mismatch")
    sources = record.get("sources") or []
    if not sources:
        raise ValueError("Usage record must carry at least one matched source")
    seen_registries = set()
    for source in sources:
        validate_source(source)
        if source["registry"] in seen_registries:
            raise ValueError("Duplicate registry within one usage record")
        seen_registries.add(source["registry"])
    if not record.get("observed_at"):
        raise ValueError("Usage record missing observed_at")


def validate_shard(shard: dict, prefix: str, known_project_ids: set[str] | None = None) -> None:
    if shard.get("format_version") != FORMAT or shard.get("prefix") != prefix:
        raise ValueError("Unsupported or mismatched usage shard")
    if shard.get("digest") != digest({k: v for k, v in shard.items() if k != "digest"}):
        raise ValueError("Usage shard digest mismatch")
    seen_ids = set()
    for record in shard.get("projects", []):
        validate_record(record, prefix)
        if record["id"] in seen_ids:
            raise ValueError("Duplicate usage record within a shard")
        seen_ids.add(record["id"])
        if known_project_ids is not None and record["id"] not in known_project_ids:
            raise ValueError("Usage record references a project outside the published catalogue")


def validate_usage(data: dict, shards: dict | None = None, known_project_ids: set[str] | None = None) -> None:
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported usage catalogue format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Usage catalogue digest mismatch")
    shard_digests = data.get("shards") or {}
    for prefix, shard_digest in shard_digests.items():
        if not re.fullmatch(r"[0-9a-f]{2}", prefix) or not re.fullmatch(r"[0-9a-f]{64}", shard_digest or ""):
            raise ValueError("Invalid shard registry entry")
    if data.get("counts", {}).get("shards") != len(shard_digests):
        raise ValueError("Shard count does not reconcile")
    if shards is None:
        return
    if set(shards) != set(shard_digests):
        raise ValueError("Shard set does not match the published index")
    total, seen_ids = 0, set()
    for prefix, shard in shards.items():
        if shard.get("digest") != shard_digests[prefix]:
            raise ValueError("Shard digest does not match the index's registered shard digest")
        validate_shard(shard, prefix, known_project_ids)
        for record in shard["projects"]:
            if record["id"] in seen_ids:
                raise ValueError("Duplicate usage record across shards")
            seen_ids.add(record["id"])
        total += len(shard["projects"])
    if data.get("counts", {}).get("projects") != total:
        raise ValueError("Project count does not reconcile")
