"""Local-only derivation of H2's headless-CLI-assisted eligibility interpretation artifact (issue
#53, Epic H). Never imported by hosted UI -- the hosted app's zero-model-dependency guarantee is
unaffected; this module runs only as an optional, offline pipeline stage (see
`tools/run_pipeline.py --enable-cli-interpretation`, off by default).

Mirrors `tools/derive_liveness.py`'s checkpoint/writer-lock/batch discipline for a slow, externally
rate-limited call: candidates are the published `pending` lists in `data/list-index.json` (see
`awesome.interpret_eligibility`'s scope note -- this never touches `list-index.json`'s own `state`),
each invoked at most once per distinct `candidate_digest`; an unchanged candidate is never
re-invoked across runs (issue #53's caching requirement), and the published artifact grows/updates
incrementally across repeated runs exactly like liveness does.

`BATCH_SIZE_DEFAULT` is set from H1's real measurement (issue #53's gating spike,
`tools/spike_headless_cli.py`): 8 real production-prompt calls against real `pending` candidates
observed a mean latency of ~11.6s/call (median 11.1s, range 7.5-17.6s), 0/8 failures. A batch of 50
therefore costs roughly 10 minutes of wall-clock time appended to an overnight run -- a small,
affordable slice of an unattended overnight window, not the full ~1,431-candidate backlog (H1's own
honest extrapolation put a full serial pass at ~4.6 hours; H1 explicitly could NOT verify real
subscription rate-limit headroom for that scale from a sandboxed few-call test, so a conservative
per-run batch, not a single one-shot full pass, is the deliberate choice here).
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
from awesome.interpret_eligibility import (CONTENT_POLICY, FORMAT, SCHEMA, build_prompt,
                                            candidate_digest, candidate_fields,
                                            validate_interpretations)
from tools.derive_projects import load_index as load_list_index
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE_DEFAULT = 50  # see module docstring: sized from H1's real measured per-call latency


def _engine_digest() -> str:
    return digest({
        "derive_interpretations": (ROOT / "tools/derive_interpretations.py").read_text(encoding="utf-8"),
        "interpret_eligibility": (ROOT / "awesome/interpret_eligibility.py").read_text(encoding="utf-8"),
        "headless_cli": cli_engine_digest(),
    })


def _invoke(prompt: str, schema: dict, model: str, timeout: int) -> dict:
    """A thin, monkeypatchable seam over `awesome.headless_cli.invoke` -- tests replace this, never
    the real CLI, matching `tools/derive_liveness.py`'s own `_fetch` seam."""
    return cli_invoke(prompt, schema, model=model, timeout=timeout)


@contextmanager
def writer_lock():
    path = ROOT / ".agent-runs/headless-interpretation.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError("Headless interpretation writer lock exists; inspect its owner before recovery") from None
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
        raise ValueError("Checkpoint or engine changed; start a new interpretation run")
    return state


def load_detail(item: dict, data_root: Path) -> dict | None:
    if not item.get("detail"):
        return None
    path = data_root / item["detail"]
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def select_candidates(data_root: Path, limit: int, already_have: dict) -> list[dict]:
    """Every currently published `pending` list not already covered by an up-to-date cached
    interpretation (`already_have`: list_id -> candidate_digest already on file), highest-stars
    first so a bounded batch covers the most-visible ambiguous cases first -- same prioritization
    discipline as `tools/derive_liveness.py`'s `select_candidates`."""
    index = load_list_index(data_root)
    candidates = []
    for item in index["lists"]:
        if item["state"] != "pending":
            continue
        detail = load_detail(item, data_root)
        fields = candidate_fields(item, detail)
        this_digest = candidate_digest(fields)
        if already_have.get(item["id"]) == this_digest:
            continue
        candidates.append({"list_id": item["id"], "name": item["name"], "stars": item.get("stars") or 0,
                            "fields": fields, "candidate_digest": this_digest})
    candidates.sort(key=lambda c: (-c["stars"], c["list_id"]))
    return candidates[:limit]


def _existing_records(data_root: Path) -> dict:
    path = data_root / "interpretations-index.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {record["list_id"]: record for record in data.get("records", [])}


