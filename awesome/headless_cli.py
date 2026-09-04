"""Shared low-level subprocess wrapper for invoking a local headless coding-CLI (Claude Code's
`claude -p`, or another configured CLI) as one more deterministic pipeline input -- never a live
dependency of the hosted Streamlit app (Epic H / issue #53). The maintainer has a CLI subscription,
not API billing, so this deliberately shells out to the same local CLI an interactive session would
use, in non-interactive/"print" mode, rather than calling any hosted API with a new credential.

Every call is a single-prompt, structured-output (`--json-schema`-constrained) subprocess
invocation. The response is validated against the same JSON Schema that was requested (this module
does not trust `--json-schema` acceptance on the CLI side blindly -- see `_conforms`) and reduced to
a small, comparable, storable record: success/failure, the parsed structured payload, observed
wall-clock latency, and enough of the CLI's own reported usage to audit cost without re-deriving it.
Callers (`awesome.interpret_eligibility`, `awesome.interpret_topics`,
`tools/spike_headless_cli.py`) own prompt construction, candidate selection, caching, and
publishing; this module owns only "run one bounded call and tell the truth about what happened."

Deliberately narrow: one prompt in, one validated JSON object (or a disclosed failure) out. No
multi-turn conversation and no tools the invoked session would need beyond answering the prompt.
`cwd` defaults to a neutral directory OUTSIDE this repository (`DEFAULT_CWD`) so the invoked
headless session never auto-discovers this repo's own `CLAUDE.md`/`AGENTS.md` -- those are
operator/workflow instructions for this repository's own agentic development process, irrelevant
(and not safe to silently inherit mid-batch) for a narrow, bounded classification subprocess call.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from awesome.catalogue import digest

FORMAT = 1
DEFAULT_CLI = "claude"
DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT_S = 120
DEFAULT_CWD = Path.home() / ".agent-runs-headless-cli-cwd"


def engine_digest() -> str:
    return digest({"headless_cli": Path(__file__).read_text(encoding="utf-8")})


def _conforms(value: Any, schema: dict) -> bool:
    """Minimal, dependency-free structural check -- object required-keys/enum/type only, enough to
    catch a CLI that returned something outside the requested schema. This module never trusts
    `--json-schema` acceptance on the CLI side alone. Not a general JSON Schema validator; extend
    narrowly if a caller's schema needs a feature this does not cover yet."""
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            return False
        for key in schema.get("required", []):
            if key not in value:
                return False
        for key, sub in schema.get("properties", {}).items():
            if key in value and not _conforms(value[key], sub):
                return False
        return True
    if schema_type == "string":
        if not isinstance(value, str):
            return False
        allowed = schema.get("enum")
        return allowed is None or value in allowed
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True  # unrecognized schema fragment: do not block on it


def invoke(prompt: str, json_schema: dict, *, model: str = DEFAULT_MODEL, cli: str = DEFAULT_CLI,
           cwd: Path | None = None, timeout: int = DEFAULT_TIMEOUT_S, runner=subprocess.run) -> dict:
    """Run one bounded, non-interactive headless-CLI call and return a comparable result record.

    Never raises for an ordinary failure (non-zero exit, timeout, malformed/off-schema output) --
    every one of those is reported as `{"ok": False, "error": "..."}` so a caller's batch loop can
    decide per-candidate whether to skip-and-retry-later or stop the whole batch (mirroring
    `tools/derive_liveness.py`'s own `_fetch` discipline). Only raises `OSError` for a call that
    could not be launched at all, which callers should treat the same as any other subprocess
    launch failure elsewhere in this codebase (a real-environment stop, not a per-candidate skip).
    """
    workdir = Path(cwd) if cwd is not None else DEFAULT_CWD
    workdir.mkdir(parents=True, exist_ok=True)
    argv = [cli, "-p", "--output-format", "json", "--model", model,
            "--json-schema", json.dumps(json_schema, separators=(",", ":")), prompt]
    started = time.monotonic()
    try:
        result = runner(argv, cwd=str(workdir), capture_output=True, text=True,
                         encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"headless CLI call timed out after {timeout}s",
                "latency_ms": int((time.monotonic() - started) * 1000)}
    latency_ms = int((time.monotonic() - started) * 1000)
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").splitlines()[-10:])
        return {"ok": False, "error": f"headless CLI exited {result.returncode}: {tail}",
                "latency_ms": latency_ms}
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "headless CLI did not print a parseable JSON envelope",
                "latency_ms": latency_ms}
    if envelope.get("is_error"):
        return {"ok": False, "error": f"headless CLI reported an error result: {envelope.get('result')!r}",
                "latency_ms": latency_ms}
    payload = envelope.get("structured_output")
    if payload is None or not _conforms(payload, json_schema):
        return {"ok": False, "error": "headless CLI response did not conform to the requested schema",
                "latency_ms": latency_ms}
    return {"ok": True, "output": payload, "latency_ms": latency_ms,
            "cli_duration_ms": envelope.get("duration_ms"), "model": model,
            "session_id": envelope.get("session_id"), "total_cost_usd": envelope.get("total_cost_usd")}
