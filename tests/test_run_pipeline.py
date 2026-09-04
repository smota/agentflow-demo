import json

import pytest

from awesome.catalogue import digest
from awesome.interpret_eligibility import CONTENT_POLICY as INTERP_CONTENT_POLICY
from awesome.interpret_eligibility import FORMAT as INTERP_FORMAT
from awesome.interpret_eligibility import candidate_digest, candidate_fields
from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
from awesome.projects import derive_projects, shard_path as project_shard_path
from tests.test_lists import MD, REV, build_index, meta
from tests.test_projects import build_two_list_index
import tools.run_pipeline as run_pipeline


def write_list_snapshot(root, index, detail):
    path = root / index["lists"][0]["detail"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(detail), encoding="utf-8")
    (root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")


class FakeProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


# --- verify_list_stage / verify_project_stage: the unattended digest-confirmation gate itself ---

def test_verify_list_stage_accepts_valid_candidate(tmp_path):
    data_root = tmp_path / "data"
    index, detail = build_index()
    write_list_snapshot(data_root / "staging", index, detail)
    verified = run_pipeline.verify_list_stage(index["digest"], data_root)
    assert verified["digest"] == index["digest"]


def test_verify_list_stage_rejects_tampered_shard(tmp_path):
    data_root = tmp_path / "data"
    index, detail = build_index()
    write_list_snapshot(data_root / "staging", index, detail)
    shard_path = data_root / "staging" / index["lists"][0]["detail"]
    tampered = json.loads(shard_path.read_text(encoding="utf-8"))
    tampered["entries"][0]["title"] = "tampered"
    shard_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(run_pipeline.StepFailed):
        run_pipeline.verify_list_stage(index["digest"], data_root)


def test_verify_list_stage_rejects_digest_mismatch(tmp_path):
    """A `stage` process that lied about its own printed digest is never trusted."""
    data_root = tmp_path / "data"
    index, detail = build_index()
    write_list_snapshot(data_root / "staging", index, detail)
    with pytest.raises(run_pipeline.StepFailed):
        run_pipeline.verify_list_stage("0" * 64, data_root)


def test_verify_project_stage_accepts_valid_candidate(tmp_path):
    data_root = tmp_path / "data"
    index, details = build_two_list_index()
    data_root.mkdir(parents=True)
    (data_root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
    derived = derive_projects(index, details, "2026-09-04T00:00:00Z")
    staging = data_root / "staging"
    for prefix, shard in derived["shards"].items():
        (staging / project_shard_path(prefix)).parent.mkdir(parents=True, exist_ok=True)
        (staging / project_shard_path(prefix)).write_text(json.dumps(shard), encoding="utf-8")
    (staging / "project-index.json").write_text(json.dumps(derived["index"]), encoding="utf-8")
    verified = run_pipeline.verify_project_stage(derived["index"]["digest"], data_root)
    assert verified["digest"] == derived["index"]["digest"]


# --- verify_interpretation_stage: H2's own digest-confirmation gate (issue #53) ---

def build_pending_list_index():
    data = meta(id="999", name="owner/awesome-ambiguous",
                url="https://github.com/owner/awesome-ambiguous", stars=None)
    item, detail = profile(data, parse_readme(MD, data["name"], REV), MD)
    assert item["state"] == "pending"
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": [item], "counts": {"pending": 1}}
    index["digest"] = digest(index)
    return index, item, detail


def build_interpretations_index(item, detail):
    fields = candidate_fields(item, detail)
    record = {"list_id": item["id"], "name": item["name"], "candidate_digest": candidate_digest(fields),
              "eligible": True, "confidence": "medium", "reasoning": "Looks like a curated list.",
              "model": "sonnet", "source": "headless-cli", "invoked_at": "2026-09-04T00:00:00Z"}
    data = {"format_version": INTERP_FORMAT, "generated_at": "2026-09-04T00:00:00Z",
            "content_policy": INTERP_CONTENT_POLICY, "counts": {"records": 1}, "records": [record]}
    data["digest"] = digest(data)
    return data


def test_verify_interpretation_stage_accepts_valid_candidate(tmp_path):
    data_root = tmp_path / "data"
    list_index, item, detail = build_pending_list_index()
    (data_root / "list-index.json").parent.mkdir(parents=True, exist_ok=True)
    (data_root / "list-index.json").write_text(json.dumps(list_index), encoding="utf-8")
    interp = build_interpretations_index(item, detail)
    (data_root / "staging").mkdir(parents=True, exist_ok=True)
    (data_root / "staging" / "interpretations-index.json").write_text(json.dumps(interp), encoding="utf-8")
    verified = run_pipeline.verify_interpretation_stage(interp["digest"], data_root)
    assert verified["digest"] == interp["digest"]


def test_verify_interpretation_stage_rejects_digest_mismatch(tmp_path):
    data_root = tmp_path / "data"
    list_index, item, detail = build_pending_list_index()
    (data_root).mkdir(parents=True, exist_ok=True)
    (data_root / "list-index.json").write_text(json.dumps(list_index), encoding="utf-8")
    interp = build_interpretations_index(item, detail)
    (data_root / "staging").mkdir(parents=True, exist_ok=True)
    (data_root / "staging" / "interpretations-index.json").write_text(json.dumps(interp), encoding="utf-8")
    with pytest.raises(run_pipeline.StepFailed):
        run_pipeline.verify_interpretation_stage("0" * 64, data_root)


def test_verify_interpretation_stage_rejects_record_for_non_pending_list(tmp_path):
    data_root = tmp_path / "data"
    list_index, item, detail = build_pending_list_index()
    list_index["lists"][0]["state"] = "eligible"  # candidate is no longer pending in list-index.json
    list_index["digest"] = digest({k: v for k, v in list_index.items() if k != "digest"})
    (data_root).mkdir(parents=True, exist_ok=True)
    (data_root / "list-index.json").write_text(json.dumps(list_index), encoding="utf-8")
    interp = build_interpretations_index(item, detail)
    (data_root / "staging").mkdir(parents=True, exist_ok=True)
    (data_root / "staging" / "interpretations-index.json").write_text(json.dumps(interp), encoding="utf-8")
    with pytest.raises(run_pipeline.StepFailed):
        run_pipeline.verify_interpretation_stage(interp["digest"], data_root)


# --- run_pipeline orchestration: sequencing, abort-on-failure, structured log ---

def build_fake_run_cli(index, details, state):
    def fake_run_cli(module_args, root, python=None):
        module, command = module_args[0], module_args[1]
        data_root = root / "data"
        staging = data_root / "staging"
        if module == "tools.lists" and command in ("discover", "enrich", "profiles"):
            return FakeProcess(0, "{}")
        if module == "tools.lists" and command == "stage":
            write_list_snapshot(staging, index, details[index["lists"][0]["detail"]])
            for detail_path, detail in details.items():
                (staging / detail_path).parent.mkdir(parents=True, exist_ok=True)
                (staging / detail_path).write_text(json.dumps(detail), encoding="utf-8")
            (staging / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
            return FakeProcess(0, json.dumps({"counts": index["counts"], "digest": index["digest"]}))
        if module == "tools.lists" and command == "publish":
            for detail_path, detail in details.items():
                (data_root / detail_path).parent.mkdir(parents=True, exist_ok=True)
                (data_root / detail_path).write_text(json.dumps(detail), encoding="utf-8")
            (data_root / "list-index.json").write_text(json.dumps(index), encoding="utf-8")
            return FakeProcess(0, json.dumps({"counts": index["counts"], "digest": index["digest"]}))
        if module == "tools.lists" and command == "validate":
            return FakeProcess(0, json.dumps({"counts": index["counts"], "digest": index["digest"]}))
        if module == "tools.derive_projects" and command == "stage":
            derived = derive_projects(index, details, "2026-09-04T00:00:00Z")
            state["derived"] = derived
            for prefix, shard in derived["shards"].items():
                path = staging / project_shard_path(prefix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(shard), encoding="utf-8")
            (staging / "project-index.json").write_text(json.dumps(derived["index"]), encoding="utf-8")
            return FakeProcess(0, json.dumps({"counts": derived["index"]["counts"], "digest": derived["index"]["digest"]}))
        if module == "tools.derive_projects" and command == "publish":
            derived = state["derived"]
            for prefix, shard in derived["shards"].items():
                path = data_root / project_shard_path(prefix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(shard), encoding="utf-8")
            (data_root / "project-index.json").write_text(json.dumps(derived["index"]), encoding="utf-8")
            return FakeProcess(0, json.dumps({"counts": derived["index"]["counts"], "digest": derived["index"]["digest"]}))
        if module == "tools.derive_projects" and command == "validate":
            derived = state["derived"]
            return FakeProcess(0, json.dumps({"counts": derived["index"]["counts"], "digest": derived["index"]["digest"]}))
        raise AssertionError(f"unexpected step invoked: {module_args}")
    return fake_run_cli


def test_run_pipeline_success_publishes_and_writes_structured_log(tmp_path, monkeypatch):
    index, details = build_two_list_index()
    monkeypatch.setattr(run_pipeline, "run_cli", build_fake_run_cli(index, details, {}))

    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path, log_dir=tmp_path / "logs")

    assert log["status"] == "success"
    assert [s["name"] for s in log["steps"]] == [
        "discover", "enrich", "profiles", "lists-stage", "lists-publish", "lists-validate",
        "projects-stage", "projects-publish", "projects-validate", "interpretation-build"]
    # H2's optional stage is opt-in (issue #53): off by default, so it shows up as an explicit
    # skipped step -- never silently absent, and never blocking the core lists/projects sequence.
    interpretation_step = log["steps"][-1]
    assert interpretation_step["status"] == "skipped"
    assert "opt-in" in interpretation_step["reason"]
    assert (tmp_path / "data" / "list-index.json").exists()
    assert (tmp_path / "data" / "project-index.json").exists()

    json_logs = list((tmp_path / "logs").glob("*.json"))
    md_logs = list((tmp_path / "logs").glob("*.md"))
    assert len(json_logs) == 1 and len(md_logs) == 1
    written = json.loads(json_logs[0].read_text(encoding="utf-8"))
    assert written["status"] == "success" and written["started_at"] and written["finished_at"]
    assert all(step.get("status") in ("ok", "skipped") for step in written["steps"])
    assert "lists-publish" in md_logs[0].read_text(encoding="utf-8")


def test_run_pipeline_skips_requested_early_stages(tmp_path, monkeypatch):
    index, details = build_two_list_index()
    monkeypatch.setattr(run_pipeline, "run_cli", build_fake_run_cli(index, details, {}))

    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path,
                                     skip=("discover", "enrich", "profiles"))

    skipped = {s["name"]: s for s in log["steps"] if s.get("status") == "skipped"}
    # "interpretation-build" is always in `skipped` too when H2 is not explicitly enabled (issue
    # #53's opt-in default) -- distinct from the explicitly-requested early-stage skips.
    assert set(skipped) == {"discover", "enrich", "profiles", "interpretation-build"}
    assert log["status"] == "success"


def test_run_pipeline_aborts_before_publish_on_stage_failure(tmp_path, monkeypatch):
    index, details = build_two_list_index()
    fake = build_fake_run_cli(index, details, {})

    def failing_stage(module_args, root, python=None):
        if module_args[0] == "tools.lists" and module_args[1] == "stage":
            return FakeProcess(1, "", "boom: engine changed")
        return fake(module_args, root, python)

    monkeypatch.setattr(run_pipeline, "run_cli", failing_stage)
    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path,
                                     skip=("discover", "enrich", "profiles"))

    assert log["status"] == "failed"
    names = [s["name"] for s in log["steps"]]
    assert "lists-stage" in names and "lists-publish" not in names
    assert not (tmp_path / "data" / "list-index.json").exists()


