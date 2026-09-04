import pytest

from awesome.alternatives import (FORMAT, MAX_ALTERNATIVES_PER_HEADING, derive_alternatives,
                                   validate_alternatives, validate_shard)
from awesome.catalogue import digest
from awesome.projects import project_id
from tests.test_projects import build_two_list_index


def full_records(derived):
    records = {}
    for shard in derived["shards"].values():
        for record in shard["projects"]:
            records[record["url"]] = record
    return records


def test_same_heading_grouping_across_lists():
    """`Tool 0` is cited (under different titles) in both fixture lists' `Tools` category, so each
    should list the other as an alternative under that shared heading."""
    index, details = build_two_list_index()
    derived = derive_alternatives(index, details, "2026-09-04T00:00:00Z")
    assert derived["index"]["format_version"] == FORMAT
    records = full_records(derived)
    shared = records["https://example.org/tool/0"]
    assert shared["alternative_count"] >= 1
    headings = {(h["list_id"], h["category"]): h for h in shared["headings"]}
    assert len(headings) == 2
    for heading in shared["headings"]:
        alt_ids = {a["id"] for a in heading["alternatives"]}
        assert shared["id"] not in alt_ids
    validate_alternatives(derived["index"], index, derived["shards"])


def test_alternatives_disclose_citing_list_and_heading():
    index, details = build_two_list_index()
    derived = derive_alternatives(index, details, "2026-09-04T00:00:00Z")
    records = full_records(derived)
    shared = records["https://example.org/tool/0"]
    for heading in shared["headings"]:
        assert heading["list_id"] and heading["list_name"] and heading["category"]
        assert heading["total_alternatives"] >= len(heading["alternatives"])
        assert heading["truncated"] == (heading["total_alternatives"] > len(heading["alternatives"]))


def test_heading_cap_is_disclosed_not_silent():
    """A heading with more distinct projects than the cap truncates, but discloses the true total
    and sets `truncated`, rather than silently dropping entries."""
    md_lines = ["# A huge list\n## Everything\n"]
    for i in range(MAX_ALTERNATIVES_PER_HEADING + 5):
        md_lines.append(f"- [Item {i}](https://example.org/huge/{i}) - Entry {i}.\n")
    md = "".join(md_lines)
    from awesome.catalogue import digest
    from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
    from tests.test_lists import REV, meta
    data = meta(id="999", name="huge/awesome-huge", url="https://github.com/huge/awesome-huge")
    item, detail = profile(data, parse_readme(md, data["name"], REV), md)
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": [item], "counts": {"eligible": 1}}
    index["digest"] = digest(index)
    details = {item["detail"]: detail}
    derived = derive_alternatives(index, details, "2026-09-04T00:00:00Z")
    records = full_records(derived)
    record = records["https://example.org/huge/0"]
    heading = record["headings"][0]
    assert len(heading["alternatives"]) == MAX_ALTERNATIVES_PER_HEADING
    assert heading["total_alternatives"] == MAX_ALTERNATIVES_PER_HEADING + 4  # excludes itself
    assert heading["truncated"] is True
    validate_alternatives(derived["index"], index, derived["shards"])


def test_validate_rejects_unknown_alternative_id(tmp_path):
    index, details = build_two_list_index()
    derived = derive_alternatives(index, details, "2026-09-04T00:00:00Z")
    prefix = next(iter(derived["shards"]))
    shard = derived["shards"][prefix]
    for record in shard["projects"]:
        for heading in record["headings"]:
            if heading["alternatives"]:
                heading["alternatives"][0]["id"] = project_id("https://example.org/nowhere")
                shard["digest"] = digest({k: v for k, v in shard.items() if k != "digest"})
                with pytest.raises(ValueError, match="unknown project"):
                    validate_shard(shard, prefix, index, known_project_ids=set())
                return
    pytest.skip("fixture had no alternatives to tamper with")
