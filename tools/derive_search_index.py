"""Local-only offline derivation of the cross-list search index. Never imported by the hosted UI.

Sibling tool to `tools/derive_projects.py`, reusing its stage/validate/publish discipline (stage
under `data/staging/`, validate, promote to `data/` only after an explicit reviewed digest -- see
`docs/demo/list-data.md`). Streams the already-published `data/projects/<prefix>.json` shards one
at a time -- never holding the full corpus (723 MB across 256 shards as of A1/#64) in memory at
once -- to compute each project's entry-level normalized topics (`awesome.topics`, A4) and
copy-lineage-discounted independent citation count (`awesome.copy_lineage`, reusing #65's validated
title-similarity heuristic, A3's redesigned secondary signal), then publishes a much smaller
`data/search-index.json` + `data/search/<prefix>.json` artifact for the hosted "Search projects"
view to load in full each session -- matching this product's "no live computation in the hosted
session" contract; only lightweight text filtering happens live (`awesome/project_search.py`).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from awesome.projects import shard_path as project_shard_path, validate_shard as validate_project_shard
from awesome.search_index import build_top_index, derive_search_shard, shard_path, validate_search_index
from tools.derive_projects import load_index as load_list_index
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


def load_project_index(data_root: Path) -> dict:
    return json.loads((data_root / "project-index.json").read_text(encoding="utf-8"))


def load_search_shards(data: dict, data_root: Path) -> dict:
    return {prefix: json.loads((data_root / shard_path(prefix)).read_text(encoding="utf-8"))
            for prefix in data.get("shards", {})}


def stage(data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging") -> dict:
    list_index = load_list_index(data_root)
    project_index = load_project_index(data_root)
    shard_digests: dict[str, str] = {}
    total_projects = 0
    for prefix, expected_digest in project_index.get("shards", {}).items():
        project_shard = json.loads((data_root / project_shard_path(prefix)).read_text(encoding="utf-8"))
        if project_shard.get("digest") != expected_digest:
            raise ValueError("Project shard digest does not match the published project index")
        validate_project_shard(project_shard, prefix, list_index)
        search_shard = derive_search_shard(project_shard, project_index["digest"])
        atomic_json(staging_root / shard_path(prefix), search_shard)
        shard_digests[prefix] = search_shard["digest"]
        total_projects += len(search_shard["projects"])
        del project_shard, search_shard  # one shard resident at a time; corpus never fully loaded
    top_index = build_top_index(project_index["digest"], now(), shard_digests,
                                 {"projects": total_projects, "shards": len(shard_digests)})
    atomic_json(staging_root / "search-index.json", top_index)
    return top_index


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "search-index.json").read_text(encoding="utf-8"))
    project_index = load_project_index(data_root)
    shards = load_search_shards(data, staging_root)
    validate_search_index(data, project_index, shards)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    for prefix, shard in shards.items():
        atomic_json(data_root / shard_path(prefix), shard)
    atomic_json(data_root / "search-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    project_index = load_project_index(data_root)
    data = json.loads((data_root / "search-index.json").read_text(encoding="utf-8"))
    shards = load_search_shards(data, data_root)
    validate_search_index(data, project_index, shards)
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
