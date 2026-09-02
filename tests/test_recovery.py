import hashlib
import base64
import json
import subprocess
from pathlib import Path

import pytest
from awesome.catalogue import digest
from tools import crawl


@pytest.fixture
def replay(monkeypatch, tmp_path):
    accepted = json.loads((Path(__file__).resolve().parents[1] / "data/catalogue.json").read_text(encoding="utf-8"))
    accepted["sources"] = accepted["sources"][:2]
    ids = {s["id"] for s in accepted["sources"]}
    accepted["candidates"] = [c for c in accepted["candidates"] if c["id"] in ids]
    monkeypatch.setattr(crawl, "ROOT", tmp_path)
    monkeypatch.setattr(crawl, "STAGING", tmp_path / "data/staging/catalogue.json")
    monkeypatch.setattr(crawl, "PUBLISHED", tmp_path / "data/catalogue.json")
    records = []
    for index, source in enumerate(accepted["sources"]):
        raw = f"# Tools\n- [Shared](https://example.com/shared) - A tool\n- [Item {index}](https://example.com/{index})\n".encode()
        source["readme_sha256"] = hashlib.sha256(raw).hexdigest()
        source["extracted_occurrences"] = 2
        cache = crawl.raw_directory(source["id"], source["revision"])
        cache.mkdir(parents=True)
        (cache / "README.md").write_bytes(raw)
        (cache / "LICENSE.txt").write_bytes(source["license_text"].encode())
        records.extend(crawl.extract(raw.decode(), source["id"]))
    accepted["resources"] = crawl.merge_records(records)
    accepted.pop("digest")
    accepted["digest"] = digest(accepted)
    crawl.atomic_json(crawl.PUBLISHED, accepted)
    def forbidden(*args, **kwargs):
        raise AssertionError("Cached replay must not use GitHub")
    monkeypatch.setattr(crawl, "github", forbidden)
    return accepted


def test_interrupt_resume_is_identical_and_preserves_lastgood(replay):
    original = crawl.PUBLISHED.read_bytes()
    with pytest.raises(InterruptedError, match="Injected"):
        crawl.build("exercise", True, 1)
    assert crawl.PUBLISHED.read_bytes() == original
    assert not crawl.STAGING.exists()
    result = crawl.build("exercise", True)
    assert result["digest"] == replay["digest"]
    assert len(result["resources"]) == 3
    assert sum(len(r["occurrences"]) for r in result["resources"]) == 4
    assert crawl.build("exercise", True) == result
    assert crawl.PUBLISHED.read_bytes() == original
    assert not (crawl.ROOT / ".agent-runs/crawler.lock").exists()


@pytest.mark.parametrize("kind", ["checkpoint", "engine", "raw", "accepted", "mode"])
def test_resume_rejects_changed_evidence(replay, monkeypatch, kind):
    with pytest.raises(InterruptedError):
        crawl.build("exercise", True, 1)
    original = crawl.PUBLISHED.read_bytes()
    path = crawl.ROOT / ".agent-runs/crawl/exercise/checkpoint.json"
    if kind == "checkpoint":
        checkpoint = json.loads(path.read_text())
        checkpoint["generated_at"] = "changed"
        crawl.atomic_json(path, checkpoint)
    elif kind == "engine":
        monkeypatch.setattr(crawl, "engine_digest", lambda: "changed")
    elif kind == "raw":
        source = replay["sources"][0]
        (crawl.raw_directory(source["id"], source["revision"]) / "README.md").write_text("changed")
    elif kind == "accepted":
        replay["generated_at"] = "2026-09-03T00:00:00Z"
        replay.pop("digest")
        replay["digest"] = digest(replay)
        crawl.atomic_json(crawl.PUBLISHED, replay)
        original = crawl.PUBLISHED.read_bytes()
    with pytest.raises(ValueError):
        crawl.build("exercise", kind != "mode")
    assert crawl.PUBLISHED.read_bytes() == original
    assert not crawl.STAGING.exists()


def test_writer_exclusion_and_stale_candidate(replay):
    original = crawl.PUBLISHED.read_bytes()
    with crawl.writer_lock():
        with pytest.raises(RuntimeError, match="lock exists"):
            crawl.build("other", True)
        with pytest.raises(RuntimeError, match="lock exists"):
            crawl.publish(replay["digest"])
    candidate = crawl.build("candidate", True)
    candidate["generated_at"] = "2026-09-03T00:00:00Z"
    candidate.pop("digest")
    candidate["digest"] = digest(candidate)
    crawl.atomic_json(crawl.STAGING, candidate)
    with pytest.raises(ValueError, match="Stale acceptance"):
        crawl.publish(replay["digest"])
    assert crawl.PUBLISHED.read_bytes() == original


def test_live_fetch_path_pins_before_processing_and_resumes(replay, monkeypatch):
    calls = []
    monkeypatch.setattr(crawl, "discover", lambda: (replay["candidates"], replay["discovery"]))
    def fake_api(endpoint):
        calls.append(endpoint)
        source = next(s for s in replay["sources"] if endpoint.startswith(f"repos/{s['id']}/"))
        if "/commits/" in endpoint:
            return {"sha": source["revision"]}
        cache = crawl.raw_directory(source["id"], source["revision"])
        license_call = "/license?" in endpoint
        raw = (cache / ("LICENSE.txt" if license_call else "README.md")).read_bytes()
        return {"content": base64.b64encode(raw).decode(), "size": len(raw),
                "path": source["license_path" if license_call else "readme_path"],
                "license": {"spdx_id": "CC0-1.0"}}
    monkeypatch.setattr(crawl, "github", fake_api)
    with pytest.raises(InterruptedError):
        crawl.build("live-fixture", False, 1)
    assert all("/commits/" in endpoint for endpoint in calls[:2])
    first_source_calls = list(calls)
    result = crawl.build("live-fixture")
    assert len(result["resources"]) == 3
    assert len(calls) == 6  # Two pins, then readme/license once per source.
    assert calls[:4] == first_source_calls


def test_disqualified_live_source_fails_before_fetch(replay, monkeypatch):
    replay["candidates"][0]["stars"] = 49999
    monkeypatch.setattr(crawl, "discover", lambda: (replay["candidates"], replay["discovery"]))
    with pytest.raises(ValueError, match="below threshold"):
        crawl.build("disqualified")


@pytest.mark.parametrize("name", ["../escape", "UPPER", "", "a" * 65, "a/b"])
def test_run_path_boundary(name):
    with pytest.raises(ValueError, match="Run ID"):
        crawl.build(name)


def test_retries_are_bounded(monkeypatch):
    calls, sleeps = [], []
    def failure(*args, **kwargs):
        calls.append(1)
        raise subprocess.TimeoutExpired("gh", 45)
    monkeypatch.setattr(crawl.subprocess, "run", failure)
    monkeypatch.setattr(crawl.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="three attempts"):
        crawl.github("unused")
    assert len(calls) == 3
    assert sleeps == [1, 2]


@pytest.mark.parametrize("error", ["401", "403", "429", "rate limit"])
def test_authorization_and_rate_limits_not_retried(monkeypatch, error):
    calls = []
    def failure(*args, **kwargs):
        calls.append(1)
        raise subprocess.CalledProcessError(1, "gh", stderr=error)
    monkeypatch.setattr(crawl.subprocess, "run", failure)
    with pytest.raises(RuntimeError, match="boundary"):
        crawl.github("unused")
    assert len(calls) == 1
