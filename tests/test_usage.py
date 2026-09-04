import pytest

from awesome.catalogue import digest
from awesome.usage import FORMAT, validate_record, validate_shard, validate_usage
from awesome.projects import project_id


def _record(**overrides):
    url = "https://github.com/octocat/hello-world"
    record = {"id": project_id(url), "url": url, "owner": "octocat", "repo": "hello-world",
              "sources": [{"registry": "npm", "package": "hello-world", "count": 4200,
                           "metric": "downloads_last_month",
                           "matched_via": "npm registry package.json repository.url resolves to this GitHub owner/repo"}],
              "observed_at": "2026-09-04T00:00:00Z"}
    record.update(overrides)
    return record


def test_validate_record_accepts_well_formed_source():
    record = _record()
    validate_record(record, record["id"][:2])


def test_validate_record_rejects_non_github_url():
    record = _record(url="https://example.org/x", id=project_id("https://example.org/x"))
    with pytest.raises(ValueError, match="GitHub project URL"):
        validate_record(record, record["id"][:2])


def test_validate_record_requires_at_least_one_source():
    record = _record(sources=[])
    with pytest.raises(ValueError, match="at least one matched source"):
        validate_record(record, record["id"][:2])


def test_validate_record_rejects_duplicate_registry():
    record = _record()
    record["sources"] = record["sources"] * 2
    with pytest.raises(ValueError, match="Duplicate registry"):
        validate_record(record, record["id"][:2])


def test_validate_source_rejects_negative_count():
    record = _record()
    record["sources"][0]["count"] = -1
    with pytest.raises(ValueError, match="non-negative"):
        validate_record(record, record["id"][:2])


def test_validate_shard_and_usage_round_trip():
    record = _record()
    prefix = record["id"][:2]
    shard = {"format_version": FORMAT, "prefix": prefix, "projects": [record]}
    shard["digest"] = digest(shard)
    validate_shard(shard, prefix)
    top_index = {"format_version": FORMAT, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
                 "counts": {"projects": 1, "shards": 1}, "shards": {prefix: shard["digest"]}}
    top_index["digest"] = digest(top_index)
    validate_usage(top_index, {prefix: shard}, known_project_ids={record["id"]})


def test_validate_usage_rejects_unknown_project_id():
    record = _record()
    prefix = record["id"][:2]
    shard = {"format_version": FORMAT, "prefix": prefix, "projects": [record]}
    shard["digest"] = digest(shard)
    top_index = {"format_version": FORMAT, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
                 "counts": {"projects": 1, "shards": 1}, "shards": {prefix: shard["digest"]}}
    top_index["digest"] = digest(top_index)
    with pytest.raises(ValueError, match="outside the published catalogue"):
        validate_usage(top_index, {prefix: shard}, known_project_ids=set())
