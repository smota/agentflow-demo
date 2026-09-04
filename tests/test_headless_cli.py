import json
import subprocess

import pytest

from awesome.headless_cli import invoke

SCHEMA = {"type": "object", "properties": {"eligible": {"type": "boolean"},
          "confidence": {"type": "string", "enum": ["high", "medium", "low"]}},
          "required": ["eligible", "confidence"]}


class FakeProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def envelope(**overrides):
    base = {"is_error": False, "duration_ms": 1500, "session_id": "abc",
            "total_cost_usd": 0.01, "structured_output": {"eligible": True, "confidence": "high"}}
    base.update(overrides)
    return json.dumps(base)


def test_invoke_success_returns_structured_output(tmp_path):
    def runner(argv, **kwargs):
        assert argv[0] == "claude" and "-p" in argv
        assert "--json-schema" in argv
        return FakeProcess(0, envelope())
    result = invoke("classify this", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is True
    assert result["output"] == {"eligible": True, "confidence": "high"}
    assert isinstance(result["latency_ms"], int)
    assert result["cli_duration_ms"] == 1500


def test_invoke_reports_nonzero_exit_without_raising(tmp_path):
    def runner(argv, **kwargs):
        return FakeProcess(1, "", "boom: some CLI failure")
    result = invoke("x", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is False
    assert "exited 1" in result["error"]


def test_invoke_reports_timeout_without_raising(tmp_path):
    def runner(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 1))
    result = invoke("x", SCHEMA, cwd=tmp_path, timeout=5, runner=runner)
    assert result["ok"] is False
    assert "timed out" in result["error"]


def test_invoke_reports_unparseable_envelope(tmp_path):
    def runner(argv, **kwargs):
        return FakeProcess(0, "not json")
    result = invoke("x", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is False
    assert "parseable" in result["error"]


def test_invoke_reports_cli_error_result(tmp_path):
    def runner(argv, **kwargs):
        return FakeProcess(0, envelope(is_error=True, result="agent refused"))
    result = invoke("x", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is False
    assert "error result" in result["error"]


def test_invoke_reports_missing_structured_output(tmp_path):
    def runner(argv, **kwargs):
        return FakeProcess(0, envelope(structured_output=None))
    result = invoke("x", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is False
    assert "conform" in result["error"]


def test_invoke_rejects_output_missing_required_keys(tmp_path):
    def runner(argv, **kwargs):
        return FakeProcess(0, envelope(structured_output={"eligible": True}))  # missing "confidence"
    result = invoke("x", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is False
    assert "conform" in result["error"]


def test_invoke_rejects_output_with_out_of_enum_value(tmp_path):
    def runner(argv, **kwargs):
        return FakeProcess(0, envelope(structured_output={"eligible": True, "confidence": "very-high"}))
    result = invoke("x", SCHEMA, cwd=tmp_path, runner=runner)
    assert result["ok"] is False
    assert "conform" in result["error"]


def test_invoke_launch_failure_raises_oserror(tmp_path):
    def runner(argv, **kwargs):
        raise OSError("cannot launch process")
    with pytest.raises(OSError):
        invoke("x", SCHEMA, cwd=tmp_path, runner=runner)


def test_invoke_creates_cwd_if_missing(tmp_path):
    workdir = tmp_path / "nested" / "cwd"

    def runner(argv, **kwargs):
        assert kwargs["cwd"] == str(workdir)
        return FakeProcess(0, envelope())
    invoke("x", SCHEMA, cwd=workdir, runner=runner)
    assert workdir.is_dir()
