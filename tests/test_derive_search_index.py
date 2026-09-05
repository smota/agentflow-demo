import json

from awesome.catalogue import digest
from awesome.interpret_topics import label_digest
from awesome.projects import shard_path as project_shard_path
from awesome.search_index import shard_path as search_shard_path
from tests.test_derive_projects import write_snapshot
from tests.test_projects import build_two_list_index
from tools.derive_projects import publish as publish_projects, stage as stage_projects
from tools.derive_search_index import load_topic_overrides, publish, stage, validate


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


# --- H3 (issue #53): optional topic-interpretations.json overlay ---

def write_topic_overrides(data_root, records):
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": len(records)}, "records": records}
    data["digest"] = digest(data)
    (data_root / "topic-interpretations.json").write_text(json.dumps(data), encoding="utf-8")


def test_load_topic_overrides_absent_by_default(tmp_path):
    data_root, _, _ = write_project_snapshot(tmp_path)
    assert load_topic_overrides(data_root) is None


def test_stage_without_overlay_matches_before_h3_output(tmp_path):
    data_root, staging_root, _ = write_project_snapshot(tmp_path)
    staged = stage(data_root=data_root, staging_root=staging_root)
    # "tools" (the MD fixture's own section category) is not in _SYNONYMS, so it degrades to the
    # raw hyphenated fallback with no overlay present.
    all_topics = {t for prefix in staged["shards"] for r in
                  json.loads((staging_root / search_shard_path(prefix)).read_text(encoding="utf-8"))["projects"]
                  for t in r["topics"]}
    assert "tools" in all_topics


def test_stage_applies_published_topic_overlay(tmp_path):
    data_root, staging_root, _ = write_project_snapshot(tmp_path)
    write_topic_overrides(data_root, [{"label": "tools", "label_digest": label_digest("tools"),
                                        "tag": "devops", "confidence": "high", "model": "sonnet",
                                        "source": "headless-cli", "invoked_at": "2026-09-04T00:00:00Z"}])
    staged = stage(data_root=data_root, staging_root=staging_root)
    all_topics = {t for prefix in staged["shards"] for r in
                  json.loads((staging_root / search_shard_path(prefix)).read_text(encoding="utf-8"))["projects"]
                  for t in r["topics"]}
    assert "tools" not in all_topics
    assert "devops" in all_topics


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
