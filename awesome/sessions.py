"""Pure derivation and validation for the session-record ledger (schemas/session-record.schema.json).

No networking, no runtime writes -- sibling to `awesome/projects.py`. `data/sessions/<id>.json` are
the raw, individually authored/generated records (one per merged PR, or a `kind: rollup` record for
a multi-PR orchestration run) -- small enough in count (dozens, not hundreds of thousands like the
project catalogue) that they need no sharding. `tools/derive_sessions.py` computes the single
published `data/sessions-index.json` aggregate from them: a sorted timeline plus precomputed rollups
(harness comparison, SDLC-conformance distribution, tests-over-time series) so `awesome/delivery.py`
never has to recompute aggregates in the hosted request path.

Full schema conformance (every session record's exact field shapes, evidence-contract vocabulary,
and cross-checks against its own PR's declared issues) is `scripts/validate-session-record.mjs`'s
job, not this module's -- this module only checks the structural invariants the aggregation itself
depends on (unique ids, resolvable `children` references, and internal count reconciliation), the
same division of labor `awesome/projects.py` keeps with its Node-side PR manifest validator.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

from awesome.catalogue import digest

FORMAT = 1
KINDS = ("pr", "rollup", "release")


def load_records(data_root: Path) -> dict[str, dict]:
    """Load every `data/sessions/<id>.json` record, keyed by filename stem."""
    sessions_dir = data_root / "sessions"
    records = {}
    if not sessions_dir.is_dir():
        return records
    for path in sorted(sessions_dir.glob("*.json")):
        records[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return records


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_records(records: dict[str, dict]) -> None:
    if not records:
        raise ValueError("No session records found under data/sessions/")
    for key, record in records.items():
        _require(record.get("schemaVersion") == 1, f"{key}: unsupported schemaVersion")
        _require(record.get("id") == key, f"{key}: record id does not match its filename")
        _require(record.get("kind") in KINDS, f"{key}: kind must be one of {KINDS}")
        _require(bool(record.get("mergedAt")), f"{key}: mergedAt is required")
        _require(isinstance(record.get("harness", {}).get("platform"), str), f"{key}: harness.platform is required")
        for child in record.get("children") or []:
            _require(child in records, f"{key}: references unknown child session record '{child}'")


def harness_comparison(sessions: list[dict]) -> list[dict]:
    """Sessions, high-assurance rate, and findings rate per `harness.platform` -- the intelligence
    view the plan calls for, reusing the same "rate over a population" shape as
    `awesome.insights.dashboard`'s other distributions."""
    by_platform: dict[str, list[dict]] = {}
    for record in sessions:
        by_platform.setdefault(record["harness"]["platform"], []).append(record)
    rows = []
    for platform, subset in sorted(by_platform.items()):
        n = len(subset)
        high_assurance = sum(1 for r in subset if r["sdlc"]["workflowProfile"] == "high-assurance")
        findings = sum(len(r.get("findings") or []) for r in subset)
        rows.append({
            "platform": platform,
            "sessions": n,
            "highAssuranceRate": round(high_assurance / n, 4) if n else 0.0,
            "findingsRate": round(findings / n, 4) if n else 0.0,
        })
    return rows


def sdlc_conformance(sessions: list[dict]) -> list[dict]:
    counts = Counter(record["sdlc"]["workflowProfile"] for record in sessions)
    return [{"workflowProfile": profile, "sessions": count} for profile, count in counts.most_common()]


def review_distribution(sessions: list[dict]) -> list[dict]:
    counts = Counter(record["sdlc"]["review"] for record in sessions)
    return [{"review": review, "sessions": count} for review, count in counts.most_common()]


def tests_over_time(sessions: list[dict]) -> list[dict]:
    """Replaces the old hand-maintained `testCheckpoints[]`: every session that recorded a real
    `verification.testsPassed` count, in merge order. Unknown is never coerced to zero -- a session
    that didn't record a count is simply absent from the series, not plotted as 0 tests."""
    # `sessions` is already sorted by full mergedAt timestamp (see derive_index) -- truncating to a
    # date here for display and then re-sorting by (date, id) would silently reorder same-day
    # records lexicographically by id (e.g. "pr-10" before "pr-8"), scrambling the actual merge
    # order. Preserve the caller's chronological order; only shorten the displayed date string.
    return [
        {"mergedAt": record["mergedAt"][:10], "id": record["id"], "title": record["title"],
         "testsPassed": record["verification"]["testsPassed"]}
        for record in sessions
        if record.get("verification", {}).get("testsPassed") is not None
    ]


def timeline(sessions: list[dict]) -> list[dict]:
    return [{
        "id": record["id"],
        "kind": record["kind"],
        "title": record["title"],
        "summary": record["summary"],
        "mergedAt": record["mergedAt"],
        "wave": record.get("wave"),
        "platform": record["harness"]["platform"],
        "workflowProfile": record["sdlc"]["workflowProfile"],
        "mode": record["sdlc"]["mode"],
        "humanReviewRequired": bool(record["sdlc"].get("humanReviewRequired")),
        "prNumber": record.get("repository", {}).get("prNumber"),
        "prUrl": record.get("repository", {}).get("prUrl"),
        "issues": record.get("repository", {}).get("issues", []),
        "children": record.get("children") or [],
    } for record in sessions]


def derive_index(records: dict[str, dict], generated_at: str) -> dict:
    """Compute the published `data/sessions-index.json` aggregate from raw per-session records.
    Pure function: performs no I/O and trusts nothing it wasn't handed."""
    _validate_records(records)
    sessions = sorted(records.values(), key=lambda record: (record["mergedAt"], record["id"]))
    kind_counts = Counter(record["kind"] for record in sessions)

    index = {
        "formatVersion": FORMAT,
        "generatedAt": generated_at,
        "counts": {
            "sessions": len(sessions),
            **{kind: kind_counts.get(kind, 0) for kind in KINDS},
        },
        "timeline": timeline(sessions),
        "harnessComparison": harness_comparison(sessions),
        "sdlcConformance": sdlc_conformance(sessions),
        "reviewDistribution": review_distribution(sessions),
        "testsOverTime": tests_over_time(sessions),
    }
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    return index


def validate_index(index: dict, records: dict[str, dict]) -> None:
    """Validate a published/staged sessions-index against the raw records it must reconcile with."""
    _require(index.get("formatVersion") == FORMAT, "Unsupported sessions-index format")
    recomputed_digest = digest({k: v for k, v in index.items() if k != "digest"})
    _require(index.get("digest") == recomputed_digest, "sessions-index digest mismatch")
    _validate_records(records)
    _require(index["counts"]["sessions"] == len(records), "sessions-index count does not reconcile with data/sessions/")
    timeline_ids = {row["id"] for row in index.get("timeline", [])}
    _require(timeline_ids == set(records), "sessions-index timeline does not match the published record set")
