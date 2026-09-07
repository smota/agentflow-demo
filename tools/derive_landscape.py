"""Local-only offline derivation of the landscape artifact. Never imported by the hosted UI.

Sibling of `tools/derive_network.py`: stage / publish / validate, stage under `data/staging/`,
promote only after explicit `--expected-digest`, `atomic_json`. Streams published
`data/projects/<prefix>.json` one shard at a time through `LandscapeAccumulator` — never holding
the corpus. Layout (`awesome.landscape_layout`) runs on the published Jaccard graph only.

Not part of `tools/run_pipeline.py` (same as `derive_network`).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from awesome.landscape import LandscapeAccumulator, shard_path, validate_landscape
from awesome.landscape_layout import layout_landscape
from awesome.network import validate_network
from awesome.projects import shard_path as project_shard_path, validate_shard as validate_project_shard
from tools.derive_projects import load_index as load_list_index
from tools.derive_search_index import load_project_index
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


def load_network(data_root: Path, project_index: dict) -> dict:
    data = json.loads((data_root / "network-index.json").read_text(encoding="utf-8"))
    validate_network(data, project_index)
    return data


def load_shards(index: dict, root: Path) -> dict:
    return {prefix: json.loads((root / shard_path(prefix)).read_text(encoding="utf-8"))
            for prefix in index.get("shards", {})}


def stage(data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging") -> dict:
    list_index = load_list_index(data_root)
    project_index = load_project_index(data_root)
    network = load_network(data_root, project_index)
    accumulator = LandscapeAccumulator(network["list_pairs"])
    for prefix, expected_digest in project_index.get("shards", {}).items():
        shard = json.loads((data_root / project_shard_path(prefix)).read_text(encoding="utf-8"))
        if shard.get("digest") != expected_digest:
            raise ValueError("Project shard digest does not match the published project index")
        validate_project_shard(shard, prefix, list_index)
        for record in shard["projects"]:
            accumulator.add_project(record)
        del shard
    eligible = [item["id"] for item in list_index["lists"] if item.get("state") == "eligible"]
    layout = layout_landscape(eligible, network["list_pairs"])
    artifact = accumulator.finalize(network, layout, eligible, now())
    index = artifact["index"]
    validate_landscape(index, network, project_index, artifact["shards"])
    landscape_dir = staging_root / "landscape"
    landscape_dir.mkdir(parents=True, exist_ok=True)
    for prefix, shard in artifact["shards"].items():
        atomic_json(staging_root / shard_path(prefix), shard)
    atomic_json(staging_root / "landscape-index.json", index)
    return index


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    index = json.loads((staging_root / "landscape-index.json").read_text(encoding="utf-8"))
    project_index = load_project_index(data_root)
    network = load_network(data_root, project_index)
    shards = load_shards(index, staging_root)
    validate_landscape(index, network, project_index, shards)
    if index["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    (data_root / "landscape").mkdir(parents=True, exist_ok=True)
    for prefix, shard in shards.items():
        atomic_json(data_root / shard_path(prefix), shard)
    atomic_json(data_root / "landscape-index.json", index)
    return index


def validate(data_root: Path = ROOT / "data") -> dict:
    project_index = load_project_index(data_root)
    network = load_network(data_root, project_index)
    index = json.loads((data_root / "landscape-index.json").read_text(encoding="utf-8"))
    shards = load_shards(index, data_root)
    validate_landscape(index, network, project_index, shards)
    return index


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
