import pytest

from awesome.liveness import (FORMAT, build_record, github_repo, validate_liveness, validate_record,
                               validate_shard)
from awesome.projects import project_id


def test_github_repo_parses_canonical_url():
    assert github_repo("https://github.com/octocat/hello-world") == ("octocat", "hello-world")
    assert github_repo("https://github.com/octocat/hello-world/") == ("octocat", "hello-world")


def test_github_repo_rejects_non_repo_urls():
    assert github_repo("https://example.org/octocat/hello-world") is None
    assert github_repo("https://github.com/octocat") is None
    assert github_repo("https://github.com/octocat/hello-world/issues") is None
    assert github_repo("") is None


def test_build_record_captures_archived_and_pushed_at():
    url = "https://github.com/octocat/hello-world"
    repo = {"default_branch": "main", "archived": True, "pushed_at": "2024-01-01T00:00:00Z"}
    record = build_record(url, "octocat", "hello-world", repo, [], "2026-09-04T00:00:00Z")
    assert record["id"] == project_id(url)
    assert record["archived"] is True
    assert record["last_commit_at"] == "2024-01-01T00:00:00Z"
    assert record["releases"] == {"observed_count": 0, "latest_at": None, "median_interval_days": None}
    validate_record(record, record["id"][:2])


def test_build_record_computes_release_cadence_median():
    url = "https://github.com/octocat/hello-world"
    repo = {"default_branch": "main", "archived": False, "pushed_at": "2024-06-01T00:00:00Z"}
    releases = [
        {"published_at": "2024-01-01T00:00:00Z"},
        {"published_at": "2024-03-01T00:00:00Z"},  # 60 days after Jan 1
        {"published_at": "2024-06-01T00:00:00Z"},  # 92 days after Mar 1
    ]
    record = build_record(url, "octocat", "hello-world", repo, releases, "2026-09-04T00:00:00Z")
    assert record["releases"]["observed_count"] == 3
    assert record["releases"]["latest_at"] == "2024-06-01T00:00:00Z"
    assert record["releases"]["median_interval_days"] == 76  # median(60, 92)
    validate_record(record, record["id"][:2])


def test_build_record_no_releases_is_null_not_zero():
    url = "https://github.com/octocat/hello-world"
    repo = {"default_branch": "main", "archived": False, "pushed_at": None}
    record = build_record(url, "octocat", "hello-world", repo, [], "2026-09-04T00:00:00Z")
    assert record["last_commit_at"] is None
    assert record["releases"]["latest_at"] is None
    assert record["releases"]["median_interval_days"] is None
    validate_record(record, record["id"][:2])


def test_validate_record_rejects_non_github_url():
    record = {"id": project_id("https://example.org/x"), "url": "https://example.org/x",
              "owner": "a", "repo": "b", "archived": False, "releases": {"observed_count": 0, "latest_at": None, "median_interval_days": None},
              "observed_at": "2026-09-04T00:00:00Z"}
    with pytest.raises(ValueError, match="GitHub repository"):
        validate_record(record, record["id"][:2])


def _shard(records: list[dict], prefix: str) -> dict:
    from awesome.catalogue import digest
    shard = {"format_version": FORMAT, "prefix": prefix, "projects": records}
    shard["digest"] = digest(shard)
    return shard


def test_validate_shard_and_liveness_round_trip():
    url = "https://github.com/octocat/hello-world"
    record = build_record(url, "octocat", "hello-world", {"default_branch": "main", "archived": False, "pushed_at": "2024-01-01T00:00:00Z"}, [], "2026-09-04T00:00:00Z")
    prefix = record["id"][:2]
    shard = _shard([record], prefix)
    validate_shard(shard, prefix)
    from awesome.catalogue import digest as _digest
    top_index = {"format_version": FORMAT, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
                 "counts": {"projects": 1, "shards": 1}, "shards": {prefix: shard["digest"]}}
    top_index["digest"] = _digest(top_index)
    validate_liveness(top_index, {prefix: shard}, known_project_ids={record["id"]})


def test_validate_liveness_rejects_unknown_project_id():
    url = "https://github.com/octocat/hello-world"
    record = build_record(url, "octocat", "hello-world", {"default_branch": "main", "archived": False, "pushed_at": None}, [], "2026-09-04T00:00:00Z")
    prefix = record["id"][:2]
    shard = _shard([record], prefix)
    from awesome.catalogue import digest as _digest
    top_index = {"format_version": FORMAT, "generated_at": "2026-09-04T00:00:00Z", "content_policy": "x",
                 "counts": {"projects": 1, "shards": 1}, "shards": {prefix: shard["digest"]}}
    top_index["digest"] = _digest(top_index)
    with pytest.raises(ValueError, match="outside the published catalogue"):
        validate_liveness(top_index, {prefix: shard}, known_project_ids=set())
