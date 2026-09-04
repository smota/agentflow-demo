"""Batch community-intake resolution.

Reads open GitHub Issues created from the "Propose a list" / "Flag an item" issue-form templates
(`.github/ISSUE_TEMPLATE/propose-a-list.yml`, `.github/ISSUE_TEMPLATE/flag-an-item.yml`) and runs
each one through the *existing* deterministic pipeline:

- Propose-list submissions are fed through `tools.lists.Run.metadata()` / `Run.content()` — the
  same two calls `Run.enrich()` makes per batch, driving the same `awesome.lists.profile()` /
  `classify()` classifier every crawled candidate goes through. No parallel classification rules
  are implemented here.
- Flag-item submissions use a narrower, explicitly-scoped deterministic rule set against the
  already-published `data/list-index.json`: exact-URL duplicate/fork checks, an HTTP reachability
  check for dead links, and a recompute of `awesome.lists.topics()` for miscategorization.

Every outcome is one of `staged` (eligible; queued into the intake run's staging index for the next
`tools.lists publish`), `resolved` (closed, with the classifier's own reason), or `queued` (left
open with `intake:queued` for a maintainer — genuinely ambiguous, never guessed).

This is a single, on-demand batch step (`python -m tools.lists intake`). It starts, runs once, and
exits — no server, no polling loop, matching the "no heartbeat" principle in `docs/demo/goal.md`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from tools.lists import GitHub, ROOT, Run, now, repository
from awesome.lists import topics as compute_topics

PROPOSE_LABEL = "intake:propose-list"
FLAG_LABEL = "intake:flag-item"
STAGED_LABEL = "intake:staged"
QUEUED_LABEL = "intake:queued"
RESOLVED_LABEL = "intake:resolved"
OUTCOME_LABELS = (STAGED_LABEL, QUEUED_LABEL, RESOLVED_LABEL)

REPO_URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+?)/?$")
FLAG_TYPES = {"Duplicate", "Dead link", "Miscategorized"}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_form_body(body: str) -> dict:
    """Parse a GitHub issue-form rendered body into {field-key: value}.

    GitHub renders each `body[].attributes.label` as a level-3 heading followed by the submitted
    value (or the literal "_No response_" for a blank optional field). Field keys are derived from
    the heading text the same way for every template, so this parser has no per-template
    special-casing: "List URL" -> "list-url", "Flag type" -> "flag-type", etc.
    """
    fields = {}
    for match in re.finditer(r"^### (.+?)\s*\n+(.*?)(?=\n### |\Z)", body or "", re.M | re.S):
        label, value = match.group(1).strip(), match.group(2).strip()
        key = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
        fields[key] = "" if value == "_No response_" else value
    return fields


def repo_url_parts(url: str) -> tuple[str, str] | None:
    match = REPO_URL_RE.match((url or "").strip())
    return (match.group(1), match.group(2)) if match else None


def already_processed(issue: dict) -> bool:
    """True when a prior intake run already labeled this issue's outcome."""
    names = {label.get("name") for label in issue.get("labels", [])}
    return bool(names & set(OUTCOME_LABELS))


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    outcome: str  # "staged" | "resolved" | "queued"
    reason: str
    label: str
    close: bool
    close_reason: str | None = None  # "completed" | "not planned"


# ---------------------------------------------------------------------------
# Propose-list resolution — reuses the real crawler/classifier pipeline
# ---------------------------------------------------------------------------

def resolve_propose(issue: dict, api: GitHub, run: Run) -> Decision:
    fields = parse_form_body(issue.get("body") or "")
    list_url = fields.get("list-url", "").strip()
    parts = repo_url_parts(list_url)
    if not parts:
        return Decision("resolved",
            f"List URL {list_url!r} is not a github.com repository URL "
            "(expected https://github.com/owner/repo).", RESOLVED_LABEL, True, "not planned")
    owner, name = parts

    try:
        data = api.request(f"repos/{owner}/{name}")
    except RuntimeError as error:
        message = str(error)
        if "authorization" in message.casefold() or "rate" in message.casefold():
            return Decision("queued",
                f"GitHub API temporarily unavailable ({message}); will retry on the next intake run.",
                QUEUED_LABEL, False)
        return Decision("resolved", f"Repository {owner}/{name} was not found or is not accessible.",
                         RESOLVED_LABEL, True, "not planned")
    if not isinstance(data, dict) or not isinstance(data.get("id"), int):
        return Decision("resolved", f"Repository {owner}/{name} was not found or is not accessible.",
                         RESOLVED_LABEL, True, "not planned")

    # Seed the candidate through the same shape `discover()` produces, then reuse the exact two
    # calls `Run.enrich()` makes per batch — never a parallel classifier.
    meta = repository(data, now(), query=f"community-intake:issue-{issue['number']}")
    run.state["candidates"][meta["id"]] = meta
    run.metadata([meta])
    fetched = run.state["metadata"].get(meta["id"])
    if fetched is None:
        if meta["id"] in run.state["completed"]:
            item = run.state["completed"][meta["id"]]
        else:
            return Decision("queued", run.state["errors"].get(meta["id"], "Repository metadata unavailable."),
                             QUEUED_LABEL, False)
    else:
        run.content([fetched])
        item = run.state["completed"].get(meta["id"])
        if item is None:
            return Decision("queued", run.state["errors"].get(meta["id"], "README content unavailable."),
                             QUEUED_LABEL, False)

    state, reason = item["state"], item["reason"]
    if state == "eligible":
        run.stage()
        return Decision("staged", reason, STAGED_LABEL, True, "completed")
    if state == "excluded":
        return Decision("resolved", reason, RESOLVED_LABEL, True, "not planned")
    return Decision("queued", reason, QUEUED_LABEL, False)


