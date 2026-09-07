import json
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from awesome.catalogue import digest
from awesome.landscape import LandscapeAccumulator, shard_path as landscape_shard_path
from awesome.landscape_layout import layout_landscape
from awesome.network import NetworkAccumulator
from awesome.projects import derive_projects, shard_path as project_shard_path
from tests.test_network import build_network_fixture

GENERATED_AT = "2026-09-04T00:00:00Z"


def write_network_snapshot(directory):
    """Builds a full offline pipeline output (list-index, project-index and network-index, plus
    their shards) under `directory`, mirroring exactly what `tools/derive_projects.py` and
    `tools/derive_network.py` publish -- the Streamlit Network view under test reads the same shapes
    production does. Uses the four-list fixture from `tests/test_network.py` (A/B near-duplicate,
    A/C independent overlap, A/D below the shared-project threshold) so the rendered graph has real
    edges to assert on, unlike the two-list fixture the Search view tests reuse."""
    index, details = build_network_fixture()
    index.update(generated_at=GENERATED_AT,
                 coverage={"scope": "Fixture observations, not a census", "enrichment_pending": 0, "queued_partitions": 0})
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    (directory / "lists").mkdir(parents=True, exist_ok=True)
    for path, detail in details.items():
        (directory / path).write_text(json.dumps(detail), encoding="utf-8")
    (directory / "list-index.json").write_text(json.dumps(index), encoding="utf-8")

    derived = derive_projects(index, details, GENERATED_AT)
    (directory / "projects").mkdir(exist_ok=True)
    accumulator = NetworkAccumulator()
    for prefix, shard in derived["shards"].items():
        (directory / project_shard_path(prefix)).write_text(json.dumps(shard), encoding="utf-8")
        for record in shard["projects"]:
            accumulator.add_project(record)
    (directory / "project-index.json").write_text(json.dumps(derived["index"]), encoding="utf-8")
    network = accumulator.finalize(derived["index"]["digest"], GENERATED_AT)
    (directory / "network-index.json").write_text(json.dumps(network), encoding="utf-8")
    landscape_acc = LandscapeAccumulator(network["list_pairs"])
    for shard in derived["shards"].values():
        for record in shard["projects"]:
            landscape_acc.add_project(record)
    eligible = [item["id"] for item in index["lists"] if item.get("state") == "eligible"]
    layout = layout_landscape(eligible, network["list_pairs"])
    artifact = landscape_acc.finalize(network, layout, eligible, GENERATED_AT)
    (directory / "landscape").mkdir(exist_ok=True)
    for prefix, shard in artifact["shards"].items():
        (directory / landscape_shard_path(prefix)).write_text(json.dumps(shard), encoding="utf-8")
    (directory / "landscape-index.json").write_text(json.dumps(artifact["index"]), encoding="utf-8")
    return index, network


def preview_entry(directory):
    from pathlib import Path
    from awesome.list_ui import render
    render(Path(directory), preview=True)


@pytest.fixture
def preview(tmp_path, monkeypatch):
    directory = tmp_path / ".cache/ui-preview"
    directory.mkdir(parents=True)
    write_network_snapshot(directory)
    (tmp_path / "package.json").write_text('{"version":"2.0.0-alpha.3"}')
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def denied(*args, **kwargs):
        raise AssertionError("Hosted UI attempted networking")

    monkeypatch.setattr(socket.socket, "connect", denied)
    return AppTest.from_function(preview_entry, args=(str(tmp_path),), default_timeout=20)


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_network_view_is_opt_in_not_default(preview):
    app = preview.run()
    assert not app.exception
    assert app.session_state.list_explorer["view"] == "Discover"  # never opens on its own


def test_network_view_shows_landscape_before_a_list_is_chosen(preview):
    app = preview.run()
    button(app, "Explore network").click().run()
    assert not app.exception
    assert app.session_state.list_explorer["view"] == "Network"
    assert not any("Choose a list above" in getattr(x, "value", "") for x in app.info)
    assert len(app.dataframe) >= 1
    nav = app.dataframe[0].value
    assert len(nav) >= 4