def test_run_pipeline_never_publishes_on_digest_mismatch(tmp_path, monkeypatch):
    """Even if `stage` exits 0, a printed digest that doesn't match the staged bytes on disk
    must never reach `publish` -- this is the independent re-verification gate itself."""
    index, details = build_two_list_index()
    fake = build_fake_run_cli(index, details, {})

    def lying_stage(module_args, root, python=None):
        if module_args[0] == "tools.lists" and module_args[1] == "stage":
            result = fake(module_args, root, python)
            payload = json.loads(result.stdout)
            payload["digest"] = "0" * 64
            return FakeProcess(0, json.dumps(payload))
        return fake(module_args, root, python)

    monkeypatch.setattr(run_pipeline, "run_cli", lying_stage)
    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path,
                                     skip=("discover", "enrich", "profiles"))

    assert log["status"] == "failed"
    assert "digest" in log["failure"].casefold()
    names = [s["name"] for s in log["steps"]]
    assert "lists-publish" not in names
    assert not (tmp_path / "data" / "list-index.json").exists()


def test_run_pipeline_preserves_last_good_snapshot_on_project_stage_failure(tmp_path, monkeypatch):
    """A failure after the list index already published must not touch the previous project
    catalogue -- projects-publish never runs, so there is nothing to roll back."""
    index, details = build_two_list_index()
    fake = build_fake_run_cli(index, details, {})
    previous_projects = {"format_version": 2, "digest": "existing"}
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "project-index.json").write_text(json.dumps(previous_projects), encoding="utf-8")

    def failing_project_stage(module_args, root, python=None):
        if module_args[0] == "tools.derive_projects" and module_args[1] == "stage":
            return FakeProcess(1, "", "boom")
        return fake(module_args, root, python)

    monkeypatch.setattr(run_pipeline, "run_cli", failing_project_stage)
    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path,
                                     skip=("discover", "enrich", "profiles"))

    assert log["status"] == "failed"
    assert (tmp_path / "data" / "list-index.json").exists()  # lists side completed and published
    still_there = json.loads((tmp_path / "data" / "project-index.json").read_text(encoding="utf-8"))
    assert still_there == previous_projects  # untouched last-good snapshot