# ---------------------------------------------------------------------------
# Flag-item resolution — narrower, explicitly-scoped deterministic rules
# ---------------------------------------------------------------------------

def _find_published(index: dict | None, url: str) -> dict | None:
    if not index:
        return None
    normalized = (url or "").rstrip("/")
    for item in index.get("lists", []):
        if item.get("url", "").rstrip("/") == normalized:
            return item
    return None


def _resolve_dead_link(url: str, timeout: float = 8.0, opener=None) -> Decision:
    opener = opener or urllib.request.urlopen
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": "agentflow-intake"})
        try:
            with opener(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as error:
            status = error.code
        except (urllib.error.URLError, TimeoutError, ValueError):
            return Decision("queued",
                "Link reachability could not be confirmed automatically (timeout/network error); "
                "needs a manual check.", QUEUED_LABEL, False)
        if status == 405 and method == "HEAD":
            continue  # some servers reject HEAD; retry with GET before giving up
        break
    if status in (404, 410):
        return Decision("resolved", f"Link returned HTTP {status}; confirmed dead.", RESOLVED_LABEL, True, "completed")
    if 200 <= status < 400:
        return Decision("resolved", f"Link returned HTTP {status}; not reproducible.", RESOLVED_LABEL, True, "not planned")
    return Decision("queued", f"Link returned HTTP {status}; ambiguous, needs a manual check.", QUEUED_LABEL, False)


def _resolve_miscategorized(published: dict | None, url: str) -> Decision:
    if not published:
        return Decision("queued", f"{url} was not found in the published catalogue; needs maintainer confirmation.",
                         QUEUED_LABEL, False)
    recomputed = sorted(compute_topics(published))
    current = sorted(published.get("topics") or [])
    if recomputed == current:
        return Decision("resolved",
            f"Recomputed category ({', '.join(current) or 'none'}) matches the published category; not a bug.",
            RESOLVED_LABEL, True, "not planned")
    return Decision("resolved",
        f"Recomputed category ({', '.join(recomputed) or 'none'}) differs from the published category "
        f"({', '.join(current) or 'none'}); will refresh on the next discover/enrich cycle.",
        RESOLVED_LABEL, True, "completed")


def _resolve_duplicate(url: str, api: GitHub, index: dict | None) -> Decision:
    parts = repo_url_parts(url)
    if not parts:
        return Decision("resolved", "Entry URL is not a github.com repository URL.", RESOLVED_LABEL, True, "not planned")
    owner, name = parts
    try:
        data = api.request(f"repos/{owner}/{name}")
    except RuntimeError as error:
        return Decision("queued",
            f"Could not re-check {owner}/{name} against GitHub right now ({error}); needs a manual check.",
            QUEUED_LABEL, False)
    parent = (data or {}).get("parent") or {}
    if not (data or {}).get("fork") or not parent.get("full_name"):
        return Decision("queued",
            f"{owner}/{name} is not a fork with a public parent repository; cannot confirm duplication automatically.",
            QUEUED_LABEL, False)
    parent_url = f"https://github.com/{parent['full_name']}"
    parent_entry = _find_published(index, parent_url)
    if parent_entry and parent_entry.get("state") == "eligible":
        return Decision("resolved",
            f"{owner}/{name} is a fork of {parent['full_name']}, which is already published; confirmed duplicate.",
            RESOLVED_LABEL, True, "completed")
    return Decision("queued",
        f"{owner}/{name} is a fork of {parent['full_name']}, but that repository is not currently published; "
        "needs maintainer confirmation.", QUEUED_LABEL, False)


def resolve_flag(issue: dict, api: GitHub, index: dict | None) -> Decision:
    fields = parse_form_body(issue.get("body") or "")
    flag_type = fields.get("flag-type", "").strip()
    entry_url = fields.get("entry-url", "").strip()
    if flag_type not in FLAG_TYPES:
        return Decision("queued", f"Unrecognized flag type {flag_type!r}; needs maintainer triage.", QUEUED_LABEL, False)
    if not entry_url:
        return Decision("resolved", "No entry URL was provided.", RESOLVED_LABEL, True, "not planned")

    if flag_type == "Dead link":
        return _resolve_dead_link(entry_url)
    if flag_type == "Miscategorized":
        return _resolve_miscategorized(_find_published(index, entry_url), entry_url)
    return _resolve_duplicate(entry_url, api, index)


# ---------------------------------------------------------------------------
# GitHub issue I/O — isolated so tests substitute a fixture, never `gh` itself
# ---------------------------------------------------------------------------

class IssueSource:
    """Reads/writes GitHub Issues through `gh`. The only class in this module that shells out."""

    def list_open(self, label: str) -> list[dict]:
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--label", label,
             "--json", "number,title,body,labels", "--limit", "200"],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"gh issue list failed: {result.stderr.strip()}")
        return json.loads(result.stdout)

    def comment(self, number: int, body: str) -> None:
        subprocess.run(["gh", "issue", "comment", str(number), "--body", body],
                        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)

    def add_label(self, number: int, label: str) -> None:
        subprocess.run(["gh", "issue", "edit", str(number), "--add-label", label],
                        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)

    def close(self, number: int, reason: str) -> None:
        subprocess.run(["gh", "issue", "close", str(number), "--reason", reason],
                        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)


