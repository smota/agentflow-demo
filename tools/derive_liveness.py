"""Local-only derivation of the liveness signal (E2/#71). Never imported by hosted UI.

Reads the published project dedup structure (`data/project-index.json` + `data/projects/`, #69),
filters to `github.com/<owner>/<repo>` project URLs, and calls GitHub's own REST API via the
`gh` CLI -- the operator's already-authenticated login, the same pattern `tools/crawl.py` uses, not
a new credential. Unlike E4 (pure computation), this makes real outbound network calls against a
rate-limited API (5,000 requests/hour authenticated) across a catalogue of 900k+ projects, so a
single run intentionally processes a bounded, checkpointed batch rather than the full catalogue --
see `select_candidates` (highest cross-list visibility first) and the module docstring in
`awesome/liveness.py`. The published artifact is designed to grow incrementally across repeated
runs (this session's run, and later unattended runs under Epic G/#52), never to be complete in one
sitting; each run merges onto whatever liveness data is already published rather than replacing it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from awesome.catalogue import digest
from awesome.liveness import (CONTENT_POLICY, FORMAT, MAX_RELEASES_OBSERVED, build_record,
                               github_repo, shard_path, validate_liveness)
from tools.derive_projects import load_index as load_list_index, load_projects
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE_DEFAULT = 300


def _engine_digest() -> str:
    return digest({
        "derive_liveness": (ROOT / "tools/derive_liveness.py").read_text(encoding="utf-8"),
        "liveness": (ROOT / "awesome/liveness.py").read_text(encoding="utf-8"),
    })


def _fetch(endpoint: str):
    """Call `gh api <endpoint>`. Returns the parsed JSON body, or None for a real 404 (the target
    repository was renamed/deleted/made private since it was cited -- an expected, not-erroneous
    outcome at this scale). Raises on authorization/rate-limit boundaries so the batch stops rather
    than burning through many guaranteed-to-fail calls; the checkpoint already saved means a later
    run resumes exactly where this one stopped."""
    for attempt in range(3):
        try:
            result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True,
                                     encoding="utf-8", timeout=45)
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise RuntimeError("GitHub request timed out after three attempts") from None
            time.sleep(2 ** attempt)
            continue
        if result.returncode == 0:
            return json.loads(result.stdout)
        stderr = result.stderr or ""
        if "rate limit" in stderr.lower() or any(code in stderr for code in ("403", "401", "429")):
            raise RuntimeError("GitHub authorization/rate-limit boundary; batch stopped, checkpoint preserved")
        if "404" in stderr or "Not Found" in stderr:
            return None
        if attempt == 2:
            raise RuntimeError(f"GitHub request failed after three attempts: {endpoint}")
        time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable retry state")


@contextmanager
def writer_lock():
    path = ROOT / ".agent-runs/liveness-crawler.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError("Liveness crawler writer lock exists; inspect its owner before recovery") from None
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
        raise ValueError("Checkpoint or engine changed; start a new liveness run")
    return state


def load_project_catalogue(data_root: Path) -> tuple[dict, dict]:
    data = json.loads((data_root / "project-index.json").read_text(encoding="utf-8"))
    shards = load_projects(data, data_root)
    return data, shards


def load_liveness(data: dict, data_root: Path) -> dict:
    return {prefix: json.loads((data_root / shard_path(prefix)).read_text(encoding="utf-8"))
            for prefix in data.get("shards", {})}


def select_candidates(data_root: Path, limit: int, already_have: set[str]) -> list[dict]:
    """Highest cross-list visibility first (by `list_count`, #69's own dedup structure) -- the
    projects a user is statistically most likely to actually view, so a bounded batch buys the most
    coverage where it matters first. Never re-selects a project that already has a published record."""
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
    index_path = data_root / "liveness-index.json"
    if not index_path.exists():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    shards = load_liveness(data, data_root)
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
    top_index = {"format_version": FORMAT, "generated_at": generated_at,
                 "content_policy": CONTENT_POLICY,
                 "counts": {"projects": len(records), "shards": len(shards)},
                 "shards": {prefix: shard["digest"] for prefix, shard in shards.items()}}
    top_index["digest"] = digest(top_index)
    return {"index": top_index, "shards": shards}


def build(run_id: str = "liveness", batch_size: int = BATCH_SIZE_DEFAULT, interrupt_after: int | None = None,
          data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging",
          checkpoint_root: Path = ROOT / ".agent-runs/liveness") -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id):
        raise ValueError("Run ID must be 1-64 lowercase letters, digits or hyphens")
    load_list_index(data_root)  # refuses to run against an invalid published list index
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
        stopped_early = None
        for candidate in state["candidates"]:
            pid = candidate["id"]
            if pid in state["completed"] or pid in state["skipped"]:
                continue
            owner, repo_name = candidate["owner"], candidate["repo"]
            try:
                repo = _fetch(f"repos/{owner}/{repo_name}")
                if repo is None:
                    state["skipped"][pid] = "repository not found (renamed, deleted, or private)"
                    checkpoint_save(path, state)
                    continue
                releases = _fetch(f"repos/{owner}/{repo_name}/releases?per_page={MAX_RELEASES_OBSERVED}") or []
            except (RuntimeError, OSError) as error:
                # A genuine GitHub auth/rate-limit boundary (RuntimeError from _fetch) or a local
                # environment failure spawning `gh` (OSError, e.g. a transient process-creation
                # denial) both stop the batch here rather than crash it -- the checkpoint already
                # has every prior candidate durably saved, so this is never lost progress, and the
                # staged artifact below still publishes everything completed before the stop.
                stopped_early = f"{type(error).__name__}: {error}"
                break
            record = build_record(candidate["url"], owner, repo_name, repo, releases, now())
            state["completed"][pid] = record
            checkpoint_save(path, state)
            processed += 1
            print(f"Checkpoint: {owner}/{repo_name}")
            if interrupt_after is not None and processed >= interrupt_after:
                raise InterruptedError("Injected interruption after durable liveness checkpoint; published artifact untouched")
        if stopped_early:
            print(f"Batch stopped early ({stopped_early}); staging {len(state['completed'])} completed record(s) so far.")
        merged = {**existing, **state["completed"]}
        published = _publish_shape(merged, state["generated_at"])
        validate_liveness(published["index"], published["shards"])
        for prefix, shard in published["shards"].items():
            atomic_json(staging_root / shard_path(prefix), shard)
        atomic_json(staging_root / "liveness-index.json", published["index"])
        return {**published["index"], "run": {"candidates": len(state["candidates"]),
                "completed_this_run": len(state["completed"]), "skipped_this_run": len(state["skipped"])}}


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "liveness-index.json").read_text(encoding="utf-8"))
    shards = load_liveness(data, staging_root)
    validate_liveness(data, shards)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    for prefix, shard in shards.items():
        atomic_json(data_root / shard_path(prefix), shard)
    atomic_json(data_root / "liveness-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    data, project_shards = load_project_catalogue(data_root)
    known_ids = {record["id"] for shard in project_shards.values() for record in shard["projects"]}
    index_path = data_root / "liveness-index.json"
    if not index_path.exists():
        return {"counts": {"projects": 0, "shards": 0}, "digest": None}
    live = json.loads(index_path.read_text(encoding="utf-8"))
    shards = load_liveness(live, data_root)
    validate_liveness(live, shards, known_ids)
    return live


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "publish", "validate"])
    parser.add_argument("--expected-digest")
    parser.add_argument("--run-id", default="liveness")
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
