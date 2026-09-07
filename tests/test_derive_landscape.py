import json

import pytest

from awesome.landscape import shard_path
from awesome.projects import shard_path as project_shard_path
from tests.test_derive_network import write_project_snapshot
from tests.test_network import build_network_fixture
from tools.derive_landscape import publish, stage, validate
from tools.derive_network import publish as publish_network, stage as stage_network


def write_network_and_projects(tmp_path):
    data_root, staging_root, _project_index = write_project_snapshot(tmp_path, build_network_fixture())
    staged = stage_network(data_root=data_root, staging_root=staging_root)
    publish_network(staged["digest"], data_root=data_root, staging_root=staging_root)
    return data_root, staging_root


def test_stage_then_publish_round_trip(tmp_path):
    data_root, staging_root = write_network_and_projects(tmp_path)
    staged = stage(data_root=data_root, staging_root=staging_root)
    assert (staging_root / "landscape-index.json").exists()
    assert staged["counts"]["lists"] == 4
    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert (data_root / "landscape-index.json").exists()
    assert published["digest"] == staged["digest"]
    validated = validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_publish_rejects_stale_digest(tmp_path):
    data_root, staging_root = write_network_and_projects(tmp_path)
    stage(data_root=data_root, staging_root=staging_root)
    with pytest.raises(ValueError, match="Stale"):
        publish("0" * 64, data_root=data_root, staging_root=staging_root)


def test_stage_rejects_tampered_project_shard(tmp_path):
    data_root, staging_root = write_network_and_projects(tmp_path)
    project_index = json.loads((data_root / "project-index.json").read_text(encoding="utf-8"))
    prefix = next(iter(project_index["shards"]))
    path = data_root / project_shard_path(prefix)
    shard = json.loads(path.read_text(encoding="utf-8"))
    shard["projects"][0]["title"] = "tampered"
    path.write_text(json.dumps(shard), encoding="utf-8")
    with pytest.raises(ValueError):
        stage(data_root=data_root, staging_root=staging_root)


def test_publish_rejects_tampered_staged_artifact(tmp_path):
    data_root, staging_root = write_network_and_projects(tmp_path)
    staged = stage(data_root=data_root, staging_root=staging_root)
    path = staging_root / "landscape-index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["lists"][0]["unique"] = 99
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        publish(staged["digest"], data_root=data_root, staging_root=staging_root)


def test_run_pipeline_does_not_invoke_landscape():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "tools/run_pipeline.py").read_text(encoding="utf-8")
    assert "derive_landscape" not in source
    assert "landscape" not in source