class FixtureIssueSource(IssueSource):
    """In-memory issue source for tests. Never calls `gh`; records every action it would take."""

    def __init__(self, issues: dict[str, list[dict]]):
        self.issues = issues  # {label: [issue, ...]}
        self.actions: list[tuple] = []

    def list_open(self, label: str) -> list[dict]:
        return list(self.issues.get(label, []))

    def comment(self, number: int, body: str) -> None:
        self.actions.append(("comment", number, body))

    def add_label(self, number: int, label: str) -> None:
        self.actions.append(("add_label", number, label))

    def close(self, number: int, reason: str) -> None:
        self.actions.append(("close", number, reason))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _apply(source: IssueSource, issue: dict, decision: Decision, dry_run: bool) -> dict:
    number = issue["number"]
    comment = f"**Automated intake result: {decision.outcome}**\n\n{decision.reason}"
    if not dry_run:
        source.comment(number, comment)
        source.add_label(number, decision.label)
        if decision.close:
            source.close(number, decision.close_reason or "completed")
    return {"issue": number, "outcome": decision.outcome, "reason": decision.reason,
            "label": decision.label, "closed": bool(decision.close), "dry_run": dry_run}


def run_intake(source: IssueSource, api: GitHub, run: Run, index: dict | None, *,
               dry_run: bool = False, propose_label: str = PROPOSE_LABEL,
               flag_label: str = FLAG_LABEL) -> list[dict]:
    results = []
    for issue in source.list_open(propose_label):
        if already_processed(issue):
            continue
        decision = resolve_propose(issue, api, run)
        results.append(_apply(source, issue, decision, dry_run))
    for issue in source.list_open(flag_label):
        if already_processed(issue):
            continue
        decision = resolve_flag(issue, api, index)
        results.append(_apply(source, issue, decision, dry_run))
    return results


def load_published_index(root=ROOT) -> dict | None:
    path = root / "data/list-index.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=f"intake-{date.today().isoformat()}")
    parser.add_argument("--dry-run", action="store_true",
                         help="Report intended actions without commenting/labeling/closing anything.")
    parser.add_argument("--label-propose", default=PROPOSE_LABEL)
    parser.add_argument("--label-flag", default=FLAG_LABEL)
    args = parser.parse_args(argv)

    source = IssueSource()
    api = GitHub()
    run = Run(args.run_id)
    index = load_published_index()
    results = run_intake(source, api, run, index, dry_run=args.dry_run,
                          propose_label=args.label_propose, flag_label=args.label_flag)
    summary = {"processed": len(results),
               "staged": sum(r["outcome"] == "staged" for r in results),
               "resolved": sum(r["outcome"] == "resolved" for r in results),
               "queued": sum(r["outcome"] == "queued" for r in results),
               "dry_run": args.dry_run, "results": results}
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    main()
