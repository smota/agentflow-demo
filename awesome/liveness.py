"""Pure liveness signal schema, validation and shard helpers; no networking or runtime writes.

Epic E / #71. Answers the single question the maintainer confirmed as this epic's gate, ahead of
usage and alternatives: is a deduplicated project (from `awesome.projects`) still alive? Computed
offline by `tools/derive_liveness.py` from GitHub's own repository metadata via the already-
authenticated `gh api` pattern `tools/crawl.py` uses (the operator's own `gh` CLI login -- not a
new credential) -- this module only defines the record shape and its validation, mirroring
`awesome.projects`' digest/shard discipline so the artifact composes with it in the UI.

Only `github.com/<owner>/<repo>` project URLs are in scope -- a project whose canonical URL is not
a GitHub repository has no liveness record published for it at all (never a null-filled stand-in),
and the UI must show that as "not observed", not "inactive". `last_commit_at` is GitHub's own
`pushed_at` on the repository -- a push to *any* branch, not proven to be the default branch's HEAD
commit -- and is disclosed as such in `CONTENT_POLICY` rather than presented as more precise than it
is. `releases` describes up to the 5 most recently published releases actually observed; cadence
(`median_interval_days`) is only computed when at least two were observed, and is null, not zero,
when a project has shipped zero or one release.
"""
from __future__ import annotations

import re
from datetime import datetime

from awesome.catalogue import digest, safe_url
from awesome.projects import project_id

FORMAT = 1
GITHUB_REPO = re.compile(r"https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)/([A-Za-z0-9._-]+?)/?$")
MAX_RELEASES_OBSERVED = 5
CONTENT_POLICY = ("Liveness is only published for GitHub-hosted projects. `last_commit_at` is "
                   "GitHub's own repository `pushed_at` timestamp -- a push to any branch, not "
                   "verified to be the default branch's HEAD commit. `archived` is GitHub's own "
                   "archived flag. `releases.median_interval_days` is computed only from the up to "
                   f"{MAX_RELEASES_OBSERVED} most recently published releases actually observed; "
                   "null (not zero) means fewer than two releases were observed. A project absent "
                   "from this artifact has not been computed yet or is not GitHub-hosted -- absence "
                   "is never presented as 'inactive'. This is the most visually prominent signal in "
                   "Epic E by explicit product decision: it gates trust before usage or alternatives.")


def github_repo(url: str) -> tuple[str, str] | None:
    """Return `(owner, repo)` for a canonical GitHub repository URL, else None."""
    match = GITHUB_REPO.fullmatch(url or "")
    if not match:
        return None
    return match.group(1), match.group(2)


def shard_path(prefix: str) -> str:
    return f"liveness/{prefix}.json"


def build_record(url: str, owner: str, repo_name: str, repo: dict, releases: list[dict], observed_at: str) -> dict:
    """Build one liveness record from already-fetched GitHub API responses. Pure: performs no I/O
    and does not decide which projects to fetch -- `tools/derive_liveness.py` owns that."""
    published = sorted((r["published_at"] for r in releases if r.get("published_at")), reverse=True)
    intervals = None
    if len(published) >= 2:
        parsed = [datetime.fromisoformat(p.replace("Z", "+00:00")) for p in published]
        deltas = [(parsed[i] - parsed[i + 1]).days for i in range(len(parsed) - 1)]
        deltas.sort()
        mid = len(deltas) // 2
        intervals = deltas[mid] if len(deltas) % 2 else (deltas[mid - 1] + deltas[mid]) / 2
    return {
        "id": project_id(url), "url": url, "owner": owner, "repo": repo_name,
        "default_branch": repo.get("default_branch"), "archived": bool(repo.get("archived")),
        "last_commit_at": repo.get("pushed_at"),
        "releases": {"observed_count": len(published), "latest_at": published[0] if published else None,
                     "median_interval_days": intervals},
        "observed_at": observed_at,
    }


def validate_record(record: dict, prefix: str) -> None:
    url = record.get("url")
    repo_pair = github_repo(url or "")
    if not repo_pair or record.get("owner") != repo_pair[0] or record.get("repo") != repo_pair[1]:
        raise ValueError("Liveness record URL is not a canonical GitHub repository")
    if record.get("id") != project_id(url) or not record["id"].startswith(prefix):
        raise ValueError("Liveness record identity or shard placement mismatch")
    if not isinstance(record.get("archived"), bool):
        raise ValueError("Liveness archived flag must be observed as a boolean")
    if record.get("last_commit_at") is not None and not isinstance(record["last_commit_at"], str):
        raise ValueError("Invalid last_commit_at")
    releases = record.get("releases") or {}
    observed_count = releases.get("observed_count")
    if not isinstance(observed_count, int) or observed_count < 0 or observed_count > MAX_RELEASES_OBSERVED:
        raise ValueError("Invalid releases.observed_count")
    if observed_count == 0 and releases.get("latest_at") is not None:
        raise ValueError("Zero observed releases cannot carry a latest_at")
    if observed_count < 2 and releases.get("median_interval_days") is not None:
        raise ValueError("Cadence requires at least two observed releases")
    if not record.get("observed_at"):
        raise ValueError("Liveness record missing observed_at")


def validate_shard(shard: dict, prefix: str, known_project_ids: set[str] | None = None) -> None:
    if shard.get("format_version") != FORMAT or shard.get("prefix") != prefix:
        raise ValueError("Unsupported or mismatched liveness shard")
    if shard.get("digest") != digest({k: v for k, v in shard.items() if k != "digest"}):
        raise ValueError("Liveness shard digest mismatch")
    seen_ids = set()
    for record in shard.get("projects", []):
        validate_record(record, prefix)
        if record["id"] in seen_ids:
            raise ValueError("Duplicate liveness record within a shard")
        seen_ids.add(record["id"])
        if known_project_ids is not None and record["id"] not in known_project_ids:
            raise ValueError("Liveness record references a project outside the published catalogue")


def validate_liveness(data: dict, shards: dict | None = None, known_project_ids: set[str] | None = None) -> None:
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported liveness catalogue format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Liveness catalogue digest mismatch")
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
                raise ValueError("Duplicate liveness record across shards")
            seen_ids.add(record["id"])
        total += len(shard["projects"])
    if data.get("counts", {}).get("projects") != total:
        raise ValueError("Project count does not reconcile")
