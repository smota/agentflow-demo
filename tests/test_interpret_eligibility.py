import pytest

from awesome.catalogue import digest
from awesome.interpret_eligibility import (build_prompt, candidate_digest, candidate_fields,
                                            sample_entries, validate_interpretations)
from awesome.lists import FORMAT, parse_readme, profile
from tests.test_lists import MD, REV, meta

PENDING_MD = MD  # a curated-looking README, but stars unavailable -> pending


def build_pending_item():
    parsed = parse_readme(PENDING_MD, "owner/awesome-tools", REV)
    item, detail = profile(meta(stars=None), parsed, PENDING_MD)
    assert item["state"] == "pending"
    return item, detail


def build_list_index(item):
    index = {"format_version": FORMAT, "min_stars": 100, "lists": [item], "counts": {"pending": 1}}
    index["digest"] = digest(index)
    return index


def test_candidate_fields_carries_disclosed_subset_only():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    assert fields["name"] == item["name"]
    assert fields["reason"] == item["reason"]
    assert fields["entry_count"] == item["entry_count"]
    assert len(fields["sample_entries"]) <= 8
    assert set(fields) == {"name", "description", "github_topics", "stars", "reason",
                            "entry_count", "unique_links", "category_count", "sample_entries"}


def test_sample_entries_respects_limit_and_shape():
    item, detail = build_pending_item()
    entries = sample_entries(detail, limit=2)
    assert len(entries) == 2
    assert set(entries[0]) == {"title", "category"}


def test_sample_entries_empty_without_detail():
    assert sample_entries(None) == []


def test_candidate_digest_is_stable_and_sensitive_to_content():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    d1 = candidate_digest(fields)
    d2 = candidate_digest(candidate_fields(item, detail))
    assert d1 == d2
    changed = dict(fields, description="a completely different description")
    assert candidate_digest(changed) != d1


def test_build_prompt_includes_key_facts():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    prompt = build_prompt(fields)
    assert item["name"] in prompt
    assert fields["reason"] in prompt
    assert "Tool 0" in prompt  # a real sample entry title should surface in the prompt


def test_build_prompt_handles_no_sample_entries():
    fields = candidate_fields(build_pending_item()[0], None)
    prompt = build_prompt(fields)
    assert "No parsed README entries" in prompt


def record_for(item, fields, **overrides):
    base = {"list_id": item["id"], "name": item["name"], "candidate_digest": candidate_digest(fields),
            "eligible": True, "confidence": "medium", "reasoning": "Looks like a curated list.",
            "model": "sonnet", "source": "headless-cli", "invoked_at": "2026-09-04T00:00:00Z"}
    base.update(overrides)
    return base


def test_validate_interpretations_round_trips():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    index = build_list_index(item)
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": 1}, "records": [record_for(item, fields)]}
    data["digest"] = digest(data)
    validate_interpretations(data, index)  # no raise


def test_validate_interpretations_rejects_record_for_non_pending_list():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    eligible_item = dict(item, state="eligible")
    index = build_list_index(eligible_item)
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": 1}, "records": [record_for(item, fields)]}
    data["digest"] = digest(data)
    with pytest.raises(ValueError, match="pending"):
        validate_interpretations(data, index)


def test_validate_interpretations_rejects_invalid_confidence():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    index = build_list_index(item)
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": 1}, "records": [record_for(item, fields, confidence="extremely-sure")]}
    data["digest"] = digest(data)
    with pytest.raises(ValueError):
        validate_interpretations(data, index)


def test_validate_interpretations_rejects_duplicate_list_id():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    index = build_list_index(item)
    records = [record_for(item, fields), record_for(item, fields)]
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": 2}, "records": records}
    data["digest"] = digest(data)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_interpretations(data, index)


def test_validate_interpretations_rejects_counts_mismatch():
    item, detail = build_pending_item()
    fields = candidate_fields(item, detail)
    index = build_list_index(item)
    data = {"format_version": 1, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
            "counts": {"records": 2}, "records": [record_for(item, fields)]}
    data["digest"] = digest(data)
    with pytest.raises(ValueError, match="reconcile"):
        validate_interpretations(data, index)
