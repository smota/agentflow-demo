import json

import pytest

from awesome.catalogue import digest
from awesome.interpret_eligibility import candidate_digest, candidate_fields
from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
from tests.test_lists import MD, REV, meta
import tools.derive_interpretations as mod

PENDING_MD = MD


def write_pending_catalogue(data_root, count=1):
    """One or more real `pending` lists (stars unavailable) with a parsed detail shard, matching
    the exact `awesome.lists.classify` reason H2 is scoped to interpret."""
    lists, details = [], {}
    for i in range(count):
        data = meta(id=str(100 + i), name=f"owner/awesome-tools-{i}",
                    url=f"https://github.com/owner/awesome-tools-{i}", stars=None)
        item, detail = profile(data, parse_readme(PENDING_MD, data["name"], REV), PENDING_MD)
        assert item["state"] == "pending"
        lists.append(item)
        details[item["detail"]] = detail
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": lists,
              "counts": {"pending": count}}
    index["digest"] = digest(index)
    (data_root / "lists").mkdir(parents=True, exist_ok=True)
    for path, detail in details.items():
        (data_root / path).write_text(json.dumps(detail), encoding="utf-8")
    (data_root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
    return index, details


def fake_invoke_ok(eligible=True, confidence="medium", reasoning="Looks like a curated list."):
    def _invoke(prompt, schema, model, timeout):
        return {"ok": True, "output": {"eligible": eligible, "confidence": confidence, "reasoning": reasoning},
                "latency_ms": 1234, "model": model}
    return _invoke


def test_select_candidates_only_returns_pending_lists(tmp_path):
    data_root = tmp_path / "data"
    write_pending_catalogue(data_root, count=2)
    candidates = mod.select_candidates(data_root, limit=10, already_have={})
    assert len(candidates) == 2
    assert all(c["fields"]["reason"] == "Star count is unavailable." for c in candidates)


def test_select_candidates_skips_up_to_date_cache(tmp_path):
    data_root = tmp_path / "data"
    write_pending_catalogue(data_root, count=2)
    index = json.loads((data_root / "list-index.json").read_text(encoding="utf-8"))
    item = index["lists"][0]
    detail = json.loads((data_root / item["detail"]).read_text(encoding="utf-8"))
    already_have = {item["id"]: candidate_digest(candidate_fields(item, detail))}
    candidates = mod.select_candidates(data_root, limit=10, already_have=already_have)
    assert len(candidates) == 1
    assert candidates[0]["list_id"] != item["id"]


def test_build_stages_interpretations_and_publish_validate_round_trip(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_pending_catalogue(data_root, count=2)
    monkeypatch.setattr(mod, "_invoke", fake_invoke_ok())
    staged = mod.build(run_id="test-run", batch_size=10, data_root=data_root,
                        staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["records"] == 2
    assert staged["run"]["completed_this_run"] == 2

    published = mod.publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert published["digest"] == staged["digest"]

    validated = mod.validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]
    assert all(r["source"] == "headless-cli" for r in validated["records"])


def test_build_skips_failed_candidate_without_aborting_batch(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_pending_catalogue(data_root, count=2)
    calls = {"n": 0}

    def flaky_invoke(prompt, schema, model, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "error": "malformed output", "latency_ms": 500}
        return {"ok": True, "output": {"eligible": True, "confidence": "low", "reasoning": "ok"},
                "latency_ms": 500, "model": model}

    monkeypatch.setattr(mod, "_invoke", flaky_invoke)
    staged = mod.build(run_id="test-run", batch_size=10, data_root=data_root,
                        staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["records"] == 1
    assert staged["run"]["completed_this_run"] == 1
    assert staged["run"]["skipped_this_run"] == 1


def test_build_resumes_from_checkpoint_after_interruption(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_pending_catalogue(data_root, count=2)
    monkeypatch.setattr(mod, "_invoke", fake_invoke_ok())
    with pytest.raises(InterruptedError):
        mod.build(run_id="resume-run", batch_size=10, interrupt_after=1, data_root=data_root,
                  staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    staged = mod.build(run_id="resume-run", batch_size=10, data_root=data_root,
                        staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["records"] == 2


def test_unchanged_candidate_is_never_reinvoked_across_runs(tmp_path, monkeypatch):
    """Issue #53's caching requirement: an unchanged candidate must not be re-invoked once cached."""
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_pending_catalogue(data_root, count=1)
    call_count = {"n": 0}

    def counting_invoke(prompt, schema, model, timeout):
        call_count["n"] += 1
        return {"ok": True, "output": {"eligible": True, "confidence": "high", "reasoning": "ok"},
                "latency_ms": 500, "model": model}

    monkeypatch.setattr(mod, "_invoke", counting_invoke)
    staged1 = mod.build(run_id="first", batch_size=10, data_root=data_root,
                         staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    mod.publish(staged1["digest"], data_root=data_root, staging_root=staging_root)
    assert call_count["n"] == 1

    staged2 = mod.build(run_id="second", batch_size=10, data_root=data_root,
                         staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert call_count["n"] == 1  # never invoked again for the same candidate content
    assert staged2["counts"]["records"] == 1


def test_incremental_publish_does_not_drop_prior_records(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_pending_catalogue(data_root, count=2)
    monkeypatch.setattr(mod, "_invoke", fake_invoke_ok())
    staged1 = mod.build(run_id="first", batch_size=1, data_root=data_root,
                         staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged1["counts"]["records"] == 1
    mod.publish(staged1["digest"], data_root=data_root, staging_root=staging_root)
    staged2 = mod.build(run_id="second", batch_size=10, data_root=data_root,
                         staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged2["counts"]["records"] == 2
