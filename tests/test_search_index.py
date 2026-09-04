import json

import pytest

from awesome.catalogue import digest
from awesome.projects import derive_projects
from awesome.search_index import (FORMAT, build_top_index, derive_search_shard,
                                   validate_search_index, validate_search_shard)
from tests.test_projects import build_two_list_index

GENERATED_AT = "2026-09-04T00:00:00Z"


def derive(index, details):
    derived = derive_projects(index, details, GENERATED_AT)
    shard_digests, search_shards, total = {}, {}, 0
    for prefix, project_shard in derived["shards"].items():
        search_shard = derive_search_shard(project_shard, derived["index"]["digest"])
        search_shards[prefix] = search_shard
        shard_digests[prefix] = search_shard["digest"]
        total += len(search_shard["projects"])
    top = build_top_index(derived["index"]["digest"], GENERATED_AT, shard_digests,
                           {"projects": total, "shards": len(shard_digests)})
    return derived, top, search_shards


def full_records(search_shards):
    records = {}
    for shard in search_shards.values():
        for record in shard["projects"]:
            records[record["url"]] = record
    return records


def test_shared_project_across_two_lists_gets_search_record_with_topics_and_independence():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    assert top["format_version"] == FORMAT
    records = full_records(search_shards)
    shared = records["https://example.org/tool/0"]
    assert shared["list_count"] == 2
    # "Tool 0" vs "Tool 0 alias" -- different wording, below the copy-lineage threshold, so this
    # is real independent-citation evidence, not a copy-lineage collapse.
    assert shared["independent_list_count"] == 2
    assert isinstance(shared["topics"], list)


def test_single_list_project_independent_count_is_one():
    index, details = build_two_list_index()
    _, _, search_shards = derive(index, details)
    unique = full_records(search_shards)["https://example.org/only-here"]
    assert unique["list_count"] == 1
    assert unique["independent_list_count"] == 1


def test_validate_search_index_round_trips_with_shards():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    validate_search_index(top, derived["index"], search_shards)  # no raise


def test_validate_search_index_round_trips_index_only():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    validate_search_index(top, derived["index"])  # no raise, shards not required


def test_validate_search_shard_round_trips():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    for prefix, shard in search_shards.items():
        validate_search_shard(shard, prefix, derived["index"])  # no raise


def test_validate_rejects_stale_source_project_index():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    other_project_index = json.loads(json.dumps(derived["index"]))
    other_project_index["counts"]["projects"] = 999999
    other_project_index["digest"] = "0" * 64
    with pytest.raises(ValueError, match="does not match"):
        validate_search_index(top, other_project_index)


def test_validate_rejects_tampered_top_digest():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    top["counts"]["projects"] = 999
    with pytest.raises(ValueError, match="digest"):
        validate_search_index(top, derived["index"])


def test_validate_rejects_tampered_shard_digest():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    prefix = next(iter(search_shards))
    tampered = json.loads(json.dumps(search_shards[prefix]))
    tampered["projects"][0]["title"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        validate_search_index(top, derived["index"], {**search_shards, prefix: tampered})


def test_validate_rejects_independent_count_above_list_count():
    index, details = build_two_list_index()
    derived, top, search_shards = derive(index, details)
    prefix = next(iter(search_shards))
    shard = search_shards[prefix]
    shard["projects"][0]["independent_list_count"] = shard["projects"][0]["list_count"] + 1
    shard["digest"] = digest({k: v for k, v in shard.items() if k != "digest"})
    with pytest.raises(ValueError, match="independent_list_count"):
        validate_search_shard(shard, prefix, derived["index"])
