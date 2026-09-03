"""Local-only, resumable discovery of Awesome lists. Never imported by hosted UI."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta, datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote

from awesome.catalogue import digest
from awesome.lists import MIN_STARS, MAX_README, parse_readme, profile, validate_index
from tools.crawl import atomic_json as _atomic_json

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ("awesome is:public fork:true", "topic:awesome is:public fork:true", "topic:awesome-list is:public fork:true")
FILENAMES = ("README.md", "readme.md", "Readme.md", "README.markdown", ".github/README.md")


def atomic_json(path, data):
    # Windows antivirus/indexers can briefly share-lock a destination. Bounded retry,
    # same candidate bytes, never delete the last-good destination to force a write.
    for attempt in range(3):
        try:
            return _atomic_json(path, data)
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.1 * (attempt + 1))


def now():
    return datetime.now(timezone.utc).isoformat()


def engine():
    parts = [Path(__file__).read_bytes(), (ROOT / "awesome/lists.py").read_bytes(),
             (ROOT / "awesome/catalogue.py").read_bytes(), (ROOT / "tools/crawl.py").read_bytes(),
             (ROOT / "requirements.txt").read_bytes(), version("markdown-it-py").encode()]
    return hashlib.sha256(b"\0".join(parts)).hexdigest()


class GitHub:
    def __init__(self, search_interval=2.1):
        self.last_search = 0.0
        self.search_interval = search_interval

    def request(self, endpoint: str, query: str | None = None):
        if endpoint.startswith("search/"):
            time.sleep(max(0, self.search_interval - (time.monotonic() - self.last_search)))
            self.last_search = time.monotonic()
        command = ["gh", "api", endpoint]
        if query is not None:
            command += ["--input", "-"]
        for attempt in range(3):
            result = subprocess.run(command, input=json.dumps({"query": query}) if query else None,
                                    capture_output=True, text=True, encoding="utf-8", timeout=60)
            if result.returncode == 0:
                return json.loads(result.stdout)
            # A partial GraphQL response is useful but never claimed complete.
            if query and result.stdout.strip().startswith("{"):
                data = json.loads(result.stdout)
                if "data" in data or "errors" in data:
                    return data
            error = result.stderr.casefold()
            if any(x in error for x in ("401", "403", "429", "rate limit")):
                raise RuntimeError("GitHub authorization/rate boundary; checkpoint retained, resume after reset")
            if attempt == 2:
                raise RuntimeError("GitHub request failed; checkpoint retained")
            time.sleep(2 ** attempt)

    def search(self, query, page):
        return self.request(f"search/repositories?q={quote(query)}&per_page=100&page={page}&sort=stars&order=desc")

    def graphql(self, query):
        return self.request("graphql", query)


def search_query(part):
    stars = f"{part['low']}..{part['high']}" if part["high"] is not None else f">={part['low']}"
    return f"{part['base']} stars:{stars} created:{part['start']}..{part['end']}"


def split_partition(part, max_stars):
    """Non-overlapping finite split. None means visible unresolved saturation."""
    first, last = date.fromisoformat(part["start"]), date.fromisoformat(part["end"])
    if first < last:
        middle = first + (last - first) // 2
        return [{**part, "end": middle.isoformat()}, {**part, "start": (middle + timedelta(days=1)).isoformat()}]
    upper = part["high"] if part["high"] is not None else max_stars
    if upper <= part["low"]:
        return None
    middle = (part["low"] + upper) // 2
    return [{**part, "high": middle}, {**part, "low": middle + 1, "high": upper}]


def repository(item, observed, query):
    if not isinstance(item["id"], int) or isinstance(item["id"], bool) or item["id"] < 0:
        raise ValueError("Repository ID must be numeric")
    return {"id": str(item["id"]), "node_id": item.get("node_id"), "name": item["full_name"],
            "url": item["html_url"], "description": item.get("description") or "",
            "public": not item.get("private", True), "stars": item["stargazers_count"],
            "forks": item.get("forks_count"), "is_fork": item.get("fork", False),
            "archived": item.get("archived", False), "github_topics": item.get("topics", []),
            "license": (item.get("license") or {}).get("spdx_id"),
            "created_at": item.get("created_at"), "repository_pushed_at": item.get("pushed_at"),
            "observed_at": observed, "queries": [query]}


def compact_page(response):
    keys = {"id", "node_id", "full_name", "html_url", "description", "private", "stargazers_count",
            "forks_count", "fork", "archived", "topics", "license", "created_at", "pushed_at"}
    return {"total_count": response["total_count"], "incomplete_results": response.get("incomplete_results", False),
            "items": [{k: v for k, v in item.items() if k in keys} for item in response["items"]], "observed_at": now()}


class Run:
    def __init__(self, run_id, root=ROOT, api=None):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id):
            raise ValueError("Invalid run ID")
        self.root, self.api = Path(root), api or GitHub()
        self.directory = self.root / ".agent-runs/list-crawl" / run_id
        self.path = self.directory / "checkpoint.json"
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            checksum = state.pop("checkpoint_digest", None)
            if checksum != digest(state) or state["engine"] != engine():
                raise ValueError("Checkpoint/engine changed; use a new reviewed run, never rewrite hashes")
            self.state = state
        else:
            self.state = {"run_id": run_id, "engine": engine(), "started_at": now(), "queries": list(QUERIES),
                          "threshold": MIN_STARS, "queue": [{"base": q, "start": "2008-01-01",
                          "end": date.today().isoformat(), "low": MIN_STARS, "high": None} for q in QUERIES],
                          "pages": {}, "partitions": [], "candidates": {}, "metadata": {}, "completed": {}, "errors": {}}
            self.save()

    def save(self):
        atomic_json(self.path, {**self.state, "checkpoint_digest": digest(self.state)})

    def discover(self, interrupt_after=None):
        processed = 0
        while self.state["queue"]:
            part = self.state["queue"][0]; query = search_query(part); key = digest(part)
            pages = self.state["pages"].setdefault(key, {})
            if "1" not in pages:
                pages["1"] = compact_page(self.api.search(query, 1)); self.save()
                processed += 1
                if interrupt_after and processed >= interrupt_after:
                    raise InterruptedError("Injected after durable search page; published index unchanged")
            first = pages["1"]; total = first["total_count"]
            for item in first["items"]:
                rid = str(item["id"])
                if rid not in self.state["candidates"]:
                    self.state["candidates"][rid] = repository(item, first["observed_at"], query)
                elif query not in self.state["candidates"][rid]["queries"]:
                    self.state["candidates"][rid]["queries"].append(query)
            if total > 1000 or first.get("incomplete_results"):
                children = split_partition(part, max([x["stargazers_count"] for x in first["items"]] or [MIN_STARS]))
                self.state["partitions"].append({"query": query, "total": total, "status": "split" if children else "unresolved",
                    "reason": "Result cap or incomplete API response", "observed_at": first["observed_at"]})
                self.state["queue"] = (children or []) + self.state["queue"][1:]; self.save(); continue
            for page in range(2, math.ceil(total / 100) + 1):
                if str(page) not in pages:
                    pages[str(page)] = compact_page(self.api.search(query, page)); self.save()
                    processed += 1
                    if interrupt_after and processed >= interrupt_after:
                        raise InterruptedError("Injected after durable search page; published index unchanged")
            unique, received, totals = set(), 0, set()
            incomplete = False
            for response in pages.values():
                incomplete |= bool(response.get("incomplete_results")); totals.add(response["total_count"])
                received += len(response["items"])
                for item in response["items"]:
                    rid = str(item["id"]); unique.add(rid)
                    if rid not in self.state["candidates"]:
                        self.state["candidates"][rid] = repository(item, response["observed_at"], query)
                    elif query not in self.state["candidates"][rid]["queries"]:
                        self.state["candidates"][rid]["queries"].append(query)
            reconciled = not incomplete and len(totals) == 1 and len(unique) == total
            self.state["partitions"].append({"query": query, "total": total, "received": received,
                "unique": len(unique), "pages": len(pages), "status": "reconciled" if reconciled else "unresolved",
                "observed_at": first["observed_at"], "completed_at": now()})
            self.state["queue"].pop(0); self.save()
            print(f"Discovery: {len(self.state['candidates'])} candidates; {len(self.state['queue'])} partitions queued", flush=True)
        self.state.setdefault("discovery_completed_at", now()); self.save()

    def metadata(self, candidates):
        fields = []
        for i, meta in enumerate(candidates):
            owner, name = meta["name"].split("/")
            fields.append(f'r{i}:repository(owner:{json.dumps(owner)},name:{json.dumps(name)})' +
                '{ id nameWithOwner url description stargazerCount forkCount isPrivate isArchived isFork parent { nameWithOwner url } licenseInfo { spdxId } defaultBranchRef { name target { oid } } }')
        response = self.api.graphql("query { " + " ".join(fields) + " }")
        bad = {str(e.get("path", [None])[0]) for e in response.get("errors", [])}
        data = response.get("data") or {}
        for i, meta in enumerate(candidates):
            alias = f"r{i}"; value = data.get(alias)
            if not value or alias in bad or "None" in bad or not value.get("defaultBranchRef"):
                self.state["errors"][meta["id"]] = "Repository metadata unavailable or partial GraphQL response"; continue
            if value["id"] != meta.get("node_id"):
                self.state["errors"][meta["id"]] = "Repository identity changed; pending stable-ID reconciliation"; continue
            if value["isPrivate"]:
                # Retain only previously public discovery metadata, never new private fields.
                item, _ = profile({**meta, "public": False}, None)
                self.state["completed"][meta["id"]] = item
                self.state["errors"].pop(meta["id"], None)
                continue
            branch = value["defaultBranchRef"]
            self.state["metadata"][meta["id"]] = {**meta, "node_id": value["id"], "name": value["nameWithOwner"],
                "url": value["url"], "description": value.get("description") or "", "stars": value["stargazerCount"],
                "forks": value["forkCount"], "public": not value["isPrivate"], "archived": value["isArchived"],
                "is_fork": value["isFork"], "parent": value.get("parent"),
                "license": (value.get("licenseInfo") or {}).get("spdxId"),
                "revision": branch["target"]["oid"], "default_branch": branch["name"], "observed_at": now()}
        self.save()

    def content(self, candidates):
        fields = []
        for i, meta in enumerate(candidates):
            owner, name = meta["name"].split("/"); rev = meta["revision"]
            objects = " ".join(f'f{j}:object(expression:{json.dumps(rev+":"+path)}) {{ ... on Blob {{ byteSize isBinary text }} }}' for j, path in enumerate(FILENAMES))
            fields.append(f'r{i}:repository(owner:{json.dumps(owner)},name:{json.dumps(name)}) {{ id isPrivate {objects} }}')
        response = self.api.graphql("query { " + " ".join(fields) + " }")
        bad = {str(e.get("path", [None])[0]) for e in response.get("errors", [])}
        data = response.get("data") or {}
        for i, meta in enumerate(candidates):
            value = data.get(f"r{i}")
            if value is None or f"r{i}" in bad or "None" in bad:
                self.state["errors"][meta["id"]] = "README request partial/unavailable"; continue
            if value.get("id") != meta.get("node_id"):
                self.state["errors"][meta["id"]] = "README repository identity changed; nothing persisted"; continue
            if value.get("isPrivate") is not False or meta.get("public") is not True:
                item, _ = profile({**self.state["candidates"][meta["id"]], "public": False}, None)
                self.state["completed"][meta["id"]] = item
                self.state["errors"].pop(meta["id"], None)
                continue
            found = next(((FILENAMES[j], value[f"f{j}"]) for j in range(len(FILENAMES)) if value.get(f"f{j}")), None)
            if not found:
                item, detail = profile(meta, None)
                item["reason"] = "No supported Markdown README filename; other formats or files may hold the list."
            else:
                path, blob = found
                if blob.get("isBinary") or blob.get("text") is None or blob["byteSize"] > MAX_README:
                    item, detail = profile(meta, None); item["reason"] = "Binary, truncated or oversized README; not counted as empty."
                else:
                    text = blob["text"]; raw = text.encode("utf-8")
                    if len(raw) != blob["byteSize"]:
                        self.state["errors"][meta["id"]] = "README byte size mismatch"; continue
                    pinned = {**meta, "readme_path": path, "readme_sha256": hashlib.sha256(raw).hexdigest(),
                              "content_updated_at": None, "content_update_status": "Pinned content fetched; path history pending"}
                    parsed = parse_readme(text, meta["name"], meta["revision"], path)
                    item, detail = profile(pinned, parsed, text)
                    raw_path = self.root / "data/raw/lists" / meta["id"] / meta["revision"] / "README.md"
                    raw_path.parent.mkdir(parents=True, exist_ok=True); raw_path.write_bytes(raw)
            if detail:
                atomic_json(self.root / "data/staging" / item["detail"], detail)
            self.state["completed"][meta["id"]] = item
            self.state["errors"].pop(meta["id"], None)
        self.save()

    def enrich(self, interrupt_after=None, batch_size=8):
        todo = sorted((m for rid, m in self.state["candidates"].items() if rid not in self.state["completed"]),
                      key=lambda m: (-m["stars"], m["id"]))
        batches = 0
        for offset in range(0, len(todo), batch_size):
            batch = todo[offset:offset + batch_size]
            missing = [m for m in batch if m["id"] not in self.state["metadata"]]
            if missing:
                self.metadata(missing)
            available = [self.state["metadata"][m["id"]] for m in batch if m["id"] in self.state["metadata"]
                         and self.state["metadata"][m["id"]].get("public") is True and m["id"] not in self.state["completed"]]
            if available:
                self.content(available)
            batches += 1
            print(f"Enrichment: {len(self.state['completed'])}/{len(self.state['candidates'])}; {len(self.state['errors'])} pending errors", flush=True)
            if interrupt_after and batches >= interrupt_after:
                raise InterruptedError("Injected after durable enrichment batch; published index unchanged")

    def stage(self):
        items = []
        for rid, meta in self.state["candidates"].items():
            if rid in self.state["completed"]:
                items.append(self.state["completed"][rid])
            else:
                item, _ = profile(meta, None)
                item["reason"] = self.state["errors"].get(rid, item["reason"]); items.append(item)
        items.sort(key=lambda m: (-m["stars"], m["name"].casefold()))
        index = {"format_version": 2, "min_stars": MIN_STARS, "run_id": self.state["run_id"],
            "started_at": self.state["started_at"], "generated_at": self.state.get("discovery_completed_at", self.state["started_at"]),
            "engine_digest": self.state["engine"], "queries": self.state["queries"],
            "coverage": {"scope": "Public keyword/topic repository searches, forks included. Non-transactional GitHub observations, not a GitHub-wide census.",
                         "queued_partitions": len(self.state["queue"]), "partitions": self.state["partitions"],
                         "enrichment_pending": len(self.state["candidates"]) - len(self.state["completed"])},
            "counts": dict(Counter(m["state"] for m in items)), "lists": items}
        index["digest"] = digest(index); validate_index(index, self.root / "data/staging")
        atomic_json(self.root / "data/staging/list-index.json", index)
        return index


def publish(expected, root=ROOT, interrupt_after=None):
    root = Path(root); staging = root / "data/staging"
    index = json.loads((staging / "list-index.json").read_text(encoding="utf-8"))
    validate_index(index, staging)
    if index["digest"] != expected:
        raise ValueError("Stale publication candidate")
    for i, item in enumerate(index["lists"]):
        if item.get("detail"):
            target = root / "data" / item["detail"]
            source = staging / item["detail"]
            if target.exists():
                if target.read_bytes() != source.read_bytes():
                    raise ValueError("Immutable detail collision")
            else:
                atomic_json(target, json.loads(source.read_text(encoding="utf-8")))
        if interrupt_after and i + 1 >= interrupt_after:
            raise InterruptedError("Injected before index pointer swap; last-good index intact")
    validate_index(index, root / "data")
    atomic_json(root / "data/list-index.json", index)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["discover", "enrich", "stage", "publish", "validate"])
    parser.add_argument("--run-id", default="lists-20260903")
    parser.add_argument("--expected-digest")
    parser.add_argument("--interrupt-after", type=int)
    args = parser.parse_args()
    lock = ROOT / ".agent-runs/list-crawler.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive writer with explicit identity; no age-based stale-lock deletion.
    handle = lock.open("x", encoding="utf-8")
    try:
        with handle:
            json.dump({"pid": os.getpid(), "started_at": now(), "run_id": args.run_id}, handle)
            handle.flush(); os.fsync(handle.fileno())
        if args.command == "publish":
            if not args.expected_digest:
                parser.error("--expected-digest required after reviewing staged content")
            result = publish(args.expected_digest, interrupt_after=args.interrupt_after)
        elif args.command == "validate":
            result = json.loads((ROOT / "data/list-index.json").read_text(encoding="utf-8")); validate_index(result, ROOT / "data")
        else:
            run = Run(args.run_id)
            if args.command == "discover":
                run.discover(args.interrupt_after)
            elif args.command == "enrich":
                run.enrich(args.interrupt_after)
            result = run.stage()
        print(json.dumps({"counts": result["counts"], "digest": result["digest"]}), flush=True)
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
