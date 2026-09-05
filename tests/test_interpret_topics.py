import pytest

from awesome.catalogue import digest
from awesome.interpret_topics import (CANONICAL_TAGS, as_overrides, build_prompt, label_digest,
                                       normalized_label, validate_interpretations)
from awesome.topics import normalize_topic


def test_normalized_label_matches_normalize_topics_own_fallback_behaviour():
    # For a label normalize_topic() cannot resolve via _SYNONYMS, its fallback output is exactly
    # normalized_label(...) with hyphens instead of spaces -- these two must never drift apart.
    label = "Weird Niche Category"
    assert normalize_topic(label) == normalized_label(label).replace(" ", "-")


def test_normalized_label_empty_for_pure_stopwords():
    assert normalized_label("the a of") == ""


def test_label_digest_stable():
    assert label_digest("weird niche category") == label_digest("weird niche category")
    assert label_digest("a") != label_digest("b")


def test_build_prompt_includes_vocabulary_and_label():
    prompt = build_prompt("weird niche category")
    assert "weird niche category" in prompt
    assert CANONICAL_TAGS[0] in prompt
    assert "none" in prompt


def record(label, tag="machine-learning", confidence="high"):
    return {"label": label, "label_digest": label_digest(label), "tag": tag, "confidence": confidence,
            "model": "sonnet", "source": "headless-cli", "invoked_at": "2026-09-04T00:00:00Z"}


def build_data(records):
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": len(records)}, "records": records}
    data["digest"] = digest(data)
    return data


def test_validate_interpretations_round_trips():
    data = build_data([record("weird niche category")])
    validate_interpretations(data)  # no raise


def test_validate_interpretations_accepts_none_tag():
    data = build_data([record("totally unrelated phrase", tag="none")])
    validate_interpretations(data)  # no raise


def test_validate_interpretations_rejects_tag_outside_closed_vocabulary():
    data = build_data([record("weird niche category", tag="invented-new-tag")])
    with pytest.raises(ValueError, match="closed canonical vocabulary"):
        validate_interpretations(data)


def test_validate_interpretations_rejects_mismatched_label_digest():
    bad = record("weird niche category")
    bad["label_digest"] = "0" * 64
    data = build_data([bad])
    with pytest.raises(ValueError, match="label digest"):
        validate_interpretations(data)


def test_validate_interpretations_rejects_duplicate_label():
    data = build_data([record("weird niche category"), record("weird niche category")])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_interpretations(data)


def test_as_overrides_drops_none_tags():
    data = build_data([record("weird niche category", tag="machine-learning"),
                        record("totally unrelated", tag="none")])
    overrides = as_overrides(data)
    assert overrides == {"weird niche category": "machine-learning"}
