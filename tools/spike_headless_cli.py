"""H1 spike (issue #53's Epic H, "scoped headless-CLI interpretation layer"): a real, non-mocked
measurement of headless-CLI invocation latency and failure rate against real ambiguous `pending`
catalogue candidates, gating H2/H3 exactly as #65 gated A3 (same spike discipline: a real finding,
reported honestly, before any further story in this epic ships beyond the spike -- see issue #53's
acceptance criteria: "The spike's findings ... are recorded before any story in this epic ships
beyond the spike").

Uses the SAME candidate-selection fields, prompt, and JSON Schema H2's `awesome.interpret_eligibility`
module builds for production use (not a synthetic/simplified benchmark prompt) and the SAME
`awesome.headless_cli.invoke` entry point H2/H3 call in production -- this is a genuine dry run of
the real mechanism, at a small, deliberately bounded count (default 8 real calls) chosen so this
spike itself stays affordable against a single subscription session, never hundreds of real calls.

## What this spike CAN verify
- Real observed wall-clock latency per call, end-to-end (subprocess launch through JSON envelope
  received), for the actual CLI on the actual machine this pipeline would run on.
- Real observed failure rate for those calls (non-zero exit, timeout, malformed/off-schema output).
- That the exact production prompt/schema (`awesome.interpret_eligibility`) round-trips
  successfully through the real CLI end-to-end, including `--json-schema`-constrained structured
  output.
- An honest, disclosed EXTRAPOLATION: naive serial wall-clock time for a batch the size of the real
  published `pending` count, assuming per-call latency stays roughly constant at that count.

## What this spike CANNOT verify (see issue #53's own framing of H1)
- Real subscription usage-cap/rate-limit headroom for a sustained run of hundreds of calls. A
  handful of calls from one interactive sandboxed session cannot observe an account-level rolling
  usage window; only a real overnight-sized run against the maintainer's own account (explicitly out
  of scope for a gating spike) or account-level usage data (not available to this session) could
  answer that.
- Whether latency or failure rate stays roughly constant at 100x-1000x the sample count (server-side
  throttling, backoff, or degraded service under sustained load could all change the real per-call
  cost at that scale).
- Real classification ACCURACY -- this spike's schema asks the CLI for a decision; it has no ground
  truth to grade those decisions against. That is a product-quality question for H2's own future
  review, not this spike's cost/reliability question.

The printed/written report always carries its own `verified`/`not_verified` lists (matching the
text above) so a reader never has to trust a human's paraphrase of what ran.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from awesome.headless_cli import DEFAULT_MODEL, DEFAULT_TIMEOUT_S, invoke
from awesome.interpret_eligibility import SCHEMA, build_prompt, candidate_fields
from tools.derive_projects import load_index as load_list_index
from tools.lists import now

ROOT = Path(__file__).resolve().parents[1]

VERIFIED = [
    "Real observed per-call wall-clock latency for the actual headless CLI on this machine.",
    "Real observed failure rate for this sample (non-zero exit / timeout / malformed or "
    "off-schema output).",
    "The exact production prompt/schema (awesome.interpret_eligibility) round-trips successfully "
    "through the real CLI end-to-end, including --json-schema-constrained structured output.",
]
NOT_VERIFIED = [
    "Real subscription usage-cap / rate-limit headroom for a sustained hundreds-of-calls overnight "
    "run -- not observable from a handful of calls in one sandboxed session.",
    "Whether latency or failure rate stays roughly constant at the real pending-count scale "
    "(100-1000x this sample).",
    "Classification accuracy/quality of the CLI's eligibility opinions (no ground truth available "
    "to this spike).",
]


def load_detail(item: dict, data_root: Path) -> dict | None:
    if not item.get("detail"):
        return None
    path = data_root / item["detail"]
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def select_sample(data_root: Path, count: int) -> list[dict]:
    """A reproducible, non-cherry-picked sample: every published `pending` list WITH a parsed
    README (a real ambiguous case, not a "no content at all" case H2 could never meaningfully
    interpret), sorted by id for a stable order, then an even stride across that sorted population
    so the sample spans the whole `pending` population rather than only its first/highest-star
    entries -- same "don't cherry-pick" discipline issue #65 used for its own validation sample."""
    index = load_list_index(data_root)
    pending = sorted((item for item in index["lists"] if item["state"] == "pending" and item.get("detail")),
                      key=lambda item: item["id"])
    if not pending:
        return []
    count = min(count, len(pending))
    stride = max(1, len(pending) // count)
    picked = [pending[i] for i in range(0, len(pending), stride)][:count]
    sample = []
    for item in picked:
        detail = load_detail(item, data_root)
        sample.append({"list_id": item["id"], "name": item["name"], "fields": candidate_fields(item, detail)})
    return sample


def run_spike(count: int = 8, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT_S,
              data_root: Path = ROOT / "data", cli: str = "claude") -> dict:
    sample = select_sample(data_root, count)
    pending_total = None
    index_path = data_root / "list-index.json"
    if index_path.exists():
        pending_total = json.loads(index_path.read_text(encoding="utf-8")).get("counts", {}).get("pending")

    calls = []
    wall_started = time.monotonic()
    for candidate in sample:
        prompt = build_prompt(candidate["fields"])
        result = invoke(prompt, SCHEMA, model=model, cli=cli, timeout=timeout)
        calls.append({"list_id": candidate["list_id"], "name": candidate["name"], **result})
        status = "ok" if result.get("ok") else f"FAILED: {result.get('error')}"
        print(f"[{len(calls)}/{len(sample)}] {candidate['name']}: {status} ({result.get('latency_ms')} ms)",
              flush=True)
    wall_elapsed_s = time.monotonic() - wall_started

    latencies_ms = [c["latency_ms"] for c in calls if c.get("latency_ms") is not None]
    successes = [c for c in calls if c.get("ok")]
    failures = [c for c in calls if not c.get("ok")]
    mean_latency_s = (statistics.mean(latencies_ms) / 1000) if latencies_ms else None

    report = {
        "spike": "H1", "issue": 53, "generated_at": now(), "model": model, "cli": cli,
        "sample_size": len(calls), "successes": len(successes), "failures": len(failures),
        "failure_rate": round(len(failures) / len(calls), 4) if calls else None,
        "latency_ms": {
            "mean": round(statistics.mean(latencies_ms), 1) if latencies_ms else None,
            "median": round(statistics.median(latencies_ms), 1) if latencies_ms else None,
            "min": min(latencies_ms) if latencies_ms else None,
            "max": max(latencies_ms) if latencies_ms else None,
        },
        "observed_wall_clock_s": round(wall_elapsed_s, 2),
        "pending_total_at_run_time": pending_total,
        "extrapolation": {
            "method": "naive serial: mean_observed_latency_s * pending_total_at_run_time",
            "estimated_serial_wall_clock_hours": (
                round(mean_latency_s * pending_total / 3600, 2)
                if mean_latency_s and pending_total else None),
            "caveat": "Assumes per-call latency stays roughly constant at 100-1000x this sample's "
                      "size and that calls run strictly serially (matching this pipeline's own "
                      "single-writer design, tools/run_pipeline.py); neither assumption is "
                      "independently verified by this spike -- see 'not_verified' below.",
        },
        "verified": VERIFIED,
        "not_verified": NOT_VERIFIED,
        "calls": calls,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--cli", default="claude")
    parser.add_argument("--out", help="Path to write the full JSON report (default: "
                         ".agent-runs/epic-h/h1-spike-<UTC timestamp>.json, git-ignored scratch)")
    args = parser.parse_args()
    report = run_spike(args.count, args.model, args.timeout, cli=args.cli)
    out = Path(args.out) if args.out else (
        ROOT / ".agent-runs/epic-h" / f"h1-spike-{now().replace(':', '').replace('+00:00', 'Z')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in
               ("sample_size", "successes", "failures", "failure_rate", "latency_ms",
                "observed_wall_clock_s", "extrapolation")}
    summary["report_path"] = str(out)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
