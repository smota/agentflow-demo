import json

from tools.changelog import append_changelog, diff_indexes, render


def index(run_id="run-a", generated_at="2026-09-01T00:00:00Z", digest="d1", lists=None):
    return {"run_id": run_id, "generated_at": generated_at, "digest": digest, "lists": lists or []}


def item(id_, name="owner/list", url=None, state="eligible", reason="Eligible.", stars=100):
    return {"id": id_, "name": name, "url": url or f"https://github.com/{name}", "state": state,
            "reason": reason, "stars": stars}


def test_diff_detects_added_removed_and_unchanged():
    before = index(lists=[item("1", "owner/a"), item("2", "owner/b")])
    after = index("run-b", "2026-09-02T00:00:00Z", "d2", lists=[item("1", "owner/a"), item("3", "owner/c")])
    diff = diff_indexes(before, after)
    assert [i["id"] for i in diff["added"]] == ["3"]
    assert [i["id"] for i in diff["removed"]] == ["2"]
    assert diff["changed"] == []


def test_diff_detects_state_and_reason_change_for_same_id():
    before = index(lists=[item("1", "owner/a", state="pending", reason="Ambiguous.")])
    after = index("run-b", lists=[item("1", "owner/a", state="eligible", reason="Now eligible.")])
    diff = diff_indexes(before, after)
    assert diff["added"] == [] and diff["removed"] == []
    assert len(diff["changed"]) == 1
    deltas = diff["changed"][0]["deltas"]
    assert deltas["state"] == {"before": "pending", "after": "eligible"}
    assert deltas["reason"] == {"before": "Ambiguous.", "after": "Now eligible."}


def test_diff_ignores_untracked_field_churn():
    before = index(lists=[item("1", "owner/a")])
    after_item = item("1", "owner/a")
    after_item["freshness"] = {"days": 3, "range": "Within 30 days", "index": 95.0}  # untracked field
    diff = diff_indexes(before, index("run-b", lists=[after_item]))
    assert diff["changed"] == []


def test_diff_is_pure_and_does_not_mutate_inputs():
    before = index(lists=[item("1", "owner/a")])
    after = index("run-b", lists=[item("1", "owner/a", state="excluded", reason="Now excluded.")])
    before_copy, after_copy = json.loads(json.dumps(before)), json.loads(json.dumps(after))
    diff_indexes(before, after)
    assert before == before_copy and after == after_copy


def test_diff_is_deterministic_across_calls():
    before = index(lists=[item("1", "owner/a"), item("2", "owner/b")])
    after = index("run-b", lists=[item("1", "owner/a"), item("3", "owner/c")])
    assert diff_indexes(before, after) == diff_indexes(before, after)


def test_render_lists_added_removed_changed_with_a_contributors_list_findable():
    before = index(lists=[item("2", "owner/gone")])
    after = index("run-b", "2026-09-02T00:00:00Z", "d2",
                   lists=[item("3", "someone/proposed-list", reason="Curated-list intent confirmed.")])
    diff = diff_indexes(before, after)
    text = render(diff)
    assert "someone/proposed-list" in text and "### Added" in text
    assert "owner/gone" in text and "### Removed" in text
    assert "run-b" in text and "d2" in text


def test_render_no_changes_says_so():
    before = index(lists=[item("1", "owner/a")])
    after = index("run-b", lists=[item("1", "owner/a")])
    text = render(diff_indexes(before, after))
    assert "No catalogue changes" in text


def test_render_is_deterministic_text():
    before = index(lists=[item("1", "owner/a")])
    after = index("run-b", lists=[item("2", "owner/b")])
    diff = diff_indexes(before, after)
    assert render(diff) == render(diff)


def test_append_changelog_is_newest_first_and_creates_heading(tmp_path):
    path = tmp_path / "catalogue-changelog.md"
    append_changelog("## run-a\n\nFirst entry.\n", path)
    append_changelog("## run-b\n\nSecond entry.\n", path)
    text = path.read_text(encoding="utf-8")
    assert text.index("run-b") < text.index("run-a")
    assert text.startswith("# Catalogue changelog")
