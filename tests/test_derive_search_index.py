import json

from awesome.projects import shard_path as project_shard_path
from awesome.search_index import shard_path as search_shard_path
from tests.test_derive_projects import write_snapshot
from tests.test_projects import build_two_list_index
from tools.derive_projects import publish as publish_projects, stage as stage_projects
from tools.derive_search_index import publish, stage, validate


def write_project_snapshot(tmp_path):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    index, details = build_two_list_index()
    write_snapshot(data_root, index, details)
    staged = stage_projects(data_root=data_root, staging_root=staging_root)
    published = publish_projects(staged["digest"], data_root=data_root, staging_root=staging_root)
    return data_root, staging_root, published


def test_stage_then_publish_round_trip(tmp_path):
    data_root, staging_root, project_index = write_project_snapshot(tmp_path)
    staged = stage(data_root=data_root, staging_root=staging_root)
    assert (staging_root / "search-index.json").exists()
    assert staged["counts"]["projects"] == project_index["counts"]["projects"]
    for prefix in staged["shards"]:
        assert (staging_root / search_shard_path(prefix)).exists()

    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert (data_root / "search-index.json").exists()
    assert published["digest"] == staged["digest"]

    validated = validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_stage_rejects_tampered_project_shard(tmp_path):
    data_root, staging_root, project_index = write_project_snapshot(tmp_path)
    prefix = next(iter(project_index["shards"]))
    path = data_root / project_shard_path(prefix)
    shard = json.loads(path.read_text(encoding="utf-8"))
    shard["projects"][0]["title"] = "tampered"
    path.write_text(json.dumps(shard), encoding="utf-8")
    try:
        stage(data_root=data_root, staging_root=staging_root)
        assert False, "expected ValueError"
    except ValueError:
        pass
