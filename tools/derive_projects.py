"""Local-only derivation of the project<->list dedup structure. Never imported by hosted UI.

Sibling tool to `tools/lists.py`, reusing its publication discipline (stage under `data/staging/`,
validate, then promote to `data/` only after an explicit reviewed digest -- see
`docs/demo/list-data.md`). Unlike the GitHub crawl in `tools/lists.py`, this is a bounded,
deterministic re-read of already-published local data (`data/list-index.json` and its `eligible`
detail shards): there is no network call and nothing to checkpoint/resume, so it intentionally does
not carry that module's `Run`/checkpoint machinery. It refuses to run against a `list-index.json`
that fails `awesome.lists.validate_index`.

The published output is sharded the same way `data/lists/` is: a tiny `data/project-index.json`
(counts plus a prefix -> shard-digest map only -- even a summary-only row per project would exceed
GitHub's single-file size limit at this catalogue's scale) plus `data/projects/<2-hex-prefix>.json`
shard files, bucketed by project id prefix, holding every per-project field.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from awesome.lists import validate_index
from awesome.projects import derive_projects, shard_path, validate_projects
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


def load_index(data_root: Path) -> dict:
    index = json.loads((data_root / "list-index.json").read_text(encoding="utf-8"))
    validate_index(index, data_root)
    return index


def load_details(index: dict, data_root: Path) -> dict:
    details = {}
    for item in index["lists"]:
        if item.get("state") == "eligible" and item.get("detail"):
            details[item["detail"]] = json.loads((data_root / item["detail"]).read_text(encoding="utf-8"))
    return details


def load_projects(data: dict, data_root: Path) -> dict:
    """Load every shard the published project-index registry refers to."""
    return {prefix: json.loads((data_root / shard_path(prefix)).read_text(encoding="utf-8"))
            for prefix in data.get("shards", {})}


def stage(data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging") -> dict:
    index = load_index(data_root)
    details = load_details(index, data_root)
    derived = derive_projects(index, details, generated_at=now())
    validate_projects(derived["index"], index, derived["shards"])
    for prefix, shard in derived["shards"].items():
        atomic_json(staging_root / shard_path(prefix), shard)
    atomic_json(staging_root / "project-index.json", derived["index"])
    return derived["index"]


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "project-index.json").read_text(encoding="utf-8"))
    index = load_index(data_root)
    shards = load_projects(data, staging_root)
    validate_projects(data, index, shards)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    for prefix, shard in shards.items():
        atomic_json(data_root / shard_path(prefix), shard)
    atomic_json(data_root / "project-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    index = load_index(data_root)
    data = json.loads((data_root / "project-index.json").read_text(encoding="utf-8"))
    shards = load_projects(data, data_root)
    validate_projects(data, index, shards)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["stage", "publish", "validate"])
    parser.add_argument("--expected-digest")
    args = parser.parse_args()
    if args.command == "stage":
        result = stage()
    elif args.command == "validate":
        result = validate()
    else:
        if not args.expected_digest:
            parser.error("--expected-digest required after reviewing staged content")
        result = publish(args.expected_digest)
    print(json.dumps({"counts": result["counts"], "digest": result["digest"]}))


if __name__ == "__main__":
    main()
