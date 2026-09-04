"""Local-only offline derivation of the D1 network exploration artifact. Never imported by the
hosted UI.

Sibling tool to `tools/derive_search_index.py`, reusing its stage/validate/publish discipline
(stage under `data/staging/`, validate, promote to `data/` only after an explicit reviewed digest --
see `docs/demo/list-data.md`). Streams the already-published `data/projects/<prefix>.json` shards
one at a time into `awesome.network.NetworkAccumulator` -- never holding the full corpus in memory
at once -- to compute D1's two derived signals (hub projects, list-to-list similarity/near-duplicate
detection; see `awesome/network.py`'s module docstring for the full methodology and threshold
provenance), then publishes a single `data/network-index.json`.

Unsharded, unlike `data/projects/` or `data/search/`: at this catalogue's real scale (932,511
projects, 6,377 eligible lists, measured while building this tool), the published artifact holds at
most 100 hub project rows and 32,820 list-pair rows (`MIN_SHARED_PROJECTS = 5` in
`awesome/network.py`) -- a few megabytes, nowhere near GitHub's 100 MB single-file limit that forced
`data/projects/` and `data/search/` into 256 shards each. Re-sharding this artifact only becomes
necessary if the published thresholds are loosened enough to change that order of magnitude; if that
happens, follow the exact prefix-bucketing pattern `awesome.projects.shard_path` established rather
than inventing a new one.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from awesome.network import NetworkAccumulator, validate_network
from awesome.projects import shard_path as project_shard_path, validate_shard as validate_project_shard
from tools.derive_projects import load_index as load_list_index
from tools.derive_search_index import load_project_index
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


def stage(data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging") -> dict:
    list_index = load_list_index(data_root)
    project_index = load_project_index(data_root)
    accumulator = NetworkAccumulator()
    for prefix, expected_digest in project_index.get("shards", {}).items():
        shard = json.loads((data_root / project_shard_path(prefix)).read_text(encoding="utf-8"))
        if shard.get("digest") != expected_digest:
            raise ValueError("Project shard digest does not match the published project index")
        validate_project_shard(shard, prefix, list_index)
        for record in shard["projects"]:
            accumulator.add_project(record)
        del shard  # one shard resident at a time; corpus never fully loaded
    network = accumulator.finalize(project_index["digest"], now())
    validate_network(network, project_index)
    atomic_json(staging_root / "network-index.json", network)
    return network


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "network-index.json").read_text(encoding="utf-8"))
    project_index = load_project_index(data_root)
    validate_network(data, project_index)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    atomic_json(data_root / "network-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    project_index = load_project_index(data_root)
    data = json.loads((data_root / "network-index.json").read_text(encoding="utf-8"))
    validate_network(data, project_index)
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
