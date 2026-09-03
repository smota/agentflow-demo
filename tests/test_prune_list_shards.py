import json

import pytest

from tests.test_lists import build_index
from tools.prune_list_shards import prune


def snapshot(tmp_path):
    index, detail = build_index()
    (tmp_path / "lists").mkdir()
    (tmp_path / index["lists"][0]["detail"]).write_text(json.dumps(detail), encoding="utf-8")
    (tmp_path / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
    extra = tmp_path / "lists" / ("f" * 64 + ".json")
    extra.write_text("{}", encoding="utf-8")
    return index, extra


def test_prune_is_dry_run_then_digest_bound_apply(tmp_path):
    index, extra = snapshot(tmp_path)
    report = prune(tmp_path, index["digest"])
    assert report["files"] == 1 and report["bytes"] == 2 and report["applied"] is False
    assert extra.exists()
    report = prune(tmp_path, index["digest"], apply=True)
    assert report["applied"] is True and not extra.exists()


def test_prune_rejects_stale_digest_and_unexpected_objects(tmp_path):
    index, _ = snapshot(tmp_path)
    with pytest.raises(ValueError, match="digest"):
        prune(tmp_path, "0" * 64, apply=True)
    (tmp_path / "lists" / "notes.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected"):
        prune(tmp_path, index["digest"], apply=True)
