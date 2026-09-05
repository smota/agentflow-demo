"""Local-only offline aggregation of the session-record ledger. Never imported by hosted UI.

Sibling tool to `tools/derive_projects.py`, reusing its publication discipline (stage under
`data/staging/`, validate, then promote to `data/` only after an explicit reviewed digest). Unlike
the project catalogue, `data/sessions/<id>.json` records are individually authored/generated (by
`scripts/derive-session-record.mjs` or by hand for a rollup) and committed directly -- there is
nothing to crawl or shard at this scale (dozens of records, not hundreds of thousands). This tool's
only job is computing the derived `data/sessions-index.json` aggregate: a sorted timeline plus
precomputed harness-comparison / SDLC-conformance / tests-over-time rollups, so
`awesome/delivery.py` never recomputes them in the hosted request path (see `docs/demo/list-data.md`
for the same "no heavy computation in the hosted request path" principle applied elsewhere).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from awesome.sessions import derive_index, load_records, validate_index
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


def stage(data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging") -> dict:
    records = load_records(data_root)
    index = derive_index(records, generated_at=now())
    validate_index(index, records)
    atomic_json(staging_root / "sessions-index.json", index)
    return index


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    index = json.loads((staging_root / "sessions-index.json").read_text(encoding="utf-8"))
    records = load_records(data_root)
    validate_index(index, records)
    if index["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    atomic_json(data_root / "sessions-index.json", index)
    return index


def validate(data_root: Path = ROOT / "data") -> dict:
    records = load_records(data_root)
    index = json.loads((data_root / "sessions-index.json").read_text(encoding="utf-8"))
    validate_index(index, records)
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
