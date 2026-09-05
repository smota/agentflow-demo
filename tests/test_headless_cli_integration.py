"""Real, non-mocked integration check for Epic H's headless-CLI mechanism (issue #53). Skipped by
default -- like the rest of this repo's test suite, `pytest -q` never makes real network/subprocess
calls to an external service by default (see `tools/derive_liveness.py`'s tests, which always mock
`_fetch`). This module is the one deliberate exception the epic itself calls for ("the real H1
measurement calls (not mocked) as an integration check"), gated behind an explicit opt-in so CI and
routine local runs stay hermetic and fast:

    RUN_REAL_HEADLESS_CLI_TESTS=1 pytest -q tests/test_headless_cli_integration.py

The actual H1 spike finding (8 real calls, 0 failures, ~11.6s mean latency) was already captured by
running `python -m tools.spike_headless_cli` directly against the real published catalogue -- see
the Epic H report. This test exists so the mechanism has automated, reproducible integration
coverage going forward, not as the sole evidence for H1's own finding.
"""
from __future__ import annotations

import os
import shutil

import pytest

from awesome.headless_cli import invoke

SCHEMA = {"type": "object", "properties": {"ping": {"type": "string", "enum": ["pong"]}},
          "required": ["ping"]}

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_HEADLESS_CLI_TESTS") != "1" or shutil.which("claude") is None,
    reason="Real headless-CLI integration check: opt in with RUN_REAL_HEADLESS_CLI_TESTS=1 "
           "and a `claude` CLI on PATH.",
)


def test_real_headless_cli_round_trips_structured_output(tmp_path):
    result = invoke('Respond with {"ping": "pong"} exactly.', SCHEMA, cwd=tmp_path, timeout=60)
    assert result["ok"] is True
    assert result["output"] == {"ping": "pong"}
    assert isinstance(result["latency_ms"], int) and result["latency_ms"] > 0
