from datetime import datetime, timezone

from awesome.vitality import liveness_status, project_profile, usage_total


PROJECT = {"id": "abc123", "url": "https://github.com/octocat/hello-world", "title": "Hello World",
           "list_count": 2, "occurrence_count": 2, "occurrences": []}


def test_project_profile_joins_all_signals():
    profile = project_profile(PROJECT, liveness_record={"archived": False}, usage_record={"sources": []},
                               alternatives_record={"headings": []})
    assert profile["id"] == PROJECT["id"]
    assert profile["liveness"] == {"archived": False}
    assert profile["usage"] == {"sources": []}
    assert profile["alternatives"] == {"headings": []}


def test_project_profile_missing_signals_are_none_not_defaults():
    profile = project_profile(PROJECT)
    assert profile["liveness"] is None
    assert profile["usage"] is None
    assert profile["alternatives"] is None


def test_liveness_status_unknown_when_not_observed():
    assert liveness_status(None) == {"bucket": "unknown", "label": "Not yet observed", "days_since_commit": None}


def test_liveness_status_archived_takes_priority():
    record = {"archived": True, "last_commit_at": "2020-01-01T00:00:00Z"}
    status = liveness_status(record)
    assert status["bucket"] == "archived"
    assert status["days_since_commit"] is None


def test_liveness_status_buckets_by_recency():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    active = liveness_status({"archived": False, "last_commit_at": "2026-08-01T00:00:00Z"}, now=now)
    assert active["bucket"] == "active"
    slowing = liveness_status({"archived": False, "last_commit_at": "2026-03-01T00:00:00Z"}, now=now)
    assert slowing["bucket"] == "slowing"
    stale = liveness_status({"archived": False, "last_commit_at": "2020-01-01T00:00:00Z"}, now=now)
    assert stale["bucket"] == "stale"


def test_liveness_status_no_push_activity_is_unknown_not_stale():
    status = liveness_status({"archived": False, "last_commit_at": None})
    assert status["bucket"] == "unknown"


def test_usage_total_not_observed_when_no_sources():
    assert usage_total(None) == {"observed": False, "sources": []}
    assert usage_total({"sources": []}) == {"observed": False, "sources": []}


def test_usage_total_preserves_individual_sources():
    sources = [{"registry": "npm", "count": 10, "metric": "downloads_last_month",
                "package": "x", "matched_via": "y"}]
    result = usage_total({"sources": sources})
    assert result["observed"] is True
    assert result["sources"] == sources


def test_resolve_project_profile_unknown_project():
    from awesome.vitality import resolve_project_profile
    fake_loader = lambda idx, path, prefix: None
    assert resolve_project_profile("unknown_pid", fake_loader) is None


def test_resolve_project_profile_with_mock_loader():
    from awesome.vitality import resolve_project_profile

    pid = "ab1234"
    mock_db = {
        ("project-index.json", "projects/ab.json", "ab"): {
            "projects": [{"id": pid, "title": "My Tool", "url": "https://example.org", "list_count": 3, "occurrence_count": 4, "occurrences": []}]
        },
        ("liveness-index.json", "liveness/ab.json", "ab"): {
            "projects": [{"id": pid, "archived": False, "last_commit_at": "2026-09-01T00:00:00Z"}]
        },
        ("usage-index.json", "usage/ab.json", "ab"): {
            "projects": [{"id": pid, "sources": [{"registry": "npm", "count": 100}]}]
        },
        ("alternatives-index.json", "alternatives/ab.json", "ab"): {
            "projects": [{"id": pid, "headings": []}]
        },
    }

    loader = lambda idx, path, prefix: mock_db.get((idx, path, prefix))

    profile = resolve_project_profile(pid, loader)
    assert profile is not None
    assert profile["id"] == pid
    assert profile["title"] == "My Tool"
    assert profile["liveness"]["last_commit_at"] == "2026-09-01T00:00:00Z"
    assert profile["usage"]["sources"][0]["registry"] == "npm"
    assert profile["alternatives"]["headings"] == []
