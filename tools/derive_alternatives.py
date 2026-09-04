"""Local-only derivation of the "see alternatives" same-heading co-occurrence structure (E4/#73).

Never imported by hosted UI. Sibling tool to `tools/derive_projects.py`, reusing its exact
staging/publish/validate discipline and its exact inputs (`data/list-index.json` and its `eligible`
detail shards) -- no new crawling, no network calls of any kind. Unlike E2 (liveness) and E3
(usage), this derivation is pure data transformation, so a single run covers the full current
catalogue, not a bounded batch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from awesome.alternatives import derive_alternatives, shard_path, validate_alternatives
from tools.derive_projects import load_details, load_index
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


def load_alternatives(data: dict, data_root: Path) -> dict:
    """Load every shard the published alternatives-index registry refers to."""
    return {prefix: json.loads((data_root / shard_path(prefix)).read_text(encoding="utf-8"))
            for prefix in data.get("shards", {})}


def stage(data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging") -> dict:
    index = load_index(data_root)
    details = load_details(index, data_root)
    derived = derive_alternatives(index, details, generated_at=now())
    validate_alternatives(derived["index"], index, derived["shards"])
    for prefix, shard in derived["shards"].items():
        atomic_json(staging_root / shard_path(prefix), shard)
    atomic_json(staging_root / "alternatives-index.json", derived["index"])
    return derived["index"]


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "alternatives-index.json").read_text(encoding="utf-8"))
    index = load_index(data_root)
    shards = load_alternatives(data, staging_root)
    validate_alternatives(data, index, shards)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    for prefix, shard in shards.items():
        atomic_json(data_root / shard_path(prefix), shard)
    atomic_json(data_root / "alternatives-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    index = load_index(data_root)
    data = json.loads((data_root / "alternatives-index.json").read_text(encoding="utf-8"))
    shards = load_alternatives(data, data_root)
    validate_alternatives(data, index, shards)
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
