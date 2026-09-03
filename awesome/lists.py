"""Pure list-first catalogue model. No network, inference, or runtime writes."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from urllib.parse import urljoin, quote

from markdown_it import MarkdownIt
from awesome.catalogue import digest, safe_url

MIN_STARS = 100
FORMAT = 2
MAX_README = 2 * 1024 * 1024
MAX_INDEX = 40 * 1024 * 1024
SKIP_SECTIONS = re.compile(r"^(table of contents|contents|contribut\w*|licen[cs]e|installation|install|usage|sponsors?|badges?|acknowledgements?|star history)$", re.I)
LIST_INTENT = re.compile(r"curated|\blist\s+of\b|\blists\s+of\b|\bcollection\s+of\b|awesome\s+(?:resources|lists|links)|资源列表|精选|资源汇总|清单", re.I)
TOPICS = {
    "AI & machine learning": r"\b(ai|llm|machine.learning|deep.learning|artificial.intelligence|agents|generative)\b",
    "Software development": r"\b(programming|development|developer|code|software|javascript|python|rust|java|typescript|golang|nodejs|cpp|dotnet)\b",
    "Self-hosting & infrastructure": r"\b(self.host(?:ed|ing)?|devops|kubernetes|docker|infrastructure|cloud|homelab|sysadmin)\b",
    "Data & analytics": r"\b(data|database|analytics|visualization|statistics|sql)\b",
    "Security & privacy": r"\b(security|privacy|hacking|pentest|cryptography|osint)\b",
    "Design & creativity": r"\b(design|creative|art|fonts|icons|animation|ux|ui|music)\b",
    "Learning & careers": r"\b(learn|learning|courses|education|interview|career|books|tutorials)\b",
    "Web & mobile": r"\b(web|frontend|front.end|react|vue|android|ios|mobile|flutter)\b",
    "Science & engineering": r"\b(science|scientific|engineering|robotics|mathematics|physics|biology|research)\b",
    "Productivity & life": r"\b(productivity|personal|life|health|travel|finance|business|work)\b",
    "Games & media": r"\b(games?|gaming|video|media|gamedev|unity|unreal)\b",
    "Meta directories": r"(?:list of (?:awesome )?lists|awesome lists|awesome-awesome|awesome indexes)",
}


def plain(children: list) -> str:
    return " ".join("".join(t.content if t.type in {"text", "code_inline"} else
                           " " if t.type in {"softbreak", "hardbreak"} else ""
                           for t in children).split())


def slug(text: str) -> str:
    return re.sub(r"[^\w\- ]", "", text.lower(), flags=re.UNICODE).replace(" ", "-")


def parse_readme(markdown: str, repo: str, revision: str, path: str = "README.md") -> dict:
    """Extract factual titles/links and original hierarchy, not copied descriptions."""
    if len(markdown.encode()) > MAX_README:
        raise ValueError("README exceeds 2 MiB parse budget")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", repo) or repo.split("/")[-1] in {".", ".."} or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Invalid repository identity")
    source = f"https://github.com/{repo}/blob/{revision}/{quote(path, safe='/')}"
    tokens = MarkdownIt("commonmark", {"html": False}).enable("table").parse(markdown)
    sections, entries, hierarchy, counts = [], [], [], Counter()
    stack, row, in_header, headers, table_headers = [], None, False, [], []
    current = None

    def entry_from(children: list, line: int, properties: dict | None = None):
        if current and SKIP_SECTIONS.fullmatch(current["title"]):
            return None
        for i, child in enumerate(children):
            if child.type != "link_open":
                continue
            raw = child.attrGet("href") or ""
            if raw.startswith("#"):
                continue
            end = next((j for j in range(i + 1, len(children)) if children[j].type == "link_close"), i)
            title = plain(children[i + 1:end])
            url = safe_url(urljoin(source, raw))
            if not title or not url or re.search(r"shields\.io|badgen\.net|/badge/", url):
                continue
            return {"title": title[:200], "url": url, "category": current["id"] if current else "general",
                    "source_url": source + f"#L{line}", "line": line,
                    "properties": properties or {}}
        return None

    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            label = plain(tokens[i + 1].children or [])[:200]
            level = int(token.tag[1:])
            hierarchy = [h for h in hierarchy if h[0] < level]
            base = slug(label); n = counts[base]; counts[base] += 1
            anchor = base + (f"-{n}" if n else "")
            current = {"id": anchor or f"section-{i}", "title": label, "level": level,
                       "path": [h[1] for h in hierarchy] + [label], "source_url": source + "#" + anchor}
            hierarchy.append((level, label)); sections.append(current)
        elif token.type == "list_item_open":
            stack.append(False)
        elif token.type == "list_item_close":
            stack.pop()
        elif token.type == "thead_open":
            in_header = True; headers = []
        elif token.type == "thead_close":
            in_header = False; table_headers = headers
        elif token.type == "tr_open":
            row = []
        elif token.type == "tr_close" and row is not None:
            if not in_header:
                props = {table_headers[j]: cell[0][:120] for j, cell in enumerate(row)
                         if j < len(table_headers) and j > 0 and
                         re.search(r"licen[cs]e|language|platform|stars|version|price|type", table_headers[j], re.I)}
                for _, children, line in row:
                    item = entry_from(children, line, props)
                    if item:
                        entries.append(item); break
            row = None
        elif token.type == "inline":
            children = token.children or []
            line = (token.map or [0])[0] + 1
            if row is not None:
                if in_header:
                    headers.append(plain(children)[:100])
                row.append((plain(children), children, line))
            elif stack and not stack[-1]:
                item = entry_from(children, line)
                if item:
                    entries.append(item); stack[-1] = True
    used = Counter(e["category"] for e in entries)
    for section in sections:
        section["entries"] = used[section["id"]]
    if used["general"]:
        sections.insert(0, {"id": "general", "title": "General", "level": 1,
                            "path": ["General"], "source_url": source, "entries": used["general"]})
    return {"sections": sections, "entries": entries, "properties": sorted({p for e in entries for p in e["properties"]}),
            "entry_count": len(entries), "unique_links": len({e["url"] for e in entries}),
            "category_count": len(used), "parser": "markdown-lists-and-tables-v2",
            "coverage": "Supported Markdown list items and table rows in this pinned README; other files and embedded HTML are not counted."}


def classify(meta: dict, parsed: dict | None, markdown: str = "") -> tuple[str, str]:
    if not meta.get("public", False):
        return "excluded", "Repository is not public."
    stars = meta.get("stars")
    if not isinstance(stars, int) or isinstance(stars, bool):
        return "pending", "Star count is unavailable."
    if stars < MIN_STARS:
        return "excluded", "Observed stars are below 100."
    if parsed is None:
        return "pending", "README has not been parsed or its format is unsupported."
    description = meta.get("description") or ""
    # Primary-purpose evidence, not incidental links to somebody else's curated list.
    introduction = markdown.split("\n## ", 1)[0][:2000]
    purpose = re.compile(r"(?:^|\n)\W*(?:(?:this|an?|the)\s+)?(?:is\s+)?(?:a\s+)?(?:(?:curated|opinionated|comprehensive|categorized|maintained|hand-picked|community-driven|sorted|awesome|useful|selected)\s+)*(?:list|collection|directory)\s+of\b", re.I)
    description_intent = bool(purpose.search(description) or re.match(r"^\W*(?:awesome|curated)\s+(?:[\w-]+\s+){0,5}(?:lists?|resources|collection)\b", description, re.I))
    application = bool(re.search(r"\b(application|framework|library|toolkit|editor|window manager|browser extension|platform)\b", description, re.I))
    intent = description_intent or (not application and bool(purpose.search(introduction)))
    if intent and parsed["unique_links"] >= 3:
        return "eligible", "Curated-list intent and at least three distinct supported content links observed."
    if parsed["unique_links"] >= 5:
        return "pending", "Links found, but curated-list intent is uncertain; not silently excluded."
    if intent:
        return "pending", "List intent found; insufficient supported README content (may use other files)."
    return "excluded", "No curated-list intent and insufficient supported list content in inspected README."


def topics(meta: dict) -> list[str]:
    text = " ".join([meta.get("name", ""), meta.get("description") or "", *meta.get("github_topics", [])])
    return [name for name, pattern in TOPICS.items() if re.search(pattern, text, re.I)] or ["Other topics"]


def freshness(content_updated: str | None, as_of: str) -> dict:
    if not content_updated:
        return {"days": None, "range": "Unknown", "index": None}
    try:
        age = max(0, (datetime.fromisoformat(as_of.replace("Z", "+00:00")) -
                      datetime.fromisoformat(content_updated.replace("Z", "+00:00"))).total_seconds() / 86400)
    except (ValueError, TypeError):
        return {"days": None, "range": "Unknown", "index": None}
    label = next((f"Within {n} days" for n in (30, 90, 180, 365) if age <= n), "Older than a year")
    return {"days": int(age), "range": label, "index": round(100 * 2 ** (-age / 180), 1)}


def profile(meta: dict, parsed: dict | None, markdown: str = "") -> tuple[dict, dict | None]:
    if meta.get("public") is not True:
        parsed, markdown = None, ""
    state, reason = classify(meta, parsed, markdown)
    item = {**meta, "state": state, "reason": reason, "topics": topics(meta),
            "topic_method": "Derived keyword mapping from repository name, description and GitHub topics.",
            "scope": (meta.get("description") or "Explore the upstream list for its stated scope.")[:500],
            "freshness": freshness(meta.get("content_updated_at"), meta["observed_at"]),
            "entry_count": parsed["entry_count"] if parsed else None,
            "unique_links": parsed["unique_links"] if parsed else None,
            "category_count": parsed["category_count"] if parsed else None,
            "contributors_count": None, "contributors_status": "Not yet observed",
            "content_policy": "Metadata, factual titles and upstream links only; no copied descriptions. Source retains its own license.",
            "detail": None}
    detail = None
    if parsed and meta.get("public") is True:
        detail = {"format_version": FORMAT, "repository_id": item["id"], "name": item["name"],
                  "revision": item["revision"], "readme_path": item["readme_path"],
                  "readme_sha256": item["readme_sha256"], **parsed,
                  "contributors": [], "attribution": f"Content curated by {item['name']} contributors.",
                  "license": item.get("license"), "license_url": item["url"] + "/tree/" + item["revision"]}
        detail["digest"] = digest(detail)
        item["detail"] = f"lists/{detail['digest']}.json"
        item["detail_digest"] = detail["digest"]
    return item, detail


def validate_detail(detail: dict, item: dict) -> None:
    if detail.get("digest") != digest({k: v for k, v in detail.items() if k != "digest"}):
        raise ValueError("Detail digest mismatch")
    if detail["digest"] != item.get("detail_digest") or detail["repository_id"] != item["id"]:
        raise ValueError("Detail identity mismatch")
    if len(detail["entries"]) != item["entry_count"]:
        raise ValueError("Entry count mismatch")
    for entry in detail["entries"]:
        if not safe_url(entry["url"]) or not safe_url(entry["source_url"]):
            raise ValueError("Unsafe detail link")


def validate_index(index: dict, data_root: Path | None = None) -> None:
    if index.get("format_version") != FORMAT or index.get("min_stars") != MIN_STARS:
        raise ValueError("Wrong list catalogue contract")
    if index.get("digest") != digest({k: v for k, v in index.items() if k != "digest"}):
        raise ValueError("Index digest mismatch")
    seen = set()
    for item in index["lists"]:
        if item["id"] in seen or item["state"] not in {"eligible", "pending", "excluded"}:
            raise ValueError("Duplicate identity or invalid classification")
        seen.add(item["id"])
        if not safe_url(item["url"]) or not item.get("reason"):
            raise ValueError("Missing safe provenance")
        if item["state"] == "eligible" and (not item["public"] or item["stars"] < MIN_STARS):
            raise ValueError("Ineligible published list")
        for key in ("stars", "forks", "entry_count", "unique_links", "category_count", "contributors_count"):
            value = item.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ValueError("Invalid numeric metric")
        if item.get("detail"):
            if item.get("public") is not True:
                raise ValueError("Non-public repository cannot publish detail")
            if not re.fullmatch(r"lists/[a-f0-9]{64}\.json", item["detail"]):
                raise ValueError("Unsafe shard path")
            if data_root:
                path = data_root / item["detail"]
                if path.is_symlink() or path.stat().st_size > MAX_README * 5:
                    raise ValueError("Invalid shard")
                validate_detail(json.loads(path.read_text(encoding="utf-8")), item)
    if dict(Counter(x["state"] for x in index["lists"])) != index["counts"]:
        raise ValueError("Classification counts do not reconcile")


def load_index(path: Path) -> dict:
    if path.stat().st_size > MAX_INDEX:
        raise ValueError("Index exceeds runtime budget")
    index = json.loads(path.read_text(encoding="utf-8")); validate_index(index)
    return index
