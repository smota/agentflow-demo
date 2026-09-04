import json

import pytest

from tests.test_derive_projects import write_snapshot
from tests.test_network import build_network_fixture
from tools.derive_network import publish, stage, validate
from tools.derive_projects import publish as publish_projects, stage as stage_projects


def write_project_snapshot(tmp_path, index_and_details):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    index, details = index_and_details
    write_snapshot(data_root, index, details)
    staged = stage_projects(data_root=data_root, staging_root=staging_root)
    published = publish_projects(staged["digest"], data_root=data_root, staging_root=staging_root)
    return data_root, staging_root, published


def test_stage_then_publish_round_trip(tmp_path):
    data_root, staging_root, project_index = write_project_snapshot(tmp_path, build_network_fixture())
    staged = stage(data_root=data_root, staging_root=staging_root)
    assert (staging_root / "network-index.json").exists()
    assert staged["counts"]["pairs"] > 0 and staged["counts"]["hub_projects"] > 0

    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert (data_root / "network-index.json").exists()
    assert published["digest"] == staged["digest"]

    validated = validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_publish_rejects_stale_digest(tmp_path):
    data_root, staging_root, _ = write_project_snapshot(tmp_path, build_network_fixture())
    stage(data_root=data_root, staging_root=staging_root)
    with pytest.raises(ValueError, match="Stale"):
        publish("0" * 64, data_root=data_root, staging_root=staging_root)


def test_stage_rejects_tampered_project_shard(tmp_path):
    data_root, staging_root, project_index = write_project_snapshot(tmp_path, build_network_fixture())
    from awesome.projects import shard_path
    prefix = next(iter(project_index["shards"]))
    path = data_root / shard_path(prefix)
    shard = json.loads(path.read_text(encoding="utf-8"))
    shard["projects"][0]["title"] = "tampered"
    path.write_text(json.dumps(shard), encoding="utf-8")
    with pytest.raises(ValueError):
        stage(data_root=data_root, staging_root=staging_root)


def test_publish_rejects_tampered_staged_artifact(tmp_path):
    data_root, staging_root, _ = write_project_snapshot(tmp_path, build_network_fixture())
    staged = stage(data_root=data_root, staging_root=staging_root)
    path = staging_root / "network-index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hub_projects"][0]["title"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        publish(staged["digest"], data_root=data_root, staging_root=staging_root)
