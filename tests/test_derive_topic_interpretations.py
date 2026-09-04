import json

import pytest

from awesome.interpret_topics import label_digest
from tests.test_derive_projects import write_snapshot
from tests.test_projects import build_two_list_index
from tools.derive_projects import publish as publish_projects, stage as stage_projects
import tools.derive_topic_interpretations as mod


def write_project_snapshot(tmp_path):
    """Same fixture shape as tests/test_derive_search_index.py -- one project shard whose
    occurrences carry the 'tools' raw category label (from tests.test_lists.MD's own "## Tools"
    section), which is NOT in awesome.topics._SYNONYMS -- a genuine H3 candidate label."""
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    index, details = build_two_list_index()
    write_snapshot(data_root, index, details)
    staged = stage_projects(data_root=data_root, staging_root=staging_root)
    published = publish_projects(staged["digest"], data_root=data_root, staging_root=staging_root)
    return data_root, published


def fake_invoke_ok(tag="devops", confidence="high"):
    def _invoke(prompt, schema, model, timeout):
        return {"ok": True, "output": {"tag": tag, "confidence": confidence}, "latency_ms": 900, "model": model}
    return _invoke


def test_collect_unmapped_labels_finds_real_uncovered_category(tmp_path):
    data_root, project_index = write_project_snapshot(tmp_path)
    labels = mod.collect_unmapped_labels(data_root, project_index)
    assert "tools" in labels


def test_select_candidates_skips_already_cached_labels(tmp_path):
    data_root, project_index = write_project_snapshot(tmp_path)
    candidates = mod.select_candidates(data_root, limit=10, already_have={"tools"})
    assert "tools" not in {c["label"] for c in candidates}


def test_select_candidates_empty_without_published_project_index(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True)
    assert mod.select_candidates(data_root, limit=10, already_have=set()) == []


def test_build_publish_validate_round_trip(tmp_path, monkeypatch):
    data_root, _ = write_project_snapshot(tmp_path)
    staging_root = data_root / "staging"
    monkeypatch.setattr(mod, "_invoke", fake_invoke_ok())
    staged = mod.build(run_id="test-run", batch_size=10, data_root=data_root,
                        staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["records"] >= 1
    labels = {r["label"]: r for r in staged["records"]}
    assert labels["tools"]["tag"] == "devops"

    published = mod.publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert published["digest"] == staged["digest"]

    validated = mod.validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_label_is_cached_forever_never_reinvoked(tmp_path, monkeypatch):
    data_root, _ = write_project_snapshot(tmp_path)
    staging_root = data_root / "staging"
    call_count = {"n": 0}

    def counting_invoke(prompt, schema, model, timeout):
        call_count["n"] += 1
        return {"ok": True, "output": {"tag": "devops", "confidence": "high"}, "latency_ms": 900, "model": model}

    monkeypatch.setattr(mod, "_invoke", counting_invoke)
    staged1 = mod.build(run_id="first", batch_size=10, data_root=data_root,
                         staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    mod.publish(staged1["digest"], data_root=data_root, staging_root=staging_root)
    calls_after_first = call_count["n"]
    assert calls_after_first >= 1

    staged2 = mod.build(run_id="second", batch_size=10, data_root=data_root,
                         staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert call_count["n"] == calls_after_first  # no label re-invoked
    assert staged2["counts"]["records"] == staged1["counts"]["records"]


def test_build_resumes_from_checkpoint_after_interruption(tmp_path, monkeypatch):
    data_root, _ = write_project_snapshot(tmp_path)
    staging_root = data_root / "staging"
    monkeypatch.setattr(mod, "_invoke", fake_invoke_ok())
    with pytest.raises(InterruptedError):
        mod.build(run_id="resume-run", batch_size=10, interrupt_after=1, data_root=data_root,
                  staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    staged = mod.build(run_id="resume-run", batch_size=10, data_root=data_root,
                        staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["records"] >= 1
