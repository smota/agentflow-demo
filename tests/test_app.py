import socket
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
    assert len(app.metric) == 3
    assert app.metric[1].value == "3"
    app.text_input(key="query").set_value("zzzz-no-resource-matches-this").run()
    assert not app.exception
    assert "No finds" in app.info[0].value
    app.text_input(key="query").set_value("terminal").run()
    assert not app.exception
    assert not app.info
    app.text_input(key="query").set_value("").run()
    app.selectbox(key="source").select("rust-unofficial/awesome-rust").run()
    assert not app.exception
    assert any("v0.1.0" in c.value for c in app.caption)
