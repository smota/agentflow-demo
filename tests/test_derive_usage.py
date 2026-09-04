import json

import pytest

from awesome.catalogue import digest
from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
from awesome.projects import derive_projects, shard_path as project_shard_path
from tests.test_lists import REV, meta
from tools.derive_usage import _matches_repo, build, docker_lookup, npm_lookup, publish, pypi_lookup, select_candidates, validate

MD_GH = ("# Awesome things\nA curated list of useful resources.\n\n## Tools\n"
         "- [Hello World](https://github.com/octocat/hello-world) - A demo repository.\n"
         "- [Other Repo](https://github.com/octocat/other-repo) - Another demo repository.\n"
         "- [Third Repo](https://github.com/octocat/third-repo) - A third demo repository.\n")


def write_github_catalogue(data_root):
    data = meta(id="123", name="octocat/awesome-demo", url="https://github.com/octocat/awesome-demo")
    item, detail = profile(data, parse_readme(MD_GH, data["name"], REV), MD_GH)
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": [item], "counts": {"eligible": 1}}
    index["digest"] = digest(index)
    (data_root / "lists").mkdir(parents=True)
    (data_root / item["detail"]).write_text(json.dumps(detail), encoding="utf-8")
    (data_root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
    derived = derive_projects(index, {item["detail"]: detail}, "2026-09-04T00:00:00Z")
    for prefix, shard in derived["shards"].items():
        (data_root / project_shard_path(prefix)).parent.mkdir(parents=True, exist_ok=True)
        (data_root / project_shard_path(prefix)).write_text(json.dumps(shard), encoding="utf-8")
    (data_root / "project-index.json").write_text(json.dumps(derived["index"]), encoding="utf-8")


@pytest.mark.parametrize("value,owner,repo,expected", [
    ("git+https://github.com/octocat/hello-world.git", "octocat", "hello-world", True),
    ("github:octocat/hello-world", "octocat", "hello-world", True),
    ("https://github.com/octocat/hello-world", "octocat", "hello-world", True),
    ("git+https://github.com/someone-else/other.git", "octocat", "hello-world", False),
    ("", "octocat", "hello-world", False),
    (None, "octocat", "hello-world", False),
])
def test_matches_repo(value, owner, repo, expected):
    assert _matches_repo(value, owner, repo) is expected


def test_npm_lookup_accepts_cross_checked_match(monkeypatch):
    import tools.derive_usage as mod

    def fake_get(url):
        if url == "https://registry.npmjs.org/hello-world":
            return {"repository": {"url": "git+https://github.com/octocat/hello-world.git"}}
        if url == "https://api.npmjs.org/downloads/point/last-month/hello-world":
            return {"downloads": 12345}
        return None

    monkeypatch.setattr(mod, "_get", fake_get)
    result = npm_lookup("octocat", "hello-world")
    assert result == {"registry": "npm", "package": "hello-world", "count": 12345,
                       "metric": "downloads_last_month",
                       "matched_via": "npm registry package.json repository.url resolves to this GitHub owner/repo"}


def test_npm_lookup_rejects_mismatched_repository(monkeypatch):
    import tools.derive_usage as mod

    def fake_get(url):
        if url == "https://registry.npmjs.org/hello-world":
            return {"repository": {"url": "git+https://github.com/someone-else/unrelated.git"}}
        return None

    monkeypatch.setattr(mod, "_get", fake_get)
    assert npm_lookup("octocat", "hello-world") is None


def test_pypi_lookup_accepts_project_urls_match(monkeypatch):
    import tools.derive_usage as mod

    def fake_get(url):
        if url == "https://pypi.org/pypi/hello-world/json":
            return {"info": {"project_urls": {"Source": "https://github.com/octocat/hello-world"}}}
        if url == "https://pypistats.org/api/packages/hello-world/recent":
            return {"data": {"last_month": 999}}
        return None

    monkeypatch.setattr(mod, "_get", fake_get)
    result = pypi_lookup("octocat", "hello-world")
    assert result["count"] == 999
    assert result["registry"] == "pypi"


def test_docker_lookup_uses_weaker_namespace_heuristic(monkeypatch):
    import tools.derive_usage as mod

    def fake_get(url):
        if url == "https://hub.docker.com/v2/repositories/octocat/hello-world/":
            return {"pull_count": 555}
        return None

    monkeypatch.setattr(mod, "_get", fake_get)
    result = docker_lookup("octocat", "hello-world")
    assert result["count"] == 555
    assert "weaker" in result["matched_via"]


def test_select_candidates_only_returns_github_projects(tmp_path):
    data_root = tmp_path / "data"
    write_github_catalogue(data_root)
    candidates = select_candidates(data_root, limit=10, already_have=set())
    assert len(candidates) == 3


def test_build_stages_only_projects_with_a_verified_source(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_github_catalogue(data_root)
    import tools.derive_usage as mod

    def fake_npm(owner, repo):
        if repo == "hello-world":
            return {"registry": "npm", "package": repo, "count": 100, "metric": "downloads_last_month", "matched_via": "x"}
        return None

    monkeypatch.setattr(mod, "LOOKUPS", (fake_npm, lambda o, r: None, lambda o, r: None))
    staged = mod.build(run_id="test-run", batch_size=10, data_root=data_root, staging_root=staging_root,
                       checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["projects"] == 1
    assert staged["run"]["skipped_this_run"] == 2
    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert published["digest"] == staged["digest"]
    validated = validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]