def test_network_view_renders_bounded_svg_graph_for_a_near_duplicate_pair(preview):
    # st.html() output (the SVG itself) is not a queryable AppTest element type; the SVG string's
    # own content (escaping, near-duplicate styling, bounds) is unit-tested directly against
    # awesome.network_view in tests/test_network_view.py. This test proves the Streamlit call site
    # actually reaches that render (no exception) and surfaces the same graph accessibly.
    app = preview.run()
    button(app, "Explore network").click().run()
    app.selectbox(key="network_select").select("owner/awesome-a").run()
    assert not app.exception
    caption_text = " ".join(c.value for c in app.caption)
    assert "nearest neighbors of owner/awesome-a" in caption_text
    assert app.selectbox(key="network_open") is not None


def test_network_view_lists_accessible_neighbor_table_with_near_duplicate_flag(preview):
    app = preview.run()
    button(app, "Explore network").click().run()
    app.selectbox(key="network_select").select("owner/awesome-a").run()
    frame = next(df.value for df in app.dataframe if "Near-duplicate" in df.value.columns)
    row = frame[frame["List"] == "owner/awesome-b"].iloc[0]
    assert row["Near-duplicate"] == "Yes"
    assert row["Shared projects"] == 6


def test_hide_clones_filters_neighbor_table(preview):
    app = preview.run()
    button(app, "Explore network").click().run()
    app.selectbox(key="network_select").select("owner/awesome-a").run()
    app.checkbox(key="hide_clones_box").check().run()
    frame = next(df.value for df in app.dataframe if "Near-duplicate" in df.value.columns)
    assert "owner/awesome-b" not in list(frame["List"])
    assert "other/curated-c" in list(frame["List"])
    assert app.session_state.list_explorer["hide_clones"] == "1"


def test_network_view_isolated_list_is_on_the_map(preview):
    app = preview.run()
    button(app, "Explore network").click().run()
    nav = app.dataframe[0].value
    assert "other/curated-d" in list(nav["List"])


def test_list_view_links_into_the_network_view_for_the_same_list(preview):
    app = preview.run()
    app.text_input(key="le_q").set_value("owner/awesome-a").run()
    button(app, "Explore list →").click().run()
    button(app, "See this list's network neighborhood →").click().run()
    assert not app.exception
    assert app.session_state.list_explorer["view"] == "Network"
    assert app.session_state.list_explorer["network_list"] == "111"


def test_network_view_never_asserts_trust_or_quality_language(preview):
    app = preview.run()
    button(app, "Explore network").click().run()
    app.selectbox(key="network_select").select("owner/awesome-a").run()
    rendered_text = " ".join(x.value for x in app.markdown) + " ".join(x.value for x in app.caption)
    for banned in ("high quality", "trusted", "best list", "top rated"):
        assert banned not in rendered_text.lower()


def test_insights_compare_includes_content_set_diff(preview):
    app = preview.run()
    button(app, "Insights").click().run()
    app.multiselect(key="compare_ids").set_value(["111", "333"]).run()
    assert not app.exception
    frames = [df.value for df in app.dataframe]
    assert any("Bucket" in frame.columns and "shared_independent" in list(frame["Bucket"]) for frame in frames)


def test_list_page_shows_signature_caption_and_heading_shelf(preview):
    app = preview.run()
    app.text_input(key="le_q").set_value("owner/awesome-a").run()
    button(app, "Explore list →").click().run()
    captions = " ".join(c.value for c in app.caption)
    assert "composition of citations, not quality" in captions
    category_key = next(box.key for box in app.selectbox if str(box.key).startswith("category_"))
    app.selectbox(key=category_key).select(app.selectbox(key=category_key).options[1]).run()
    assert any("Same shelf" in c.value for c in app.caption)
    assert any("never merged across headings" in c.value for c in app.caption)