# --- run_pipeline: optional H2 stage wiring (issue #53), opt-in and never blocking the core publish ---

def empty_interpretations_artifact():
    data = {"format_version": INTERP_FORMAT, "generated_at": "2026-09-04T00:00:00Z",
            "content_policy": INTERP_CONTENT_POLICY, "counts": {"records": 0}, "records": []}
    data["digest"] = digest(data)
    return data


def build_fake_run_cli_with_interpretation(index, details, state, interpretation_behavior="ok"):
    base = build_fake_run_cli(index, details, state)

    def fake_run_cli(module_args, root, python=None):
        if module_args[0] != "tools.derive_interpretations":
            return base(module_args, root, python)
        command = module_args[1]
        data_root = root / "data"
        staging = data_root / "staging"
        if command == "build":
            if interpretation_behavior == "fail":
                return FakeProcess(1, "", "boom: interpretation build failed")
            artifact = empty_interpretations_artifact()
            if interpretation_behavior == "lying-digest":
                (staging).mkdir(parents=True, exist_ok=True)
                (staging / "interpretations-index.json").write_text(json.dumps(artifact), encoding="utf-8")
                return FakeProcess(0, json.dumps({"counts": artifact["counts"], "digest": "0" * 64}))
            (staging).mkdir(parents=True, exist_ok=True)
            (staging / "interpretations-index.json").write_text(json.dumps(artifact), encoding="utf-8")
            return FakeProcess(0, json.dumps({"counts": artifact["counts"], "digest": artifact["digest"]}))
        if command == "publish":
            artifact = json.loads((staging / "interpretations-index.json").read_text(encoding="utf-8"))
            (data_root / "interpretations-index.json").write_text(json.dumps(artifact), encoding="utf-8")
            return FakeProcess(0, json.dumps({"counts": artifact["counts"], "digest": artifact["digest"]}))
        if command == "validate":
            artifact = json.loads((data_root / "interpretations-index.json").read_text(encoding="utf-8"))
            return FakeProcess(0, json.dumps({"counts": artifact["counts"], "digest": artifact["digest"]}))
        raise AssertionError(f"unexpected interpretation step invoked: {module_args}")
    return fake_run_cli


