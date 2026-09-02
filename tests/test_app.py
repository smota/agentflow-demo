import socket
import json
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_credential_free_offline_app(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    def denied(*args, **kwargs):
        raise AssertionError("Hosted app attempted networking")
    monkeypatch.setattr(socket.socket, "connect", denied)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
    assert not app.exception
    assert any("3,037 resources" in c.value for c in app.caption)
    app.text_input(key="query").set_value("zzzz-no-resource-matches-this").run()
    assert not app.exception
    assert "No finds" in app.info[0].value
    app.text_input(key="query").set_value("terminal").run()
    assert not app.exception
    assert not app.info
    app.text_input(key="query").set_value("").run()
    app.selectbox(key="source").select("rust-unofficial/awesome-rust").run()
    assert not app.exception
    version = json.loads((Path(__file__).resolve().parents[1] / "package.json").read_text())["version"]
    assert any(f"v{version}" in c.value for c in app.caption)


def test_navigation_share_reset_and_deep_link():
    path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(path, default_timeout=20)
    app.query_params.update({"q": "terminal", "page": "999999", "untrusted": "ignored"})
    app.run()
    assert not app.exception
    assert app.text_input(key="query").value == "terminal"
    assert any("Page 5 of 5" in c.value for c in app.caption)
    app.radio(key="view").set_value("Sources").run()
    assert len(app.expander) == 3
    app.radio(key="view").set_value("Delivery story").run()
    assert not app.exception
    app.radio(key="view").set_value("Discover").run()
    assert app.text_input(key="query").value == "terminal"
    next(b for b in app.button if b.label == "Share this search").click().run()
    assert "private information" in app.warning[0].value
    assert "q=terminal" in app.code[0].value
    assert "untrusted" not in app.code[0].value
    next(b for b in app.button if b.label == "Reset discovery").click().run()
    assert app.text_input(key="query").value == ""
    assert not app.query_params
    assert any("Page 1 of 127" in c.value for c in app.caption)
    next(b for b in app.button if b.label == "Next →").click().run()
    assert any("Page 2 of 127" in c.value for c in app.caption)
    app.selectbox(key="sort").select("Title Z–A").run()
    assert any("Page 1 of 127" in c.value for c in app.caption)
    assert not app.exception


def test_ambiguous_query_parameters():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20)
    app.query_params.update({"q": ["terminal", "rust"], "view": "invalid", "source": "invalid"})
    app.run()
    assert not app.exception
    assert app.text_input(key="query").value == ""
    assert app.selectbox(key="source").value == "All sources"
