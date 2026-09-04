import json

import pytest

from awesome.alternatives import shard_path
from tests.test_projects import build_two_list_index
from tools.derive_alternatives import publish, stage, validate


def write_snapshot(root, index, details):
    (root / "lists").mkdir(parents=True)
    for detail_path, detail in details.items():
        (root / detail_path).write_text(json.dumps(detail), encoding="utf-8")
    (root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")


def test_stage_then_publish_round_trip(tmp_path):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    index, details = build_two_list_index()
    write_snapshot(data_root, index, details)

    staged = stage(data_root=data_root, staging_root=staging_root)
    assert (staging_root / "alternatives-index.json").exists()
    assert staged["counts"]["shards"] >= 1
    for prefix in staged["shards"]:
        assert (staging_root / shard_path(prefix)).exists()
    assert not (data_root / "alternatives-index.json").exists()

    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert (data_root / "alternatives-index.json").exists()
    assert published["digest"] == staged["digest"]

    validated = validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_publish_rejects_stale_digest(tmp_path):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    index, details = build_two_list_index()
    write_snapshot(data_root, index, details)
    stage(data_root=data_root, staging_root=staging_root)
    with pytest.raises(ValueError, match="Stale"):
        publish("0" * 40, data_root=data_root, staging_root=staging_root)
