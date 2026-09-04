"""Local-only derivation of H3's headless-CLI-assisted entry-level topic-normalization overlay
(issue #53, Epic H). Never imported by hosted UI -- purely an offline input to
`tools/derive_search_index.py`'s optional `topic-interpretations.json` overlay (see
`awesome.topics.normalize_topic`'s `overrides` parameter), which the deterministic `_SYNONYMS`
table always takes precedence over (see `awesome/interpret_topics.py`'s module docstring). Run
manually/on-demand alongside `tools/derive_search_index.py`, the same way `tools/derive_liveness.py`
and `tools/derive_network.py` already run outside `tools/run_pipeline.py`'s fixed sequence (see
`docs/demo/list-data.md`) -- H3 feeds A3/A4's existing search-index derivation, not the list-crawl
wrapper H2 hooks into.

Candidate raw category labels are collected by a single streaming pass over the already-published
project corpus (`data/projects/<prefix>.json`, one shard at a time -- same discipline as
`awesome/network.py`'s `NetworkAccumulator`, never the full 900k+-project corpus in memory at once),
keeping only the labels `awesome.topics.normalize_topic` cannot already resolve via `_SYNONYMS`.
Each distinct label is invoked at most once EVER (cached forever by its own label text, since a raw
label string's own meaning never changes) -- unlike H2's per-repository interpretation, there is no
staleness/re-invocation trigger here once a label has been classified.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

from awesome.catalogue import digest
from awesome.headless_cli import DEFAULT_MODEL, DEFAULT_TIMEOUT_S
from awesome.headless_cli import engine_digest as cli_engine_digest
from awesome.headless_cli import invoke as cli_invoke
from awesome.interpret_topics import (CONTENT_POLICY, FORMAT, SCHEMA, build_prompt, label_digest,
                                       normalized_label, validate_interpretations)
from awesome.projects import shard_path as project_shard_path
from awesome.topics import _SYNONYMS
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE_DEFAULT = 50  # see tools/derive_interpretations.py's docstring: sized from H1's real measurement


def _engine_digest() -> str:
    return digest({
        "derive_topic_interpretations": (ROOT / "tools/derive_topic_interpretations.py").read_text(encoding="utf-8"),
        "interpret_topics": (ROOT / "awesome/interpret_topics.py").read_text(encoding="utf-8"),
        "topics": (ROOT / "awesome/topics.py").read_text(encoding="utf-8"),
        "headless_cli": cli_engine_digest(),
    })


def _invoke(prompt: str, schema: dict, model: str, timeout: int) -> dict:
    return cli_invoke(prompt, schema, model=model, timeout=timeout)


@contextmanager
def writer_lock():
    path = ROOT / ".agent-runs/headless-topic-interpretation.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError("Headless topic interpretation writer lock exists; inspect its owner before recovery") from None
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
        raise ValueError("Checkpoint or engine changed; start a new topic interpretation run")
    return state


def collect_unmapped_labels(data_root: Path, project_index: dict) -> list[str]:
    """Single streaming pass over every published project shard, collecting distinct normalized
    label-keys `_SYNONYMS` does not already resolve. Deterministic, reproducible order: shard
    prefixes visited in sorted order, first-seen label order within/across shards."""
    seen: dict[str, None] = {}
    for prefix in sorted(project_index.get("shards", {})):
        shard = json.loads((data_root / project_shard_path(prefix)).read_text(encoding="utf-8"))
        for record in shard["projects"]:
            for occurrence in record["occurrences"]:
                key = normalized_label(occurrence.get("category", ""))
                if key and key not in _SYNONYMS and key not in seen:
                    seen[key] = None
    return list(seen)


def select_candidates(data_root: Path, limit: int, already_have: set) -> list[dict]:
    project_index_path = data_root / "project-index.json"
    if not project_index_path.exists():
        return []
    project_index = json.loads(project_index_path.read_text(encoding="utf-8"))
    labels = collect_unmapped_labels(data_root, project_index)
    candidates = [{"label": label, "label_digest": label_digest(label)}
                  for label in sorted(labels) if label not in already_have]
    return candidates[:limit]


def _existing_records(data_root: Path) -> dict:
    path = data_root / "topic-interpretations.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {record["label"]: record for record in data.get("records", [])}


def _publish_shape(records: dict, generated_at: str) -> dict:
    ordered = sorted(records.values(), key=lambda r: r["label"])
    data = {"format_version": FORMAT, "generated_at": generated_at, "content_policy": CONTENT_POLICY,
            "counts": {"records": len(ordered)}, "records": ordered}
    data["digest"] = digest(data)
    return data


def build(run_id: str = "topic-interpretation", batch_size: int = BATCH_SIZE_DEFAULT,
          interrupt_after: int | None = None, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT_S,
          data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging",
          checkpoint_root: Path = ROOT / ".agent-runs/headless-topic-interpretation") -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id):
        raise ValueError("Run ID must be 1-64 lowercase letters, digits or hyphens")
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
            key = candidate["label"]
            if key in state["completed"] or key in state["skipped"]:
                continue
            prompt = build_prompt(key)
            try:
                result = _invoke(prompt, SCHEMA, model, timeout)
            except OSError as error:
                stopped_early = f"{type(error).__name__}: {error}"
                break
            if not result.get("ok"):
                state["skipped"][key] = result.get("error", "headless CLI call failed")
                checkpoint_save(path, state)
                continue
            output = result["output"]
            record = {"label": key, "label_digest": candidate["label_digest"], "tag": output["tag"],
                       "confidence": output["confidence"], "model": result.get("model", model),
                       "source": "headless-cli", "invoked_at": now(), "latency_ms": result.get("latency_ms")}
            state["completed"][key] = record
            checkpoint_save(path, state)
            processed += 1
            print(f"Checkpoint: {key!r}", flush=True)
            if interrupt_after is not None and processed >= interrupt_after:
                raise InterruptedError("Injected interruption after durable topic-interpretation checkpoint; published artifact untouched")
        if stopped_early:
            print(f"Batch stopped early ({stopped_early}); staging {len(state['completed'])} completed record(s) so far.")
        merged = {**existing, **state["completed"]}
        published = _publish_shape(merged, state["generated_at"])
        validate_interpretations(published)
        atomic_json(staging_root / "topic-interpretations.json", published)
        return {**published, "run": {"candidates": len(state["candidates"]),
                "completed_this_run": len(state["completed"]), "skipped_this_run": len(state["skipped"])}}


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "topic-interpretations.json").read_text(encoding="utf-8"))
    validate_interpretations(data)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    atomic_json(data_root / "topic-interpretations.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    path = data_root / "topic-interpretations.json"
    if not path.exists():
        return {"counts": {"records": 0}, "digest": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_interpretations(data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "publish", "validate"])
    parser.add_argument("--expected-digest")
    parser.add_argument("--run-id", default="topic-interpretation")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--interrupt-after", type=int)
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.run_id, args.batch_size, args.interrupt_after, args.model, args.timeout)
    elif args.command == "validate":
        result = validate()
    else:
        if not args.expected_digest:
            parser.error("publish requires --expected-digest after review")
        result = publish(args.expected_digest)
    print(json.dumps({"counts": result["counts"], "digest": result["digest"]}))


if __name__ == "__main__":
    main()