def _publish_shape(records: dict, generated_at: str) -> dict:
    ordered = sorted(records.values(), key=lambda r: r["list_id"])
    data = {"format_version": FORMAT, "generated_at": generated_at, "content_policy": CONTENT_POLICY,
            "counts": {"records": len(ordered)}, "records": ordered}
    data["digest"] = digest(data)
    return data


def build(run_id: str = "interpretation", batch_size: int = BATCH_SIZE_DEFAULT,
          interrupt_after: int | None = None, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT_S,
          data_root: Path = ROOT / "data", staging_root: Path = ROOT / "data/staging",
          checkpoint_root: Path = ROOT / ".agent-runs/headless-interpretation") -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id):
        raise ValueError("Run ID must be 1-64 lowercase letters, digits or hyphens")
    with writer_lock():
        path = checkpoint_root / run_id / "checkpoint.json"
        existing = _existing_records(data_root)
        already_have = {list_id: record["candidate_digest"] for list_id, record in existing.items()}
        if path.exists():
            state = checkpoint_load(path)
        else:
            candidates = select_candidates(data_root, batch_size, already_have)
            state = {"schema_version": 1, "engine_digest": _engine_digest(), "generated_at": now(),
                      "candidates": candidates, "completed": {}, "skipped": {}}
            checkpoint_save(path, state)
        processed = 0
        stopped_early = None
        for candidate in state["candidates"]:
            list_id = candidate["list_id"]
            if list_id in state["completed"] or list_id in state["skipped"]:
                continue
            prompt = build_prompt(candidate["fields"])
            try:
                result = _invoke(prompt, SCHEMA, model, timeout)
            except OSError as error:
                # A real environment failure launching the CLI process -- stop the batch here
                # rather than burn through many guaranteed-to-fail calls; the checkpoint already
                # has every prior candidate durably saved (mirrors tools/derive_liveness.py's own
                # RuntimeError/OSError stop discipline).
                stopped_early = f"{type(error).__name__}: {error}"
                break
            if not result.get("ok"):
                # An ordinary per-candidate failure (non-zero exit, timeout, off-schema output):
                # skip and continue the batch so one bad candidate never stalls the unattended run
                # (issue #53's own requirement); recorded so it is retried on a future run rather
                # than silently dropped.
                state["skipped"][list_id] = result.get("error", "headless CLI call failed")
                checkpoint_save(path, state)
                continue
            output = result["output"]
            record = {"list_id": list_id, "name": candidate["name"],
                       "candidate_digest": candidate["candidate_digest"], "eligible": output["eligible"],
                       "confidence": output["confidence"], "reasoning": output["reasoning"][:1000],
                       "model": result.get("model", model), "source": "headless-cli",
                       "invoked_at": now(), "latency_ms": result.get("latency_ms")}
            state["completed"][list_id] = record
            checkpoint_save(path, state)
            processed += 1
            print(f"Checkpoint: {candidate['name']}", flush=True)
            if interrupt_after is not None and processed >= interrupt_after:
                raise InterruptedError("Injected interruption after durable interpretation checkpoint; published artifact untouched")
        if stopped_early:
            print(f"Batch stopped early ({stopped_early}); staging {len(state['completed'])} completed record(s) so far.")
        merged = {**existing, **state["completed"]}
        published = _publish_shape(merged, state["generated_at"])
        list_index = load_list_index(data_root)
        validate_interpretations(published, list_index)
        atomic_json(staging_root / "interpretations-index.json", published)
        return {**published, "run": {"candidates": len(state["candidates"]),
                "completed_this_run": len(state["completed"]), "skipped_this_run": len(state["skipped"])}}


def publish(expected_digest: str, data_root: Path = ROOT / "data",
            staging_root: Path = ROOT / "data/staging") -> dict:
    data = json.loads((staging_root / "interpretations-index.json").read_text(encoding="utf-8"))
    list_index = load_list_index(data_root)
    validate_interpretations(data, list_index)
    if data["digest"] != expected_digest:
        raise ValueError("Stale publication candidate")
    atomic_json(data_root / "interpretations-index.json", data)
    return data


def validate(data_root: Path = ROOT / "data") -> dict:
    path = data_root / "interpretations-index.json"
    if not path.exists():
        return {"counts": {"records": 0}, "digest": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    list_index = load_list_index(data_root)
    validate_interpretations(data, list_index)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "publish", "validate"])
    parser.add_argument("--expected-digest")
    parser.add_argument("--run-id", default="interpretation")
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
