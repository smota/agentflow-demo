"""Unified staging verification gate for unattended pipeline runs.

Provides a single seam for disk re-reading, digest recomputation, validator protocol
dispatch, and step failure enforcement, consolidating logic previously duplicated across
`tools/run_pipeline.py` and various offline derivation scripts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from awesome.catalogue import digest
from awesome.interpret_eligibility import validate_interpretations
from awesome.lists import validate_index
from awesome.projects import shard_path as project_shard_path, validate_projects


class StepFailed(RuntimeError):
    """Raised for any step that fails, is unreachable, or fails independent verification."""


def verify_staged_artifact(
    artifact_path: Path,
    expected_digest: str,
    validator: Callable[[dict], None],
    missing_message: str = "Staged artifact missing before publish verification",
) -> dict:
    """Read a staged JSON artifact from disk, verify its digest, and run a validator.

    Guarantees that:
    1. The candidate actually exists on disk.
    2. The recomputed digest over the bytes on disk matches the claimed digest and expected_digest.
    3. The domain validator passes against the loaded document.
    """
    if not artifact_path.exists():
        raise StepFailed(missing_message)
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    recomputed = digest({k: v for k, v in data.items() if k != "digest"})
    if recomputed != data.get("digest") or recomputed != expected_digest:
        raise StepFailed(f"Independent digest recomputation did not match the staged artifact at {artifact_path.name}")
    try:
        validator(data)
    except (ValueError, OSError) as exc:
        raise StepFailed(f"Staged artifact failed independent validation: {exc}") from exc
    return data


def verify_list_stage(expected_digest: str, data_root: Path) -> dict:
    staging = data_root / "staging"
    path = staging / "list-index.json"

    def validator(index: dict):
        validate_index(index, staging)

    return verify_staged_artifact(
        path,
        expected_digest,
        validator,
        missing_message="Staged list index missing before publish verification",
    )


def verify_project_stage(expected_digest: str, data_root: Path) -> dict:
    staging = data_root / "staging"
    path = staging / "project-index.json"
    list_index_path = data_root / "list-index.json"
    if not list_index_path.exists():
        raise StepFailed("Published list index missing before project publish verification")
    list_index = json.loads(list_index_path.read_text(encoding="utf-8"))

    def validator(data: dict):
        shards = {prefix: json.loads((staging / project_shard_path(prefix)).read_text(encoding="utf-8"))
                  for prefix in data.get("shards", {})}
        validate_projects(data, list_index, shards)

    return verify_staged_artifact(
        path,
        expected_digest,
        validator,
        missing_message="Staged project index missing before publish verification",
    )


def verify_interpretation_stage(expected_digest: str, data_root: Path) -> dict:
    staging = data_root / "staging"
    path = staging / "interpretations-index.json"
    list_index_path = data_root / "list-index.json"
    if not list_index_path.exists():
        raise StepFailed("Published list index missing before interpretation publish verification")
    list_index = json.loads(list_index_path.read_text(encoding="utf-8"))

    def validator(data: dict):
        validate_interpretations(data, list_index)

    return verify_staged_artifact(
        path,
        expected_digest,
        validator,
        missing_message="Staged interpretation index missing before publish verification",
    )