def test_run_pipeline_enabled_interpretation_runs_and_publishes(tmp_path, monkeypatch):
    index, details = build_two_list_index()
    monkeypatch.setattr(run_pipeline, "run_cli",
                         build_fake_run_cli_with_interpretation(index, details, {}))

    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path, enable_cli_interpretation=True)

    assert log["status"] == "success"
    assert [s["name"] for s in log["steps"]][-3:] == [
        "interpretation-build", "interpretation-publish", "interpretation-validate"]
    assert all(s.get("status") == "ok" for s in log["steps"])
    assert (tmp_path / "data" / "interpretations-index.json").exists()


def test_run_pipeline_interpretation_failure_never_touches_already_published_core_catalogue(tmp_path, monkeypatch):
    """H2 is additive: if it fails after being explicitly enabled, the run is honestly reported as
    failed, but the lists/projects catalogue that already published earlier in this same run is
    left untouched -- issue #53's "never required for the wrapper to run" / no-rollback discipline."""
    index, details = build_two_list_index()
    monkeypatch.setattr(run_pipeline, "run_cli",
                         build_fake_run_cli_with_interpretation(index, details, {}, interpretation_behavior="fail"))

    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path, enable_cli_interpretation=True)

    assert log["status"] == "failed"
    assert (tmp_path / "data" / "list-index.json").exists()
    assert (tmp_path / "data" / "project-index.json").exists()
    assert not (tmp_path / "data" / "interpretations-index.json").exists()


def test_run_pipeline_interpretation_never_publishes_on_digest_mismatch(tmp_path, monkeypatch):
    index, details = build_two_list_index()
    monkeypatch.setattr(run_pipeline, "run_cli",
                         build_fake_run_cli_with_interpretation(index, details, {},
                                                                 interpretation_behavior="lying-digest"))

    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path, enable_cli_interpretation=True)

    assert log["status"] == "failed"
    assert "digest" in log["failure"].casefold()
    assert not (tmp_path / "data" / "interpretations-index.json").exists()


def test_run_pipeline_disabled_by_default_never_invokes_interpretation_tool(tmp_path, monkeypatch):
    index, details = build_two_list_index()
    base_fake = build_fake_run_cli(index, details, {})

    def fake_run_cli(module_args, root, python=None):
        assert module_args[0] != "tools.derive_interpretations", "must not run when disabled (default)"
        return base_fake(module_args, root, python)

    monkeypatch.setattr(run_pipeline, "run_cli", fake_run_cli)
    log = run_pipeline.run_pipeline("lists-test-epicg", root=tmp_path)  # enable_cli_interpretation defaults False

    assert log["status"] == "success"
    assert not (tmp_path / "data" / "interpretations-index.json").exists()
