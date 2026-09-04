"""Real published-snapshot acceptance; pure/corruption fixtures live separately."""
import json
import socket
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def action(app, label):
    return next(x for x in app.button if x.label == label)


def test_credential_free_offline_list_app(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    def denied(*args, **kwargs): raise AssertionError("Hosted app attempted networking")
    monkeypatch.setattr(socket.socket, "connect", denied)
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert not app.exception
    index = json.loads((ROOT / "data/list-index.json").read_text(encoding="utf-8"))
    assert app.metric[0].label == "Curated lists"
    assert app.metric[0].value == f"{index['counts']['eligible']:,}"
    app.text_input(key="le_q").set_value("zz-no-list-matches-zz").run()
    assert any("No lists match" in x.value for x in app.info)
    app.text_input(key="le_q").set_value("awesome-selfhosted/awesome-selfhosted").run()
    action(app, "Explore list →").click().run()
    assert app.title[0].value == "awesome-selfhosted/awesome-selfhosted"
    assert int(app.metric[2].value.replace(",", "")) >= 1000
    assert not app.exception


def test_published_threshold_list_and_reset():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    app.text_input(key="le_q").set_value("donovanglover/awesome-calculus").run()
    action(app, "Explore list →").click().run()
    assert app.metric[0].value == "100"
    action(app, "← Back to results").click().run()
    action(app, "Reset discovery").click().run()
    assert app.text_input(key="le_q").value == ""
    action(app, "Next →").click().run()
    assert any("Page 2 of" in x.value for x in app.caption)
    app.selectbox(key="le_sort").select("Name A–Z").run()
    assert any("Page 1 of" in x.value for x in app.caption)
    assert not app.exception


def test_published_content_share_roundtrip():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30)
    app.query_params.update({"q": "selfhosted", "view": "List", "list": "36633370", "content_q": "nextcloud"})
    app.run()
    assert not app.exception
    assert app.text_input(key="content_36633370").value == "nextcloud"
    assert len(app.dataframe[0].value) == 3
    action(app, "Share this view").click().run()
    assert any("private information" in x.value for x in app.warning)
    params = {k: v[0] for k, v in parse_qs(urlsplit(app.code[0].value).query).items()}
    reopened = AppTest.from_file(ROOT / "app.py", default_timeout=30)
    reopened.query_params.update(params); reopened.run()
    assert reopened.session_state.list_explorer == app.session_state.list_explorer
    assert len(reopened.dataframe[0].value) == 3
    assert not reopened.exception


def test_published_repeated_params_story_and_identity():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30)
    app.query_params.update({"q": ["a", "b"], "view": "invalid", "list": "../bad"})
    app.run()
    assert app.text_input(key="le_q").value == ""
    action(app, "Delivery story").click().run()
    assert app.title[0].value == "Built in the open."
    version = json.loads((ROOT / "package.json").read_text())["version"]
    index = json.loads((ROOT / "data/list-index.json").read_text(encoding="utf-8"))
    assert any(f"v{version}" in x.value and index["digest"][:12] in x.value for x in app.caption)
    assert not any("Local design preview" in x.value for x in app.warning)
    assert not app.exception


def test_identity_footer_uses_local_brand_assets_and_safe_external_links():
    from awesome.list_ui import identity_footer

    footer = identity_footer(ROOT / "awesome" / "assets")
    assert 'aria-label="Application identity"' in footer
    assert 'href="https://movetheneedle.info/"' in footer
    assert 'href="https://movetheneedle.info/agent-sdlc/"' in footer
    assert footer.count('target="_blank" rel="noopener noreferrer"') == 2
    assert "Maintained by" in footer and "Move the Needle" in footer
    assert "Built with" in footer and "AgentFlow" in footer
    assert footer.count("data:image/png;base64,") == 2
