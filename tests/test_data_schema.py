"""Validate the committed data-contract schemas against the published snapshots.

Issue #60 (Epic #49, story C1): a third party consuming data/list-index.json or
data/catalogue.json directly (e.g. via raw.githubusercontent.com) needs a machine-checkable,
language-neutral contract, not just the Python validators in awesome/lists.py and
awesome/catalogue.py. These schemas are that contract; this test keeps them honest against the
real files, not a hand-built fixture.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _validate(schema_path: str, data_path: str) -> None:
    schema = _load(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    data = _load(data_path)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        details = "\n".join(
            f"  at {list(e.path)}: {e.message}" for e in errors[:20]
        )
        raise AssertionError(f"{len(errors)} schema violation(s) in {data_path}:\n{details}")


def test_list_index_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(_load("schemas/list-index.schema.json"))


def test_catalogue_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(_load("schemas/catalogue.schema.json"))


def test_committed_list_index_matches_schema():
    _validate("schemas/list-index.schema.json", "data/list-index.json")


def test_committed_catalogue_matches_schema():
    _validate("schemas/catalogue.schema.json", "data/catalogue.json")


def test_list_index_schema_rejects_a_broken_record():
    schema = _load("schemas/list-index.schema.json")
    data = _load("data/list-index.json")
    data["lists"][0]["state"] = "not-a-real-state"
    validator = Draft202012Validator(schema)
    assert any(validator.iter_errors(data))


def test_catalogue_schema_rejects_a_broken_record():
    schema = _load("schemas/catalogue.schema.json")
    data = _load("data/catalogue.json")
    data["sources"][0]["license"] = "MIT"
    validator = Draft202012Validator(schema)
    assert any(validator.iter_errors(data))
