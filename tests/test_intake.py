"""Fixture-based tests for tools/intake.py. No real GitHub issues are touched — every scenario
below drives the real tools.lists.Run / awesome.lists.profile/classify pipeline (or the flag-item
rules) against fakes, proving the auto-resolve/queue logic works against the actual classification
rules rather than a parallel reimplementation.
"""
import json

import pytest

from tests.test_lists import REV, build_index, meta as list_meta
from tools.intake import (
    Decision,
    FixtureIssueSource,
    PROPOSE_LABEL,
    FLAG_LABEL,
    QUEUED_LABEL,
    RESOLVED_LABEL,
    STAGED_LABEL,
    already_processed,
    parse_form_body,
    repo_url_parts,
    resolve_flag,
    resolve_propose,
    run_intake,
)
from tools.lists import Run

MD = "# Awesome things\nA curated list of useful resources.\n\n## Tools\n" + "\n".join(
    f"- [Tool {i}](https://example.org/tool/{i}) - Descriptive prose not republished." for i in range(5))
PENDING_MD = "# Awesome App\nAn application to manage projects.\n## Documentation\n" + "\n".join(
    f"- [Guide {i}](https://docs.example.com/{i})" for i in range(10))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def propose_body(name="owner/eligible-list", url="https://github.com/owner/eligible-list", rationale="Great list."):
    return (f"### List name\n\n{name}\n\n### List URL\n\n{url}\n\n### Rationale\n\n{rationale}\n")


def flag_body(flag_type="Duplicate", entry_url="https://github.com/owner/entry", notes=""):
    notes_text = notes or "_No response_"
    return (f"### Flag type\n\n{flag_type}\n\n### Entry URL\n\n{entry_url}\n\n### Notes\n\n{notes_text}\n")


def test_parse_form_body_extracts_fields_and_blank_optional():
    fields = parse_form_body(flag_body(notes=""))
    assert fields == {"flag-type": "Duplicate", "entry-url": "https://github.com/owner/entry", "notes": ""}


def test_parse_form_body_matches_propose_template_field_ids():
    fields = parse_form_body(propose_body())
    assert set(fields) == {"list-name", "list-url", "rationale"}


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/owner/repo", ("owner", "repo")),
    ("https://github.com/owner/repo/", ("owner", "repo")),
    ("https://gitlab.com/owner/repo", None),
    ("not a url", None),
    ("", None),
])
def test_repo_url_parts(url, expected):
    assert repo_url_parts(url) == expected


def test_already_processed_checks_outcome_labels():
    assert already_processed({"labels": [{"name": STAGED_LABEL}]})
    assert already_processed({"labels": [{"name": QUEUED_LABEL}]})
    assert not already_processed({"labels": [{"name": PROPOSE_LABEL}]})
    assert not already_processed({"labels": []})


# ---------------------------------------------------------------------------
# Propose-list resolution — reuses tools.lists.Run + awesome.lists.profile/classify
# ---------------------------------------------------------------------------

def repo_data(id_=9001, node_id="node-1", full_name="owner/eligible-list", stars=150, private=False,
              description="A curated list of useful resources.", fork=False, parent=None):
    data = {"id": id_, "node_id": node_id, "full_name": full_name,
            "html_url": f"https://github.com/{full_name}", "description": description,
            "private": private, "stargazers_count": stars, "forks_count": 0, "fork": fork,
            "archived": False, "topics": [], "license": None,
            "created_at": "2020-01-01T00:00:00Z", "pushed_at": "2026-01-01T00:00:00Z"}
    if parent:
        data["parent"] = parent
    return data


class FakeApi:
    """Serves both the single-repo REST call and the two GraphQL calls Run.metadata/Run.content
    make, exactly like the real GitHub API — so resolve_propose drives the real classifier."""

    def __init__(self, data, readme_text=MD, revision=REV, request_error=None):
        self.data = data
        self.readme_text = readme_text
        self.revision = revision
        self.request_error = request_error
        self.request_calls = []
        self.graphql_calls = []

    def request(self, endpoint):
        self.request_calls.append(endpoint)
        if self.request_error:
            raise self.request_error
        return self.data

    def graphql(self, query):
        self.graphql_calls.append(query)
        if "defaultBranchRef" in query:
            return {"data": {"r0": {
                "id": self.data["node_id"], "nameWithOwner": self.data["full_name"],
                "url": self.data["html_url"], "description": self.data.get("description") or "",
                "stargazerCount": self.data["stargazers_count"], "forkCount": self.data.get("forks_count", 0),
                "isPrivate": self.data["private"], "isArchived": False, "isFork": False, "parent": None,
                "licenseInfo": None, "defaultBranchRef": {"name": "main", "target": {"oid": self.revision}}}}}
        raw = self.readme_text.encode()
        return {"data": {"r0": {"id": self.data["node_id"], "isPrivate": self.data["private"],
                "f0": {"oid": None, "byteSize": len(raw), "isBinary": False, "text": self.readme_text}}}}


