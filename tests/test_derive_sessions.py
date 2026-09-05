"""Tests for awesome.sessions (pure derivation/validation) and tools.derive_sessions (stage/
publish/validate CLI), mirroring tests/test_derive_projects.py's coverage shape for the sibling
project-catalogue pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from awesome.sessions import derive_index, harness_comparison, load_records, validate_index
from awesome.sessions import tests_over_time as compute_tests_over_time
# ^ aliased on import: pytest's default `python_functions = test` collection rule matches any name
# that merely *starts with* "test" (not just an exact "test_*" prefix) once it is a module-level
# name here -- importing `tests_over_time` unaliased makes pytest try to collect and run it as a
# test function of its own (with a "sessions" fixture it doesn't have). Renaming on import avoids
# reserving that prefix for anything pytest should not treat as a test.
from tools import derive_sessions


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_records():
    return {
        "pr-1": {
            "schemaVersion": 1, "id": "pr-1", "kind": "pr", "title": "First", "summary": "First PR",
            "mergedAt": "2026-01-01T00:00:00Z",
            "harness": {"platform": "claude", "executor": "claude-cli", "transport": "local-cli", "delegationBoundary": "current-session"},
            "sdlc": {"mode": "single-agent", "workflowProfile": "standard", "phasesRun": ["developer"],
                     "review": "self-review", "humanReviewRequired": False, "mergeOwner": "human/operator"},
            "repository": {"prNumber": 1, "prUrl": "https://example.test/pull/1", "targetBranch": "development", "issues": []},
            "verification": {"testsPassed": 10},
            "decisions": [], "findings": [], "followUps": [], "evidence": [],
        },
        "pr-2": {
            "schemaVersion": 1, "id": "pr-2", "kind": "pr", "title": "Second", "summary": "Second PR",
            "mergedAt": "2026-01-02T00:00:00Z",
            "harness": {"platform": "codex", "executor": "codex-cli", "transport": "local-cli", "delegationBoundary": "current-session"},
            "sdlc": {"mode": "single-agent", "workflowProfile": "high-assurance", "phasesRun": ["developer"],
                     "review": "human", "humanReviewRequired": True, "mergeOwner": "human/operator"},
            "repository": {"prNumber": 2, "prUrl": "https://example.test/pull/2", "targetBranch": "development", "issues": []},
            "verification": {"testsPassed": 15},
            "decisions": [], "findings": [{"summary": "x", "howFound": "y"}], "followUps": [], "evidence": [],
        },
        "rollup-1": {
            "schemaVersion": 1, "id": "rollup-1", "kind": "rollup", "title": "Wave", "summary": "A wave",
            "mergedAt": "2026-01-02T12:00:00Z",
            "harness": {"platform": "claude", "executor": "claude-cli", "transport": "local-cli", "delegationBoundary": "current-session"},
            "sdlc": {"mode": "single-agent", "workflowProfile": "high-assurance", "phasesRun": ["developer"],
                     "review": "human", "humanReviewRequired": True, "mergeOwner": "human/operator"},
            "repository": {"issues": []},
            "verification": {},
            "decisions": [], "findings": [], "followUps": [], "children": ["pr-1", "pr-2"], "evidence": [],
        },
    }


def test_derive_index_reconciles_counts(sample_records):
    index = derive_index(sample_records, generated_at="2026-01-03T00:00:00Z")
    assert index["counts"] == {"sessions": 3, "pr": 2, "rollup": 1, "release": 0}
    assert index["digest"]


def test_derive_index_rejects_dangling_child_reference(sample_records):
    sample_records["rollup-1"]["children"] = ["pr-1", "pr-does-not-exist"]
    with pytest.raises(ValueError):
        derive_index(sample_records, generated_at="2026-01-03T00:00:00Z")


def test_harness_comparison_computes_rates(sample_records):
    sessions = list(sample_records.values())
    rows = harness_comparison(sessions)
    by_platform = {row["platform"]: row for row in rows}
    assert by_platform["codex"]["sessions"] == 1
    assert by_platform["codex"]["highAssuranceRate"] == 1.0
    assert by_platform["codex"]["findingsRate"] == 1.0
    assert by_platform["claude"]["sessions"] == 2
    assert by_platform["claude"]["findingsRate"] == 0.0


def test_tests_over_time_preserves_input_order_not_lexicographic_id(sample_records):
    # pr-1 (2026-01-01) then pr-2 (2026-01-02): chronological. Passing them in id-shuffled but
    # time-ordered form must not get re-sorted by id -- regression test for a real bug found while
    # building this pipeline (see awesome/sessions.py#tests_over_time docstring).
    ordered = [sample_records["pr-1"], sample_records["pr-2"]]
    points = compute_tests_over_time(ordered)
    assert [p["id"] for p in points] == ["pr-1", "pr-2"]
    assert [p["testsPassed"] for p in points] == [10, 15]


def test_validate_index_detects_digest_tamper(sample_records):
    index = derive_index(sample_records, generated_at="2026-01-03T00:00:00Z")
    index["counts"]["sessions"] = 999
    with pytest.raises(ValueError):
        validate_index(index, sample_records)


def test_derive_sessions_stage_publish_validate_roundtrip(tmp_path, sample_records):
    data_root = tmp_path / "data"
    staging_root = tmp_path / "data" / "staging"
    sessions_dir = data_root / "sessions"
    sessions_dir.mkdir(parents=True)
    for session_id, record in sample_records.items():
        (sessions_dir / f"{session_id}.json").write_text(json.dumps(record), encoding="utf-8")

    staged = derive_sessions.stage(data_root=data_root, staging_root=staging_root)
    assert staged["counts"]["sessions"] == 3

    published = derive_sessions.publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert published["digest"] == staged["digest"]
    assert (data_root / "sessions-index.json").exists()

    with pytest.raises(ValueError):
        derive_sessions.publish("0" * 64, data_root=data_root, staging_root=staging_root)

    validated = derive_sessions.validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_real_published_sessions_index_validates():
    records = load_records(ROOT / "data")
    result = derive_sessions.validate(data_root=ROOT / "data")
    assert result["counts"]["sessions"] == len(records)
