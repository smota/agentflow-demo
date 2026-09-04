import json
import socket

import pytest
from streamlit.testing.v1 import AppTest

from awesome.catalogue import digest
from awesome.projects import derive_projects, shard_path as project_shard_path
from awesome.search_index import build_top_index, derive_search_shard, shard_path as search_shard_path
from tests.test_projects import build_two_list_index

GENERATED_AT = "2026-09-04T00:00:00Z"


def write_search_snapshot(directory):
    """Builds a full offline pipeline output (list-index, project-index, search-index and their
    shards) under `directory`, mirroring exactly what `tools/derive_projects.py` and
    `tools/derive_search_index.py` publish -- so the Streamlit view under test reads the same
    shapes production does, never a shortcut fixture."""
    index, details = build_two_list_index()
    index.update(generated_at=GENERATED_AT,
                 coverage={"scope": "Fixture observations, not a census", "enrichment_pending": 0, "queued_partitions": 0})
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    (directory / "lists").mkdir(parents=True, exist_ok=True)
    for path, detail in details.items():
        (directory / path).write_text(json.dumps(detail), encoding="utf-8")
    (directory / "list-index.json").write_text(json.dumps(index), encoding="utf-8")

    derived = derive_projects(index, details, GENERATED_AT)
    (directory / "projects").mkdir(exist_ok=True)
    for prefix, shard in derived["shards"].items():
        (directory / project_shard_path(prefix)).write_text(json.dumps(shard), encoding="utf-8")
    (directory / "project-index.json").write_text(json.dumps(derived["index"]), encoding="utf-8")

    shard_digests, total = {}, 0
    (directory / "search").mkdir(exist_ok=True)
    for prefix, project_shard in derived["shards"].items():
        search_shard = derive_search_shard(project_shard, derived["index"]["digest"])
        (directory / search_shard_path(prefix)).write_text(json.dumps(search_shard), encoding="utf-8")
        shard_digests[prefix] = search_shard["digest"]
        total += len(search_shard["projects"])
    top = build_top_index(derived["index"]["digest"], GENERATED_AT, shard_digests,
                           {"projects": total, "shards": len(shard_digests)})
    (directory / "search-index.json").write_text(json.dumps(top), encoding="utf-8")
    return index


def preview_entry(directory):
    from pathlib import Path
    from awesome.list_ui import render
    render(Path(directory), preview=True)


@pytest.fixture
def preview(tmp_path, monkeypatch):
    directory = tmp_path / ".cache/ui-preview"
    directory.mkdir(parents=True)
    write_search_snapshot(directory)
    (tmp_path / "package.json").write_text('{"version":"2.0.0-alpha.3"}')
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def denied(*args, **kwargs):
        raise AssertionError("Hosted UI attempted networking")

    monkeypatch.setattr(socket.socket, "connect", denied)
    return AppTest.from_function(preview_entry, args=(str(tmp_path),), default_timeout=20)


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_search_projects_view_returns_cross_list_result_with_honest_provenance(preview):
    app = preview.run()
    assert not app.exception
    button(app, "Search projects").click().run()
    assert not app.exception
    app.text_input(key="search_q").set_value("tool 0").run()
    assert not app.exception
    # "Tool 0" (list-a wording) / "Tool 0 alias" (list-b wording) is the shared, cross-list URL
    # from the two-list fixture -- a real result sourced from more than one list. AppTest does not
    # expose st.link_button as a queryable element type, so the per-occurrence "Also listed in"
    # provenance links are exercised indirectly here (no exception means `project_citations`
    # resolved real occurrence detail for this result) and directly by
    # `awesome.project_search`/`awesome.search_index`'s own unit tests.
    assert any("Tool 0" in md.value for md in app.markdown)
    assert any("Cited independently by 2 of 2" in c.value for c in list(app.caption) + list(app.success))


def test_search_projects_view_no_query_shows_prompt_not_full_dump(preview):
    app = preview.run()
    button(app, "Search projects").click().run()
    assert any("Type a search term" in x.value for x in app.info)


def test_search_projects_view_no_match_shows_no_results_message(preview):
    app = preview.run()
    button(app, "Search projects").click().run()
    app.text_input(key="search_q").set_value("zz-no-such-project-zz").run()
    assert any("No projects match" in x.value for x in app.info)


def test_search_result_never_states_trust_or_quality_from_citation_count_alone(preview):
    """The methodology copy and any per-result label must stay factual/disclosed, never an
    unqualified trust/quality claim -- this is the redesign's central, testable guardrail."""
    app = preview.run()
    button(app, "Search projects").click().run()
    app.text_input(key="search_q").set_value("tool 0").run()
    rendered_text = " ".join(x.value for x in app.markdown) + " ".join(x.value for x in app.caption)
    for banned in ("high quality", "trusted", "best project", "top rated"):
        assert banned not in rendered_text.lower()