def issue(number=1, body="", labels=None):
    return {"number": number, "title": "t", "body": body, "labels": labels or []}


def test_resolve_propose_eligible_stages_via_real_pipeline(tmp_path):
    api = FakeApi(repo_data())
    run = Run("intake-test", tmp_path, api)
    decision = resolve_propose(issue(body=propose_body()), api, run)
    assert decision.outcome == "staged"
    assert decision.label == STAGED_LABEL
    assert decision.close and decision.close_reason == "completed"
    # Real Run.stage() ran: the candidate is in the staged index the maintainer reviews before publish.
    staged = json.loads((tmp_path / "data/staging/list-index.json").read_text(encoding="utf-8"))
    assert any(item["name"] == "owner/eligible-list" and item["state"] == "eligible" for item in staged["lists"])


def test_resolve_propose_below_star_threshold_resolves_excluded(tmp_path):
    api = FakeApi(repo_data(stars=50))
    run = Run("intake-test", tmp_path, api)
    decision = resolve_propose(issue(body=propose_body()), api, run)
    assert decision.outcome == "resolved"
    assert decision.close_reason == "not planned"
    assert "100" in decision.reason  # classifier's own exclusion reason, not a reimplemented one


def test_resolve_propose_private_repo_resolves_excluded(tmp_path):
    api = FakeApi(repo_data(private=True))
    run = Run("intake-test", tmp_path, api)
    decision = resolve_propose(issue(body=propose_body()), api, run)
    assert decision.outcome == "resolved"
    assert "public" in decision.reason.casefold()


def test_resolve_propose_ambiguous_intent_is_queued_not_guessed(tmp_path):
    api = FakeApi(repo_data(full_name="owner/awesome-app", description="A project management application"),
                  readme_text=PENDING_MD)
    run = Run("intake-test", tmp_path, api)
    decision = resolve_propose(issue(body=propose_body(url="https://github.com/owner/awesome-app")), api, run)
    assert decision.outcome == "queued"
    assert decision.label == QUEUED_LABEL
    assert not decision.close


def test_resolve_propose_rejects_non_github_url_without_any_api_call():
    api = FakeApi(repo_data())
    run_placeholder = object()  # never touched: bad URL short-circuits before Run/API use
    decision = resolve_propose(issue(body=propose_body(url="https://gitlab.com/owner/repo")), api, run_placeholder)
    assert decision.outcome == "resolved" and decision.close_reason == "not planned"
    assert api.request_calls == [] and api.graphql_calls == []


def test_resolve_propose_repo_not_found_resolves_excluded(tmp_path):
    api = FakeApi(repo_data(), request_error=RuntimeError("GitHub request failed; checkpoint retained"))
    run = Run("intake-test", tmp_path, api)
    decision = resolve_propose(issue(body=propose_body()), api, run)
    assert decision.outcome == "resolved" and decision.close_reason == "not planned"


def test_resolve_propose_rate_limit_is_queued_for_retry(tmp_path):
    api = FakeApi(repo_data(), request_error=RuntimeError("GitHub authorization/rate boundary; checkpoint retained, resume after reset"))
    run = Run("intake-test", tmp_path, api)
    decision = resolve_propose(issue(body=propose_body()), api, run)
    assert decision.outcome == "queued"


# ---------------------------------------------------------------------------
# Flag-item resolution
# ---------------------------------------------------------------------------

def published_index_with(url="https://github.com/owner/eligible-list", topics=None):
    index, _ = build_index()
    index["lists"][0]["url"] = url
    index["lists"][0]["topics"] = topics if topics is not None else index["lists"][0]["topics"]
    return index


def test_resolve_flag_unrecognized_type_is_queued():
    decision = resolve_flag(issue(body=flag_body(flag_type="Something else")), FakeApi(repo_data()), None)
    assert decision.outcome == "queued"


def test_resolve_flag_missing_url_resolves_not_planned():
    decision = resolve_flag(issue(body=flag_body(entry_url="")), FakeApi(repo_data()), None)
    assert decision.outcome == "resolved" and decision.close_reason == "not planned"


def test_resolve_flag_duplicate_confirmed_fork_of_published_parent():
    parent_url = "https://github.com/owner/eligible-list"
    index = published_index_with(url=parent_url)
    api = FakeApi(repo_data(full_name="someone/fork-of-eligible-list", fork=True,
                             parent={"full_name": "owner/eligible-list"}))
    body = flag_body(flag_type="Duplicate", entry_url="https://github.com/someone/fork-of-eligible-list")
    decision = resolve_flag(issue(body=body), api, index)
    assert decision.outcome == "resolved" and decision.close_reason == "completed"
    assert "duplicate" in decision.reason.casefold()


