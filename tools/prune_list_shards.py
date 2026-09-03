"""Digest-bound removal of list shards no longer referenced by an accepted index."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from awesome.lists import validate_index

ROOT = Path(__file__).resolve().parents[1]
SHARD = re.compile(r"[a-f0-9]{64}\.json")


def unused_shards(directory: Path, expected_digest: str) -> list[Path]:
    directory = Path(directory).resolve()
    index = json.loads((directory / "list-index.json").read_text(encoding="utf-8"))
    validate_index(index, directory)
    if index["digest"] != expected_digest:
        raise ValueError("Index digest does not match the accepted publication")
    shard_dir = directory / "lists"
    referenced = {Path(item["detail"]).name for item in index["lists"] if item.get("detail")}
    unused = []
    for path in shard_dir.iterdir():
        if path.is_symlink() or not path.is_file() or not SHARD.fullmatch(path.name):
            raise ValueError("Unexpected object in list shard directory")
        if path.name not in referenced:
            unused.append(path)
    return sorted(unused)


def prune(directory: Path, expected_digest: str, apply: bool = False) -> dict:
    unused = unused_shards(directory, expected_digest)
    result = {"directory": str(Path(directory).resolve()), "files": len(unused),
              "bytes": sum(path.stat().st_size for path in unused), "applied": apply}
    if apply:
        for path in unused:
            path.unlink()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", choices=("data", "data/staging"), required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prune(ROOT / args.directory, args.expected_digest, args.apply), indent=2))


if __name__ == "__main__":
    main()
