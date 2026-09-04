"""Delivery-story manifest, evidence and image-branding contracts."""
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from awesome.delivery import load_story, watermarked_image


ROOT = Path(__file__).resolve().parents[1]


def test_delivery_manifest_has_four_publicly_evidenced_episodes():
    path = ROOT / "data" / "delivery-story.json"
    story = load_story(path)
    assert [item["id"] for item in story["episodes"]] == ["build-1", "build-2", "build-3", "build-4"]
    assert story["episodes"][-1]["tests"] == 409
    assert story["recovery"] == {
        "successfulFreshContext": 2,
        "partialAttemptsRejected": 1,
        "initialGeneration": 0,
        "replacementGeneration": 1,
        "stalePlanExitCode": 4,
        "obsoleteWriterExitCode": 4,
        "publicationAttempts": 2,
        "createdComments": 1,
    }
    raw = path.read_text(encoding="utf-8")
    assert "codex://" not in raw
    assert all(item["url"].startswith("https://") for item in story["evidence"])


def test_consistency_matrix_is_explicit_not_an_invented_score():
    story = json.loads((ROOT / "data" / "delivery-story.json").read_text(encoding="utf-8"))
    assert len(story["consistency"]) == 6
    assert all(row["match"] == "Matched" for row in story["consistency"])
    assert "score" not in story


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
    assert "watermarked_image(APP_ROOT / relative, logo_path)" in module
