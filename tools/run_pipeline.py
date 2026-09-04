"""Unattended orchestration of the full local catalogue pipeline.

Runs `discover -> enrich -> profiles -> stage -> publish` (`tools.lists`) followed by the project
dedup derivation (`tools.derive_projects stage -> publish`), then a final `validate` of each
published artifact -- the complete sequence a maintainer would otherwise type by hand from
`docs/demo/list-data.md`. Invoked unattended by `tools/run_pipeline.ps1` under Windows Task
Scheduler (see `docs/adr/008-local-pipeline-scheduling.md`, Epic G / issue #52); also runnable
directly for a manual or scoped test run.

Design constraints (issue #52's Requirements/Acceptance criteria):

- Reuse existing checkpointing/locking unchanged. Every stage is invoked exactly as documented --
  a subprocess call to `python -m tools.lists <command>` / `python -m tools.derive_projects
  <command>` -- so `.agent-runs/list-crawler.lock`'s single-writer guarantee and each command's own
  checkpoint/atomic-publish behaviour are reused verbatim; this module never reimplements or
  bypasses them by importing pipeline internals directly.
- No manual confirmation step. `--expected-digest` is never typed by a human: this module captures
  the digest each `stage` command prints for *this run's own* staged output, then independently
  re-reads the staged file(s) from disk, recomputes the digest with the same
  `awesome.catalogue.digest` function `validate_index`/`validate_projects` use, and re-runs that
  full validator (which itself re-checks every referenced shard from bytes on disk) before ever
  calling `publish`. A run only auto-approves publish when the recomputed digest matches the printed
  one AND full validation passes -- never on the printed digest alone. See `verify_list_stage` /
  `verify_project_stage`.
- No partial publish. The first failing/mismatched step aborts every remaining step and the run
  exits non-zero; `publish` is only ever invoked once its own stage's independent verification has
  already passed, so the previous published snapshot is left byte-for-byte untouched on any failure
  -- there is no rollback step because there is nothing to roll back.
- Structured, morning-readable run log. Every invocation writes a JSON log (`run-log.json`) and a
  companion Markdown summary (`run-log.md`) under a per-run directory in the git-ignored
  `.agent-runs/pipeline-runs/`, recording start/end timestamps and, per step, its status
  (`ok`/`failed`/`skipped`), counts, digest and a tail of stdout/stderr for a failed step.
- No new server process. This module runs once per invocation and exits; it is a scheduled batch
  job, never a resident listener (`docs/demo/goal.md`'s "no heartbeat" principle).

`tools.prune_list_shards` (obsolete-shard cleanup) is intentionally NOT part of this unattended
sequence: it is a destructive maintenance command whose own docs require reviewing a dry run before
`--apply`, which is exactly the kind of human-in-the-loop step this epic explicitly does not extend
to. It stays a separate, manually-run tool.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from awesome.catalogue import digest
from awesome.lists import validate_index
from awesome.projects import shard_path as project_shard_path
from awesome.projects import validate_projects
from tools.lists import atomic_json, now

ROOT = Path(__file__).resolve().parents[1]


class StepFailed(RuntimeError):
    """Raised for any step that fails, is unreachable, or fails independent verification."""


def run_cli(module_args: list[str], root: Path, python: str | None = None) -> subprocess.CompletedProcess:
    """Invoke `python -m tools....` exactly as a human would type it per docs/demo/list-data.md."""
    executable = python or sys.executable
    return subprocess.run([executable, "-m", *module_args], cwd=root,
                           capture_output=True, text=True, encoding="utf-8")


def parse_result_line(stdout: str | None) -> dict | None:
    """Every pipeline CLI prints exactly one trailing JSON object; tolerate log noise around it."""
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def verify_list_stage(expected_digest: str, data_root: Path) -> dict:
    """Independently re-verify a staged list-index candidate before it may be published.

    Re-reads `data/staging/list-index.json` from disk (never trusts the digest `stage` printed on
    its own), recomputes its digest the same way `validate_index` does, and runs `validate_index`
    with `data_root` set so every `eligible` item's detail shard is also re-validated from bytes on
    disk. Raises `StepFailed` on any mismatch or validation error.
    """
    staging = data_root / "staging"
    path = staging / "list-index.json"
    if not path.exists():
        raise StepFailed("Staged list index missing before publish verification")
    index = json.loads(path.read_text(encoding="utf-8"))
    recomputed = digest({k: v for k, v in index.items() if k != "digest"})
    if recomputed != index.get("digest") or recomputed != expected_digest:
        raise StepFailed("Independent digest recomputation did not match the staged list index")
    try:
        validate_index(index, staging)
    except ValueError as exc:
        raise StepFailed(f"Staged list index failed independent validation: {exc}") from exc
    return index


def verify_project_stage(expected_digest: str, data_root: Path) -> dict:
    """Independently re-verify a staged project-index candidate before it may be published.

    Mirrors `verify_list_stage`: re-reads the staged project index and every shard it references
    from disk, recomputes the digest, and runs the full `validate_projects` (index + shards) against
    the already-published list index those projects were derived from.
    """
    staging = data_root / "staging"
    path = staging / "project-index.json"
    if not path.exists():
        raise StepFailed("Staged project index missing before publish verification")
    data = json.loads(path.read_text(encoding="utf-8"))
    recomputed = digest({k: v for k, v in data.items() if k != "digest"})
    if recomputed != data.get("digest") or recomputed != expected_digest:
        raise StepFailed("Independent digest recomputation did not match the staged project index")
    list_index_path = data_root / "list-index.json"
    if not list_index_path.exists():
        raise StepFailed("Published list index missing before project publish verification")
    index = json.loads(list_index_path.read_text(encoding="utf-8"))
    try:
        shards = {prefix: json.loads((staging / project_shard_path(prefix)).read_text(encoding="utf-8"))
                  for prefix in data.get("shards", {})}
        validate_projects(data, index, shards)
    except (ValueError, OSError) as exc:
        raise StepFailed(f"Staged project index failed independent validation: {exc}") from exc
    return data


def run_step(log: dict, name: str, module_args: list[str], root: Path, python: str | None = None) -> dict | None:
    """Run one CLI step, record it in `log["steps"]`, and return its parsed JSON result.

    Raises `StepFailed` on a non-zero exit or an unlaunchable process; the caller aborts the
    remaining sequence on that exception, which is what guarantees no partial publish.
    """
    step = {"name": name, "command": ["python", "-m", *module_args], "started_at": now()}
    log["steps"].append(step)
    try:
        result = run_cli(module_args, root, python)
    except OSError as exc:
        step.update(status="failed", finished_at=now(), error=str(exc))
        raise StepFailed(f"{name}: could not launch subprocess ({exc})") from exc
    step["finished_at"] = now()
    tail = lambda text: "\n".join((text or "").splitlines()[-20:])
    if result.returncode != 0:
        step.update(status="failed", returncode=result.returncode,
                     stdout_tail=tail(result.stdout), stderr_tail=tail(result.stderr))
        raise StepFailed(f"{name} exited {result.returncode}")
    payload = parse_result_line(result.stdout)
    step.update(status="ok", returncode=0, counts=(payload or {}).get("counts"),
                digest=(payload or {}).get("digest"), stdout_tail=tail(result.stdout))
    return payload


def skip_step(log: dict, name: str, reason: str) -> None:
    log["steps"].append({"name": name, "status": "skipped", "reason": reason})


def render_summary(log: dict) -> str:
    lines = [f"# Pipeline run `{log['run_id']}`", "", f"- Status: **{log['status']}**",
              f"- Started: {log['started_at']}", f"- Finished: {log.get('finished_at', 'n/a')}"]
    if log.get("failure"):
        lines.append(f"- Failure: {log['failure']}")
    lines += ["", "| Step | Status | Counts | Digest |", "| --- | --- | --- | --- |"]
    for step in log["steps"]:
        counts = json.dumps(step.get("counts")) if step.get("counts") else "-"
        step_digest = (step.get("digest") or "-")[:12]
        lines.append(f"| {step['name']} | {step.get('status', 'unknown')} | {counts} | {step_digest} |")
    for step in log["steps"]:
        if step.get("status") == "failed":
            lines += ["", f"## {step['name']} failure detail", "```",
                       step.get("error") or step.get("stderr_tail") or "(no captured output)", "```"]
    return "\n".join(lines) + "\n"


def write_log(log: dict, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = log["started_at"].replace(":", "").replace("+00:00", "Z")
    base = log_dir / f"{log['run_id']}-{stamp}"
    atomic_json(base.with_suffix(".json"), log)
    base.with_suffix(".md").write_text(render_summary(log), encoding="utf-8")
    return base.with_suffix(".json")


def run_pipeline(run_id: str, root: Path = ROOT, batch_size: int = 32, workers: int = 4,
                  log_dir: Path | None = None, skip: tuple[str, ...] = (),
                  python: str | None = None) -> dict:
    """Run the full unattended sequence once and return the structured log dict.

    `skip` (any of "discover", "enrich", "profiles") lets a test or a maintainer's manual re-run
    start from an existing checkpoint's later stage; it never skips stage/publish/validate, which
    always run so a candidate is always independently re-verified before publication.
    """
    data_root = root / "data"
    log = {"run_id": run_id, "started_at": now(), "steps": [], "status": "running"}
    try:
        for name, args in (
            ("discover", ["tools.lists", "discover", "--run-id", run_id]),
            ("enrich", ["tools.lists", "enrich", "--run-id", run_id, "--batch-size", str(batch_size)]),
            ("profiles", ["tools.lists", "profiles", "--run-id", run_id,
                          "--batch-size", str(min(batch_size, 16)), "--workers", str(workers)]),
        ):
            if name in skip:
                skip_step(log, name, "requested via --skip")
            else:
                run_step(log, name, args, root, python)

        staged_lists = run_step(log, "lists-stage", ["tools.lists", "stage", "--run-id", run_id], root, python)
        if not staged_lists or not staged_lists.get("digest"):
            raise StepFailed("lists-stage did not report a digest to verify")
        verify_list_stage(staged_lists["digest"], data_root)
        run_step(log, "lists-publish",
                 ["tools.lists", "publish", "--expected-digest", staged_lists["digest"]], root, python)
        run_step(log, "lists-validate", ["tools.lists", "validate"], root, python)

        staged_projects = run_step(log, "projects-stage", ["tools.derive_projects", "stage"], root, python)
        if not staged_projects or not staged_projects.get("digest"):
            raise StepFailed("projects-stage did not report a digest to verify")
        verify_project_stage(staged_projects["digest"], data_root)
        run_step(log, "projects-publish",
                 ["tools.derive_projects", "publish", "--expected-digest", staged_projects["digest"]], root, python)
        run_step(log, "projects-validate", ["tools.derive_projects", "validate"], root, python)

        log["status"] = "success"
    except StepFailed as exc:
        log["status"] = "failed"
        log["failure"] = str(exc)
    log["finished_at"] = now()
    write_log(log, log_dir or (root / ".agent-runs/pipeline-runs"))
    return log


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None,
                         help="defaults to lists-<UTC date> to match tools.lists' own convention")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--log-dir")
    parser.add_argument("--skip", action="append", default=[],
                         choices=["discover", "enrich", "profiles"],
                         help="Skip early crawl stages; testing/manual re-run only, never stage/publish/validate")
    parser.add_argument("--python", help="Python executable used for each subprocess step; defaults to this interpreter")
    args = parser.parse_args()
    run_id = args.run_id or f"lists-{now()[:10].replace('-', '')}"
    log = run_pipeline(run_id, batch_size=args.batch_size, workers=args.workers,
                        log_dir=Path(args.log_dir) if args.log_dir else None,
                        skip=tuple(args.skip), python=args.python)
    print(json.dumps({"run_id": log["run_id"], "status": log["status"],
                       "steps": [{"name": s["name"], "status": s.get("status")} for s in log["steps"]]}))
    sys.exit(0 if log["status"] == "success" else 1)


if __name__ == "__main__":
    main()
