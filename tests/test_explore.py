import copy
import json
import socket
from urllib.parse import parse_qs, urlsplit
import pytest
from streamlit.testing.v1 import AppTest
from awesome.catalogue import digest
from awesome.explore import DEFAULTS, normalize, filtered, page_slice, share_url, content_filter
from awesome.lists import FORMAT, parse_readme, profile
from tests.test_lists import MD, meta


def fixture_index():
    records, details = [], {}
    for i in range(15):
        source = meta(id=str(i), name=f"owner/awesome-{i}", stars=100+i,
                      description="A curated list of Python tools")
        if i == 14: source.update(name="awesome-selfhosted/awesome-selfhosted", description="A curated list of self-hosted tools", stars=300000)
        parsed = parse_readme(MD, source["name"], source["revision"])
        item, detail = profile(source, parsed, MD)
        records.append(item); details[item["detail"]] = detail
    index = {"format_version": FORMAT, "min_stars": 100, "lists": records,
             "counts": {"eligible": 15}, "generated_at": "2026-09-03T00:00:00Z",
             "coverage": {"scope": "Fixture observations, not a census", "enrichment_pending": 0, "queued_partitions": 0}}
    index["digest"] = digest(index)
    return index, details


def test_state_bounds_and_share_roundtrip():
    index, _ = fixture_index()
    state = normalize({"q": "  self  hosted ", "page": -1, "min_stars": 99, "view": "bad", "topic": "bad", "evil": "x"}, index)
    assert state["q"] == "self hosted" and state["page"] == 1 and state["min_stars"] == 100
    assert state["topic"] == "All topics" and "evil" not in state
    assert normalize({"q": ["a", "b"], "min_stars": True}, index) == DEFAULTS
    state.update(view="List", list="14", page=4, content_q="tool", content_category="tools")
    params = {k: v[0] for k, v in parse_qs(urlsplit(share_url(state)).query).items()}
    assert normalize(params, index) == state
    assert normalize({"view": "List", "list": "unknown"}, index)["view"] == "Discover"
    compared = normalize({"view": "Insights", "compare": "14,13,14,bad,12,11,10"}, index)
    assert compared["view"] == "Insights" and compared["compare"] == "14,13,12,11"
    assert normalize({k: v[0] for k, v in parse_qs(urlsplit(share_url(compared)).query).items()}, index) == compared


def test_all_results_boundaries_and_freshness():
    index, _ = fixture_index(); state = dict(DEFAULTS)
    assert len(filtered(index, state)) == 15
    assert filtered(index, state)[-1]["stars"] == 100
    state["q"] = "selfhosted"
    assert filtered(index, state)[0]["id"] == "14"
    state.update(q="", freshness="Within 30 days")
    assert not filtered(index, state)
    state["freshness"] = "Unknown"
    assert len(filtered(index, state)) == 15
    assert page_slice(15, 9999) == (2, 2, 12, 15)
    assert page_slice(0, 3) == (1, 1, 0, 0)


def test_detail_filter_uses_original_category():
    _, details = fixture_index(); detail = next(iter(details.values()))
    assert len(content_filter(detail, "tool 2", "tools")) == 1
    assert content_filter(detail, "", "missing") == []


