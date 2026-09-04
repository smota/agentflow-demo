import json

import pytest

from awesome.catalogue import digest
from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
from awesome.projects import FORMAT, derive_projects, project_id, validate_projects, validate_shard
from tests.test_lists import MD, REV, build_index, meta

GENERATED_AT = "2026-09-04T00:00:00Z"


def second_list():
    """A second eligible list whose README cites one of the first list's URLs plus one unique URL."""
    md = ("# Another curated list\n## Tools\n"
          "- [Tool 0 alias](https://example.org/tool/0) - Different wording, different curator.\n"
          "- [Unique thing](https://example.org/only-here) - Only cited by this list.\n"
          "- [Third thing](https://example.org/third) - Also only cited here.\n")
    data = meta(id="456", name="other/awesome-other", url="https://github.com/other/awesome-other")
    return profile(data, parse_readme(md, data["name"], REV), md)


def build_two_list_index():
    index1, detail1 = build_index()
    item1 = index1["lists"][0]
    item2, detail2 = second_list()
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": [item1, item2],
              "counts": {"eligible": 2}}
    index["digest"] = digest(index)
    details = {item1["detail"]: detail1, item2["detail"]: detail2}
    return index, details


def full_records(derived):
    """Flatten every shard's full project records back into one list, keyed by url, for
    assertions that need occurrence detail (which only lives in shards, not the summary index)."""
    records = {}
    for shard in derived["shards"].values():
        for record in shard["projects"]:
            records[record["url"]] = record
    return records


def test_dedup_by_canonical_url_across_lists():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    assert derived["index"]["format_version"] == FORMAT
    records = full_records(derived)
    shared = records["https://example.org/tool/0"]
    assert shared["list_count"] == 2
    assert shared["occurrence_count"] == 2
    assert {occ["list_id"] for occ in shared["occurrences"]} == {"123", "456"}
    assert shared["id"] == project_id("https://example.org/tool/0")
    unique = records["https://example.org/only-here"]
    assert unique["list_count"] == 1
    top = derived["index"]
    assert top["counts"]["projects"] == len(records)
    assert top["counts"]["occurrences"] == sum(r["occurrence_count"] for r in records.values())
    assert top["counts"]["shards"] == len(derived["shards"])
    assert set(top["shards"]) == set(derived["shards"])
    # The tiny top index only carries a prefix -> shard-digest map; every actual project field
    # (including which projects sort first by list_count) lives in the shard itself.
    for prefix, shard_digest in top["shards"].items():
        assert derived["shards"][prefix]["digest"] == shard_digest
    # Within a shard, highest-distinct-list-count projects still sort first.
    shared_shard = derived["shards"][shared["id"][:2]]
    if len(shared_shard["projects"]) > 1:
        assert shared_shard["projects"][0]["list_count"] >= shared_shard["projects"][-1]["list_count"]


def test_repeated_citation_within_one_list_does_not_inflate_list_count():
    """A single list citing the same URL twice (e.g. under two categories) must not look like
    cross-list agreement: list_count counts distinct lists, occurrence_count counts raw entries."""
    md = ("# A curated list\n## Category A\n- [Dup](https://example.org/dup) - First mention.\n"
          "## Category B\n- [Dup again](https://example.org/dup) - Second mention, same list.\n"
          "## Category C\n- [Other](https://example.org/other-thing) - Third link.\n"
          "## Category D\n- [Another](https://example.org/another-thing) - Fourth link.\n")
    data = meta(id="789", name="solo/awesome-solo", url="https://github.com/solo/awesome-solo")
    item, detail = profile(data, parse_readme(md, data["name"], REV), md)
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": [item], "counts": {"eligible": 1}}
    index["digest"] = digest(index)
    derived = derive_projects(index, {item["detail"]: detail}, GENERATED_AT)
    dup = full_records(derived)["https://example.org/dup"]
    assert dup["occurrence_count"] == 2
    assert dup["list_count"] == 1
    validate_projects(derived["index"], index, derived["shards"])  # no raise


def test_occurrence_preserves_per_list_text_not_a_merged_description():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    shared = full_records(derived)["https://example.org/tool/0"]
    titles = {occ["list_id"]: occ["title"] for occ in shared["occurrences"]}
    assert titles["123"] == "Tool 0"
    assert titles["456"] == "Tool 0 alias"


def test_non_eligible_and_pending_lists_are_excluded():
    index, details = build_two_list_index()
    index["lists"][1]["state"] = "pending"
    derived = derive_projects(index, details, GENERATED_AT)
    assert "https://example.org/only-here" not in full_records(derived)


def test_validate_projects_round_trips_index_only():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    validate_projects(derived["index"], index)  # no raise, shards not required


def test_validate_projects_round_trips_with_shards():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    validate_projects(derived["index"], index, derived["shards"])  # no raise


def test_validate_shard_round_trips():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    for prefix, shard in derived["shards"].items():
        validate_shard(shard, prefix, index)  # no raise


def test_validate_rejects_stale_source_index():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    other_index = json.loads(json.dumps(index))
    other_index["lists"][0]["stars"] = 999999
    other_index["digest"] = digest(other_index)
    with pytest.raises(ValueError, match="does not match"):
        validate_projects(derived["index"], other_index)


def test_validate_rejects_tampered_digest():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    data = derived["index"]
    data["counts"]["projects"] = 999
    with pytest.raises(ValueError, match="digest"):
        validate_projects(data, index)


def test_validate_rejects_shard_digest_tampering():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    prefix = next(iter(derived["shards"]))
    tampered = json.loads(json.dumps(derived["shards"][prefix]))
    tampered["projects"][0]["title"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        validate_projects(derived["index"], index, {**derived["shards"], prefix: tampered})


@pytest.mark.parametrize("field,value", [("list_name", "tampered"), ("list_url", "https://example.org/wrong")])
def test_validate_rejects_occurrence_identity_mismatch(field, value):
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    prefix = next(iter(derived["shards"]))
    shard = derived["shards"][prefix]
    shard["projects"][0]["occurrences"][0][field] = value
    shard["digest"] = digest({k: v for k, v in shard.items() if k != "digest"})
    with pytest.raises(ValueError, match="identity mismatch"):
        validate_shard(shard, prefix, index)


def test_validate_rejects_unknown_list_reference():
    index, details = build_two_list_index()
    derived = derive_projects(index, details, GENERATED_AT)
    prefix = next(iter(derived["shards"]))
    shard = derived["shards"][prefix]
    shard["projects"][0]["occurrences"][0]["list_id"] = "999999"
    shard["digest"] = digest({k: v for k, v in shard.items() if k != "digest"})
    with pytest.raises(ValueError, match="non-eligible or unknown"):
        validate_shard(shard, prefix, index)
