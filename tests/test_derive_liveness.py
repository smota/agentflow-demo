import json

import pytest

from awesome.catalogue import digest
from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
from awesome.projects import derive_projects, shard_path as project_shard_path
from awesome.liveness import shard_path
from tests.test_lists import REV, meta
from tools.derive_liveness import build, publish, select_candidates, validate

MD_GH = ("# Awesome things\n## Tools\n"
         "- [Hello World](https://github.com/octocat/hello-world) - A demo repository.\n"
         "- [Other Repo](https://github.com/octocat/other-repo) - Another demo repository.\n"
         "- [Non GitHub](https://example.org/tool) - Not a GitHub project.\n")


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
    return index, derived


def test_select_candidates_only_returns_github_projects(tmp_path):
    data_root = tmp_path / "data"
    write_github_catalogue(data_root)
    candidates = select_candidates(data_root, limit=10, already_have=set())
    assert len(candidates) == 2
    assert {c["owner"] + "/" + c["repo"] for c in candidates} == {"octocat/hello-world", "octocat/other-repo"}


def _fake_fetch(responses):
    def fetch(endpoint):
        return responses.get(endpoint, [])
    return fetch


def test_build_stages_liveness_for_github_projects_only(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_github_catalogue(data_root)
    import tools.derive_liveness as mod
    responses = {
        "repos/octocat/hello-world": {"default_branch": "main", "archived": False, "pushed_at": "2024-01-01T00:00:00Z"},
        "repos/octocat/hello-world/releases?per_page=5": [{"published_at": "2024-01-01T00:00:00Z"}],
        "repos/octocat/other-repo": {"default_branch": "main", "archived": True, "pushed_at": "2023-01-01T00:00:00Z"},
        "repos/octocat/other-repo/releases?per_page=5": [],
    }
    monkeypatch.setattr(mod, "_fetch", _fake_fetch(responses))
    staged = mod.build(run_id="test-run", batch_size=10, data_root=data_root, staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["projects"] == 2
    assert staged["run"]["completed_this_run"] == 2
    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert published["digest"] == staged["digest"]
    validated = validate(data_root=data_root)
    assert validated["digest"] == staged["digest"]


def test_build_skips_not_found_repo_without_aborting(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_github_catalogue(data_root)
    import tools.derive_liveness as mod

    def fetch(endpoint):
        if endpoint == "repos/octocat/hello-world":
            return None  # simulate a real 404: renamed/deleted repo
        return {"default_branch": "main", "archived": False, "pushed_at": "2022-01-01T00:00:00Z"} if "releases" not in endpoint else []

    monkeypatch.setattr(mod, "_fetch", fetch)
    staged = mod.build(run_id="test-run-2", batch_size=10, data_root=data_root, staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["projects"] == 1
    assert staged["run"]["skipped_this_run"] == 1


def test_build_resumes_from_checkpoint_after_interruption(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_github_catalogue(data_root)
    import tools.derive_liveness as mod
    responses = {
        "repos/octocat/hello-world": {"default_branch": "main", "archived": False, "pushed_at": "2024-01-01T00:00:00Z"},
        "repos/octocat/hello-world/releases?per_page=5": [],
        "repos/octocat/other-repo": {"default_branch": "main", "archived": False, "pushed_at": "2024-01-01T00:00:00Z"},
        "repos/octocat/other-repo/releases?per_page=5": [],
    }
    monkeypatch.setattr(mod, "_fetch", _fake_fetch(responses))
    with pytest.raises(InterruptedError):
        mod.build(run_id="resume-run", batch_size=10, interrupt_after=1, data_root=data_root, staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    staged = mod.build(run_id="resume-run", batch_size=10, data_root=data_root, staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["projects"] == 2


def test_incremental_publish_does_not_drop_prior_records(tmp_path, monkeypatch):
    """A later run with a smaller/different batch must merge onto, not replace, what is already
    published -- this artifact grows across many bounded runs, never resets."""
    data_root = tmp_path / "data"
    staging_root = data_root / "staging"
    write_github_catalogue(data_root)
    import tools.derive_liveness as mod
    responses = {
        "repos/octocat/hello-world": {"default_branch": "main", "archived": False, "pushed_at": "2024-01-01T00:00:00Z"},
        "repos/octocat/hello-world/releases?per_page=5": [],
        "repos/octocat/other-repo": {"default_branch": "main", "archived": False, "pushed_at": "2024-01-01T00:00:00Z"},
        "repos/octocat/other-repo/releases?per_page=5": [],
    }
    monkeypatch.setattr(mod, "_fetch", _fake_fetch(responses))
    staged = mod.build(run_id="first", batch_size=1, data_root=data_root, staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged["counts"]["projects"] == 1
    published = publish(staged["digest"], data_root=data_root, staging_root=staging_root)
    assert published["counts"]["projects"] == 1
    staged2 = mod.build(run_id="second", batch_size=10, data_root=data_root, staging_root=staging_root, checkpoint_root=tmp_path / "checkpoints")
    assert staged2["counts"]["projects"] == 2