def test_resolve_flag_duplicate_not_a_fork_is_queued():
    api = FakeApi(repo_data(full_name="owner/standalone", fork=False))
    body = flag_body(flag_type="Duplicate", entry_url="https://github.com/owner/standalone")
    decision = resolve_flag(issue(body=body), api, None)
    assert decision.outcome == "queued"


def test_resolve_flag_dead_link_confirmed_404(monkeypatch):
    import urllib.error

    class Opener:
        def __call__(self, request, timeout):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    def opener_factory(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    from tools import intake
    decision = intake._resolve_dead_link("https://example.org/gone", opener=opener_factory)
    assert decision.outcome == "resolved" and decision.close_reason == "completed"
    assert "404" in decision.reason


def test_resolve_flag_dead_link_alive_not_reproducible():
    import io

    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def opener_factory(request, timeout):
        return FakeResponse()

    from tools import intake
    decision = intake._resolve_dead_link("https://example.org/alive", opener=opener_factory)
    assert decision.outcome == "resolved" and decision.close_reason == "not planned"


def test_resolve_flag_dead_link_timeout_is_queued():
    def opener_factory(request, timeout):
        raise TimeoutError("timed out")

    from tools import intake
    decision = intake._resolve_dead_link("https://example.org/slow", opener=opener_factory)
    assert decision.outcome == "queued"


def test_resolve_flag_miscategorized_matches_published_is_not_a_bug():
    index, detail = build_index()
    item = index["lists"][0]
    # topics() is deterministic over name/description/github_topics — recompute must equal what's published
    from awesome.lists import topics as compute_topics
    item["topics"] = compute_topics(item)
    body = flag_body(flag_type="Miscategorized", entry_url=item["url"])
    decision = resolve_flag(issue(body=body), FakeApi(repo_data()), index)
    assert decision.outcome == "resolved" and decision.close_reason == "not planned"


def test_resolve_flag_miscategorized_differs_is_resolved_for_refresh():
    index, _ = build_index()
    item = index["lists"][0]
    item["topics"] = ["Deliberately wrong topic"]
    body = flag_body(flag_type="Miscategorized", entry_url=item["url"])
    decision = resolve_flag(issue(body=body), FakeApi(repo_data()), index)
    assert decision.outcome == "resolved" and decision.close_reason == "completed"


def test_resolve_flag_miscategorized_entry_not_published_is_queued():
    body = flag_body(flag_type="Miscategorized", entry_url="https://github.com/owner/not-published")
    decision = resolve_flag(issue(body=body), FakeApi(repo_data()), None)
    assert decision.outcome == "queued"


# ---------------------------------------------------------------------------
# End-to-end orchestration with a fixture issue source (no real GitHub issues touched)
# ---------------------------------------------------------------------------

def test_run_intake_end_to_end_dry_run_makes_no_gh_calls(tmp_path):
    api = FakeApi(repo_data())
    run = Run("intake-test", tmp_path, api)
    source = FixtureIssueSource({
        PROPOSE_LABEL: [issue(number=101, body=propose_body())],
        FLAG_LABEL: [issue(number=102, body=flag_body(flag_type="Dead link", entry_url="https://example.org/x"))],
    })
    results = run_intake(source, api, run, None, dry_run=True)
    assert {r["issue"] for r in results} == {101, 102}
    assert all(r["dry_run"] for r in results)
    assert source.actions == []  # dry-run never calls comment/add_label/close


def test_run_intake_skips_already_processed_issues(tmp_path):
    api = FakeApi(repo_data())
    run = Run("intake-test", tmp_path, api)
    already = issue(number=201, body=propose_body(), labels=[{"name": STAGED_LABEL}])
    source = FixtureIssueSource({PROPOSE_LABEL: [already], FLAG_LABEL: []})
    results = run_intake(source, api, run, None, dry_run=False)
    assert results == []
    assert source.actions == []


def test_run_intake_applies_comment_label_and_close_for_resolved(tmp_path):
    api = FakeApi(repo_data(stars=50))  # excluded -> resolved/closed
    run = Run("intake-test", tmp_path, api)
    source = FixtureIssueSource({PROPOSE_LABEL: [issue(number=301, body=propose_body())], FLAG_LABEL: []})
    results = run_intake(source, api, run, None, dry_run=False)
    assert results[0]["outcome"] == "resolved"
    kinds = [a[0] for a in source.actions]
    assert kinds == ["comment", "add_label", "close"]
    assert source.actions[1] == ("add_label", 301, RESOLVED_LABEL)
    assert source.actions[2] == ("close", 301, "not planned")
