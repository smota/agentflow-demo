"""Delivery-story manifest, session-ledger rendering inputs, and image-branding contracts.

Schema/shape assertions, not exact-count assertions -- see docs/agent-workflow.md's session-record
architecture. The old exact-match assertions (`episodes == [...]`, `tests == 409`) broke every time
new work landed because the manifest had no incremental unit; a session record per merged PR is that
unit, and this suite asserts the *shape* every session record and the derived index must hold, not a
frozen snapshot of today's count.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from awesome.delivery import load_session_record, load_sessions_index, load_story, watermarked_image
from awesome.sessions import derive_index, load_records, validate_index


ROOT = Path(__file__).resolve().parents[1]


def test_delivery_story_manifest_is_editorial_framing_only():
    story = load_story(ROOT / "data" / "delivery-story.json")
    assert story["schemaVersion"] == 2
    for field in ("kicker", "title", "lede", "claim"):
        assert story["hero"].get(field)
    for field in ("spine", "boundaries", "closing"):
        assert story["narrative"].get(field)
    # The manifest must never regain narrative/test-count/episode-identity fields -- that content
    # now lives in data/sessions/*.json, not this editorial file.
    for legacy_field in ("episodes", "testCheckpoints", "decisions", "commands", "recovery", "consistency"):
        assert legacy_field not in story
    assert all((ROOT / shot["path"]).exists() for shot in story["screenshots"])


def test_sessions_index_validates_and_reconciles_with_raw_records():
    records = load_records(ROOT / "data")
    index = load_sessions_index(ROOT / "data" / "sessions-index.json")
    validate_index(index, records)
    assert index["counts"]["sessions"] == len(records) >= 1
    assert index["counts"]["sessions"] == index["counts"]["pr"] + index["counts"]["rollup"] + index["counts"]["release"]


def test_every_session_record_is_individually_loadable_and_schema_shaped():
    records = load_records(ROOT / "data")
    assert records, "expected at least one migrated session record"
    for session_id in records:
        record = load_session_record(session_id)
        assert record["schemaVersion"] == 1
        assert record["kind"] in ("pr", "rollup", "release")
        assert record["harness"]["platform"]
        assert record["sdlc"]["workflowProfile"] in ("bounded", "standard", "high-assurance", "exploratory")
        assert isinstance(record.get("repository", {}).get("issues"), list)


def test_derive_index_is_a_pure_function_of_its_inputs():
    records = load_records(ROOT / "data")
    first = derive_index(records, generated_at="2026-01-01T00:00:00Z")
    second = derive_index(records, generated_at="2026-01-01T00:00:00Z")
    assert first == second


def test_harness_comparison_reflects_at_least_two_platforms_once_migrated():
    """The plan's own acceptance bar: once historical episodes are migrated alongside Claude's, the
    harness-comparison view must show more than one distinct platform."""
    index = load_sessions_index(ROOT / "data" / "sessions-index.json")
    platforms = {row["platform"] for row in index["harnessComparison"]}
    assert len(platforms) >= 2


def test_tests_over_time_is_chronologically_ordered_not_lexicographically():
    index = load_sessions_index(ROOT / "data" / "sessions-index.json")
    points = index["testsOverTime"]
    assert len(points) >= 2
    counts = [point["testsPassed"] for point in points]
    assert counts == sorted(counts), "tests-over-time must be non-decreasing in merge order"


def test_story_screenshots_receive_logo_and_visible_site_watermark():
    source = ROOT / "docs" / "demo" / "images" / "v0.1-local.png"
    logo = ROOT / "awesome" / "assets" / "move-the-needle-icon.png"
    branded = watermarked_image(source, logo)
    assert branded != source.read_bytes()
    with Image.open(BytesIO(branded)) as image:
        assert image.format == "JPEG"
        assert image.size == Image.open(source).size
    module = (ROOT / "awesome" / "delivery.py").read_text(encoding="utf-8")
    assert 'text = "movetheneedle.info"' in module
    assert "watermarked_image(APP_ROOT / shot" in module
