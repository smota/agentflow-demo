"""Local-only derivation of the real-usage signal (E3/#72). Never imported by hosted UI.

Reads the published project dedup structure (`data/project-index.json` + `data/projects/`, #69),
filters to `github.com/<owner>/<repo>` project URLs (same candidate pool E2/#71 uses, prioritized
the same way -- highest cross-list visibility first), and calls three **public, unauthenticated**
package registry APIs -- the maintainer's explicit constraint for this epic, no new credentials:

- npm: `registry.npmjs.org` (package existence + `repository.url`) and `api.npmjs.org` (downloads).
- PyPI: `pypi.org/pypi/<name>/json` (package existence + `project_urls`/`home_page`) and
  `pypistats.org` (downloads).
- Docker Hub: `hub.docker.com` public v2 API (`pull_count`).

This catalogue has no authoritative project -> package mapping. The GitHub repo name is used as a
*candidate* package name only; npm and PyPI matches are accepted only when the registry's own
metadata cross-references back to the same GitHub `owner/repo` (see `_matches_repo`). Docker Hub's
public API exposes no such cross-check field, so that source is accepted on a weaker namespace/name
heuristic and always labelled as such -- see `awesome/usage.py`'s module docstring.

## GitHub "used by" dependents -- investigated, not assumed

GitHub's own per-repository "used by" / dependents count (shown on a repository's Insights ->
Dependency graph page) has **no public, unauthenticated, non-scraping API** as of this writing:
the REST/GraphQL dependency graph surface (`Repository.dependencyGraphManifests` and the
`dependency-graph` REST endpoints) describes a repository's own *declared* dependencies -- what it
depends on -- not the reverse (who depends on it). The "N Repositories" / "N Packages" dependents
counts on `github.com/<owner>/<repo>/network/dependents` are rendered by GitHub's web application
and are not exposed through `api.github.com` or the public GraphQL schema in any form this pipeline
could call without scraping HTML (explicitly out of scope: this pipeline only ever calls documented
JSON APIs). This is a genuine, disclosed gap, not an oversight -- E3 is scoped to package-registry
downloads only, per #72's own acceptance criteria.

Same bounded-batch, checkpointed, incrementally-merging discipline as `tools/derive_liveness.py`
(see that module's docstring for the rationale); one HTTP request budget covers three registries per
candidate here, so this tool defaults to a smaller batch than E2.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import requests

from awesome.catalogue import digest
from awesome.liveness import github_repo
from awesome.usage import CONTENT_POLICY, FORMAT, shard_path, validate_usage
from tools.derive_projects import load_index as load_list_index, load_projects
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE_DEFAULT = 150
HTTP_TIMEOUT = 15
GITHUB_REF = re.compile(r"github\.com[:/]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?]|$)", re.IGNORECASE)
GITHUB_SHORTHAND = re.compile(r"^github:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", re.IGNORECASE)


def _matches_repo(value: str, owner: str, repo: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    match = GITHUB_REF.search(value) or GITHUB_SHORTHAND.match(value)
    return bool(match) and match.group(1).lower() == owner.lower() and match.group(2).lower() == repo.lower()


def _get(url: str):
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": "AwesomeAwesomeness-offline-pipeline"})
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def npm_lookup(owner: str, repo: str) -> dict | None:
    package = _get(f"https://registry.npmjs.org/{quote(repo, safe='')}")
    if not package:
        return None
    repository = package.get("repository")
    repo_url = repository.get("url") if isinstance(repository, dict) else repository
    if not _matches_repo(repo_url or "", owner, repo):
        return None
    downloads = _get(f"https://api.npmjs.org/downloads/point/last-month/{quote(repo, safe='')}")
    count = (downloads or {}).get("downloads")
    if not isinstance(count, int):
        return None
    return {"registry": "npm", "package": repo, "count": count, "metric": "downloads_last_month",
            "matched_via": "npm registry package.json repository.url resolves to this GitHub owner/repo"}


def pypi_lookup(owner: str, repo: str) -> dict | None:
    package = _get(f"https://pypi.org/pypi/{quote(repo, safe='')}/json")
    if not package:
        return None
    info = package.get("info") or {}
    candidates = [*(info.get("project_urls") or {}).values(), info.get("home_page"), info.get("download_url")]
    if not any(_matches_repo(candidate or "", owner, repo) for candidate in candidates):
        return None
    stats = _get(f"https://pypistats.org/api/packages/{quote(repo, safe='')}/recent")
    count = ((stats or {}).get("data") or {}).get("last_month")
    if not isinstance(count, int):
        return None
    return {"registry": "pypi", "package": repo, "count": count, "metric": "downloads_last_month",
            "matched_via": "PyPI project_urls/home_page resolves to this GitHub owner/repo"}


def docker_lookup(owner: str, repo: str) -> dict | None:
    namespace, name = owner.lower(), repo.lower()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?", namespace) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?", name):
        return None
    data = _get(f"https://hub.docker.com/v2/repositories/{namespace}/{name}/")
    if not data:
        return None
    pulls = data.get("pull_count")
    if not isinstance(pulls, int):
        return None
    return {"registry": "docker", "package": f"{namespace}/{name}", "count": pulls, "metric": "pulls_total",
            "matched_via": "namespace/name matches this GitHub owner/repo (Docker Hub's public API "
                           "has no independent cross-check field; weaker evidence than npm/PyPI)"}


LOOKUPS = (npm_lookup, pypi_lookup, docker_lookup)


def _engine_digest() -> str:
    return digest({
        "derive_usage": (ROOT / "tools/derive_usage.py").read_text(encoding="utf-8"),
        "usage": (ROOT / "awesome/usage.py").read_text(encoding="utf-8"),
    })


@contextmanager
def writer_lock():
    path = ROOT / ".agent-runs/usage-crawler.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError("Usage crawler writer lock exists; inspect its owner before recovery") from None
    try:
        with handle:
            json.dump({"pid": os.getpid(), "started_at": now()}, handle)
            handle.flush()
        yield
    finally:
        path.unlink()


def checkpoint_save(path: Path, state: dict) -> None:
    atomic_json(path, {**state, "checkpoint_digest": digest(state)})


def checkpoint_load(path: Path) -> dict:
    state = json.loads(path.read_text(encoding="utf-8"))
    checksum = state.pop("checkpoint_digest", None)
    if checksum != digest(state) or state.get("engine_digest") != _engine_digest():
        raise ValueError("Checkpoint or engine changed; start a new usage run")
    return state


def load_project_catalogue(data_root: Path) -> tuple[dict, dict]:
    data = json.loads((data_root / "project-index.json").read_text(encoding="utf-8"))
    return data, load_projects(data, data_root)


def load_usage(data: dict, data_root: Path) -> dict:
    return {prefix: json.loads((data_root / shard_path(prefix)).read_text(encoding="utf-8"))
            for prefix in data.get("shards", {})}


def select_candidates(data_root: Path, limit: int, already_have: set[str]) -> list[dict]:
    _, shards = load_project_catalogue(data_root)
    candidates = []
    for shard in shards.values():
        for record in shard["projects"]:
            if record["id"] in already_have:
                continue
            repo_pair = github_repo(record["url"])
            if not repo_pair:
                continue
            candidates.append({"id": record["id"], "url": record["url"], "owner": repo_pair[0],
                                "repo": repo_pair[1], "list_count": record["list_count"]})
    candidates.sort(key=lambda c: (-c["list_count"], c["url"]))
    return candidates[:limit]


def _existing_records(data_root: Path) -> dict:
    index_path = data_root / "usage-index.json"
    if not index_path.exists():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    shards = load_usage(data, data_root)
    return {record["id"]: record for shard in shards.values() for record in shard["projects"]}


def _publish_shape(records: dict[str, dict], generated_at: str) -> dict:
    buckets: dict[str, list[dict]] = {}
    for record in sorted(records.values(), key=lambda r: r["id"]):
        buckets.setdefault(record["id"][:2], []).append(record)
    shards = {}
    for prefix, bucket_records in buckets.items():
        shard = {"format_version": FORMAT, "prefix": prefix, "projects": bucket_records}
        shard["digest"] = digest(shard)
        shards[prefix] = shard
    top_index = {"format_version": FORMAT, "generated_at": generated_at, "content_policy": CONTENT_POLICY,
                 "counts": {"projects": len(records), "shards": len(shards)},
                 "shards": {prefix: shard["digest"] for prefix, shard in shards.items()}}
    top_index["digest"] = digest(top_index)
    return {"index": top_index, "shards": shards}


def build(run_id: str = "usage", batch_size: int = BATCH_SIZE_DEFAULT, interrupt_after: int | None = None,
          data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging",
          checkpoint_root: Path = ROOT / ".agent-runs/usage") -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id):
        raise ValueError("Run ID must be 1-64 lowercase letters, digits or hyphens")
    load_list_index(data_root)
    with writer_lock():
        path = checkpoint_root / run_id / "checkpoint.json"
        existing = _existing_records(data_root)
        if path.exists():
            state = checkpoint_load(path)
        else:
            candidates = select_candidates(data_root, batch_size, set(existing))
            state = {"schema_version": 1, "engine_digest": _engine_digest(), "generated_at": now(),
                      "candidates": candidates, "completed": {}, "skipped": {}}
            checkpoint_save(path, state)
        processed = 0
        for candidate in state["candidates"]:
            pid = candidate["id"]
            if pid in state["completed"] or pid in state["skipped"]:
                continue
            owner, repo_name = candidate["owner"], candidate["repo"]
            sources = [source for lookup in LOOKUPS if (source := lookup(owner, repo_name)) is not None]
            if not sources:
                state["skipped"][pid] = "no verified registry match for this candidate package name"
                checkpoint_save(path, state)
                continue
            state["completed"][pid] = {"id": pid, "url": candidate["url"], "owner": owner, "repo": repo_name,
                                        "sources": sources, "observed_at": now()}
            checkpoint_save(path, state)
            processed += 1
            print(f"Checkpoint: {owner}/{repo_name} ({len(sources)} matched source(s))")
            if interrupt_after is not None and processed >= interrupt_after:
                raise InterruptedError("Injected interruption after durable usage checkpoint; published artifact untouched")
        merged = {**existing, **state["completed"]}
        published = _publish_shape(merged, state["generated_at"])
        validate_usage(published["index"], published["shards"])
        for prefix, shard in published["shards"].items():
            atomic_json(staging_root / shard_path(prefix), shard)
        atomic_json(staging_root / "usage-index.json", published["index"])
        return {**published["index"], "run": {"candidates": len(state["candidates"]),
                "completed_this_run": len(state["completed"]), "skipped_this_run": len(state["skipped"])}}


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "usage-index.json").read_text(encoding="utf-8"))
    shards = load_usage(data, staging_root)
    validate_usage(data, shards)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    for prefix, shard in shards.items():
        atomic_json(data_root / shard_path(prefix), shard)
    atomic_json(data_root / "usage-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    data, project_shards = load_project_catalogue(data_root)
    known_ids = {record["id"] for shard in project_shards.values() for record in shard["projects"]}
    index_path = data_root / "usage-index.json"
    if not index_path.exists():
        return {"counts": {"projects": 0, "shards": 0}, "digest": None}
    usage = json.loads(index_path.read_text(encoding="utf-8"))
    shards = load_usage(usage, data_root)
    validate_usage(usage, shards, known_ids)
    return usage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "publish", "validate"])
    parser.add_argument("--expected-digest")
    parser.add_argument("--run-id", default="usage")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--interrupt-after", type=int)
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.run_id, args.batch_size, args.interrupt_after)
    elif args.command == "validate":
        result = validate()
    else:
        if not args.expected_digest:
            parser.error("publish requires --expected-digest after review")
        result = publish(args.expected_digest)
    print(json.dumps({"counts": result["counts"], "digest": result["digest"]}))


if __name__ == "__main__":
    main()