@pytest.fixture
def preview(tmp_path, monkeypatch):
    index, details = fixture_index(); directory = tmp_path / ".cache/ui-preview"
    directory.mkdir(parents=True)
    (directory / "lists").mkdir()
    (directory / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
    for path, detail in details.items(): (directory / path).write_text(json.dumps(detail), encoding="utf-8")
    (tmp_path / "package.json").write_text('{"version":"2.0.0-alpha.3"}')
    monkeypatch.delenv("GH_TOKEN", raising=False); monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    def denied(*args, **kwargs): raise AssertionError("Hosted UI attempted networking")
    monkeypatch.setattr(socket.socket, "connect", denied)
    return AppTest.from_function(preview_entry, args=(str(tmp_path),), default_timeout=20)


def preview_entry(directory):
    from pathlib import Path
    from awesome.list_ui import render
    render(Path(directory), preview=True)


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_offline_list_preview_navigation_and_content(preview):
    app = preview.run()
    assert not app.exception
    assert app.metric[0].value == "15"
    assert any("unaccepted" in x.value for x in app.warning)
    assert any("Page 1 of 2" in x.value for x in app.caption)
    button(app, "Next →").click().run()
    assert any("Page 2 of 2" in x.value for x in app.caption)
    app.text_input(key="le_q").set_value("selfhosted").run()
    assert any("Page 1 of 1" in x.value for x in app.caption)
    app.button(key="open_14").click().run()
    assert app.title[0].value == "awesome-selfhosted/awesome-selfhosted"
    assert app.metric[3].value == "Unknown"
    app.text_input(key="content_14").set_value("Tool 2").run()
    assert len(app.dataframe[0].value) == 1
    button(app, "Share this view").click().run()
    assert "list=14" in app.code[0].value and "q=selfhosted" in app.code[0].value and "content_q=Tool+2" in app.code[0].value
    button(app, "← Back to results").click().run()
    assert app.text_input(key="le_q").value == "selfhosted"
    button(app, "Reset discovery").click().run()
    assert app.text_input(key="le_q").value == ""
    assert not app.exception


def test_preview_repeated_params_table_and_empty_state(preview):
    preview.query_params.update({"q": ["a", "b"], "view": "List", "list": "missing"})
    app = preview.run()
    assert not app.exception and app.text_input(key="le_q").value == ""
    app.selectbox(key="le_layout").select("Table").run()
    assert not app.exception and len(app.dataframe[0].value) == 12
    app.text_input(key="le_q").set_value("zz-no-match-zz").run()
    assert any("No lists match" in x.value for x in app.info)
    button(app, "Delivery story").click().run()
    assert app.title[0].value == "Built in the open."
    assert not app.exception


def test_full_content_share_reopens_and_changed_index_recovers(preview, tmp_path):
    preview.query_params.update({"view": "List", "list": "14", "content_q": "Tool 3", "content_category": "tools"})
    app = preview.run()
    assert not app.exception and len(app.dataframe[0].value) == 1
    button(app, "Share this view").click().run()
    params = {k: v[0] for k, v in parse_qs(urlsplit(app.code[0].value).query).items()}
    reopened = AppTest.from_function(preview_entry, args=(str(tmp_path),), default_timeout=20)
    reopened.query_params.update(params); reopened.run()
    assert reopened.text_input(key="content_14").value == "Tool 3"
    assert reopened.selectbox(key="category_14").value == "tools"
    assert len(reopened.dataframe[0].value) == 1
    path = tmp_path / ".cache/ui-preview/list-index.json"
    index = json.loads(path.read_text()); index["lists"] = index["lists"][:-1]; index["counts"]["eligible"] -= 1
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    path.write_text(json.dumps(index), encoding="utf-8")
    reopened.run()
    assert not reopened.exception and reopened.session_state.list_explorer["view"] == "Discover"


def test_corrupt_section_is_not_rendered_as_link(preview, tmp_path):
    root = tmp_path / ".cache/ui-preview"; index = json.loads((root / "list-index.json").read_text())
    item = index["lists"][-1]; detail = json.loads((root / item["detail"]).read_text())
    detail["sections"][0]["source_url"] = "javascript:alert(1)"
    detail["digest"] = digest({k: v for k, v in detail.items() if k != "digest"})
    item.update(detail=f"lists/{detail['digest']}.json", detail_digest=detail["digest"])
    (root / item["detail"]).write_text(json.dumps(detail), encoding="utf-8")
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    (root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
    preview.query_params.update({"view": "List", "list": "14"}); app = preview.run()
    assert not app.exception
    assert any("could not be verified" in x.value for x in app.error)


def test_dashboard_comparison_and_share_are_offline(preview):
    app = preview.run(); button(app, "Insights").click().run()
    assert not app.exception and app.metric[0].value == "15"
    assert any("Population: 15 filtered eligible public lists" in x.value for x in app.caption)
    app.text_input(key="insight_q").set_value("no-such-list").run()
    assert app.metric[0].value == "0" and any("No eligible lists match" in x.value for x in app.info)
    button(app, "Reset dashboard").click().run()
    assert app.metric[0].value == "15"
    assert app.multiselect(key="compare_ids").value == ["0", "1"]
    app.multiselect(key="compare_ids").set_value(["14", "2", "3"]).run()
    assert not app.exception and len(app.dataframe[-1].value) == 3
    assert app.selectbox(key="compare_metric").value == "Stars"
    button(app, "Share this view").click().run()
    assert "view=Insights" in app.code[0].value and "compare=14%2C2%2C3" in app.code[0].value
