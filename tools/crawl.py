"""Run locally: python -m tools.crawl build, then review and publish by digest."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt
from awesome.catalogue import digest, qualifies, safe_url, validate_catalogue

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data/staging/catalogue.json"
PUBLISHED = ROOT / "data/catalogue.json"
MAX_README = 2 * 1024 * 1024
QUERIES = ["awesome in:name,description stars:>=50000 is:public",
           "topic:awesome stars:>=50000 is:public"]
REVIEWED = {
    "sindresorhus/awesome": "Curated directory of Awesome topic lists; CC0 preview source.",
    "sindresorhus/awesome-nodejs": "Curated Node.js package/resource list; CC0 preview source.",
    "rust-unofficial/awesome-rust": "Curated Rust libraries/resources list; CC0 preview source.",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def github(endpoint: str) -> dict:
    for attempt in range(3):
        try:
            result = subprocess.run(["gh", "api", endpoint], capture_output=True,
                                    text=True, encoding="utf-8", timeout=45, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as error:
            # Do not retry authorization or rate-limit failures blindly.
            if any(x in error.stderr for x in ("403", "401", "429", "rate limit")):
                raise RuntimeError("GitHub authorization/rate-limit boundary; no output published") from None
            if attempt == 2:
                raise RuntimeError("GitHub request failed after three attempts") from None
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise RuntimeError("GitHub request timed out after three attempts") from None
        time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable retry state")


def discover() -> tuple[list[dict], list[dict]]:
    candidates: dict[str, dict] = {}
    runs = []
    for query in QUERIES:
        page, received = 1, 0
        observed = now()
        while True:
            response = github(f"search/repositories?q={quote(query)}&per_page=100&page={page}&sort=stars&order=desc")
            if response.get("incomplete_results") or response["total_count"] > 1000:
                raise ValueError("Incomplete discovery; split the query before continuing")
            for item in response["items"]:
                name = item["full_name"]
                if name not in candidates:
                    candidates[name] = {"id": name, "stars": item["stargazers_count"],
                        "public": not item["private"], "observed_at": observed,
                        "default_branch": item["default_branch"], "queries": [],
                        "detected_license": (item.get("license") or {}).get("spdx_id"),
                        "is_resource_list": name in REVIEWED,
                        "decision": "selected" if name in REVIEWED else "excluded",
                        "reason": REVIEWED.get(name, "Outside reviewed three-source preview; suitability/license not adjudicated.")}
                candidates[name]["queries"].append(query)
            received += len(response["items"])
            if received >= response["total_count"]:
                break
            if not response["items"]:
                raise ValueError("Discovery pagination ended early")
            page += 1
        runs.append({"query": query, "observed_at": observed, "total_count": response["total_count"],
                     "received": received, "pages": page, "incomplete_results": False})
    if set(REVIEWED) - candidates.keys():
        raise ValueError("A reviewed source no longer independently qualifies in discovery")
    return sorted(candidates.values(), key=lambda x: x["id"]), runs


def plain(tokens: list) -> str:
    return " ".join("".join(t.content if t.type in {"text", "code_inline"} else
                            " " if t.type in {"softbreak", "hardbreak"} else ""
                            for t in tokens).split())


def extract(markdown: str, source: str) -> list[dict]:
    if len(markdown.encode()) > MAX_README:
        raise ValueError("README exceeds 2 MiB budget")
    tokens = MarkdownIt("commonmark", {"html": False}).parse(markdown)
    records, stack = [], []
    category = "General"
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and index + 1 < len(tokens):
            category = plain(tokens[index + 1].children or []) or "General"
        elif token.type == "list_item_open":
            stack.append(False)
        elif token.type == "list_item_close":
            stack.pop()
        elif token.type == "inline" and stack and not stack[-1]:
            if category.casefold() in {"contents", "table of contents", "contributing", "license", "related"}:
                continue
            children = token.children or []
            for offset, child in enumerate(children):
                if child.type != "link_open":
                    continue
                end = next((j for j in range(offset + 1, len(children)) if children[j].type == "link_close"), None)
                if end is None:
                    continue
                title = plain(children[offset + 1:end])
                url = safe_url(child.attrGet("href") or "")
                if not title or not url:
                    continue
                context = plain(children)
                description = context[len(title):].lstrip(" -–—:") if context.startswith(title) else context
                occurrence = {"source": source, "line": (token.map or [0])[0] + 1,
                              "title": title[:200], "description": description[:700], "category": category[:150]}
                records.append({"url": url, **occurrence})
                stack[-1] = True
                break
    return records


def merge_records(records: list[dict]) -> list[dict]:
    merged = {}
    for record in records:
        url = record["url"]
        item = merged.setdefault(url, {"id": hashlib.sha256(url.encode()).hexdigest()[:20],
            "url": url, "title": record["title"], "description": record["description"], "occurrences": []})
        occurrence = {k: v for k, v in record.items() if k != "url"}
        if occurrence not in item["occurrences"]:
            item["occurrences"].append(occurrence)
    for item in merged.values():
        item["occurrences"].sort(key=lambda x: (x["source"], x["line"]))
    return sorted(merged.values(), key=lambda x: (x["title"].casefold(), x["url"]))


def build() -> dict:
    candidates, runs = discover()
    sources, records = [], []
    for candidate in candidates:
        if candidate["decision"] != "selected":
            continue
        if not qualifies(candidate):
            raise ValueError("Selected source below threshold or not public/list")
        repo = candidate["id"]
        revision = github(f"repos/{repo}/commits/{quote(candidate['default_branch'], safe='')}")["sha"]
        readme = github(f"repos/{repo}/readme?ref={revision}")
        license_data = github(f"repos/{repo}/license?ref={revision}")
        if readme["size"] > MAX_README:
            raise ValueError("README exceeds budget")
        raw = base64.b64decode(readme["content"])
        license_raw = base64.b64decode(license_data["content"])
        license_text = license_raw.decode("utf-8")
        if license_data["license"]["spdx_id"] != "CC0-1.0" or "CC0 1.0 Universal" not in license_text:
            raise ValueError("License outside reviewed CC0 policy")
        source = {**candidate, "revision": revision, "extracted_at": now(),
                  "readme_path": readme["path"], "readme_sha256": hashlib.sha256(raw).hexdigest(),
                  "license": "CC0-1.0", "license_path": license_data["path"],
                  "license_text": license_text, "license_sha256": hashlib.sha256(license_raw).hexdigest()}
        extracted = extract(raw.decode("utf-8"), repo)
        if not extracted:
            raise ValueError(f"No supported records in {repo}")
        source["extracted_occurrences"] = len(extracted)
        sources.append(source)
        records.extend(extracted)
        cache = ROOT / "data/raw" / repo.replace("/", "--") / revision
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "README.md").write_bytes(raw)
        (cache / "LICENSE.txt").write_bytes(license_raw)
        print(f"{repo}: {len(extracted)} occurrences, {candidate['stars']} stars, revision {revision}")
    data = {"format_version": 1, "generated_at": now(), "discovery": runs, "candidates": candidates,
            "coverage": "Three reviewed CC0 lists; primary Markdown list-item links only. Not exhaustive.",
            "sources": sources, "resources": merge_records(records)}
    data["digest"] = digest(data)
    validate_catalogue(data)
    atomic_json(STAGING, data)
    return data


def publish(expected: str) -> dict:
    data = json.loads(STAGING.read_text(encoding="utf-8"))
    validate_catalogue(data)
    if data["digest"] != expected:
        raise ValueError("Stale acceptance: reviewed candidate digest has changed")
    atomic_json(PUBLISHED, data)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "publish", "validate"])
    parser.add_argument("--expected-digest")
    args = parser.parse_args()
    if args.command == "build":
        result = build()
    elif args.command == "publish":
        if not args.expected_digest:
            parser.error("publish requires --expected-digest after content/license review")
        result = publish(args.expected_digest)
    else:
        result = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        validate_catalogue(result)
    print(f"{len(result['resources'])} resources; digest {result['digest']}")
