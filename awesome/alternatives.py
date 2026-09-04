"""Pure same-heading co-occurrence ("see alternatives") derivation; no networking or runtime writes.

Epic E / #73. Reuses the exact same inputs as `awesome.projects.derive_projects` (the published
list index plus already-loaded, already-validated eligible list detail shards) -- no new crawling.
Where `derive_projects` groups parsed entries by canonical project URL, this module groups them by
`(list_id, category)` -- the original heading a curator filed the entry under -- so that for any
project, the "alternatives" it can offer are the other distinct projects a real curator placed
under the same heading in the same list. This is a factual re-grouping of already-published data,
never a similarity score: two projects sharing a heading in one list are not claimed to be
interchangeable, only co-filed by the same curator under the same original label.

A project cited under different headings (different lists, or different categories within one
list) surfaces alternatives per heading it actually occupies -- never a single merged "similar
projects" list, so every alternative stays traceable to the exact list + heading a real curator
placed it under.

Sharded like `data/projects/` (see that module's docstring for the size rationale, which applies
identically here): a tiny `data/alternatives-index.json` (counts + prefix -> shard-digest map only)
plus `data/alternatives/<2-hex-prefix>.json` shards, bucketed by the same project id used in
`data/projects/` (`awesome.projects.project_id`), so a UI can resolve a project's alternatives with
the same shard path it already uses for the project record itself.
"""
from __future__ import annotations

import re

from awesome.catalogue import digest, safe_url
from awesome.projects import project_id

FORMAT = 1
MAX_ALTERNATIVES_PER_HEADING = 3
CONTENT_POLICY = ("Alternatives are the other distinct projects a citing list's own curator filed "
                   "under the same original heading (list + category) as this project. This is a "
                   "factual co-occurrence re-grouping of already-published list content, never a "
                   "similarity or quality score. Headings with more than "
                   f"{MAX_ALTERNATIVES_PER_HEADING} distinct projects are capped; the cap is "
                   "disclosed per heading (`truncated` + `total_alternatives`), never a silent "
                   "truncation.")


def shard_path(prefix: str) -> str:
    return f"alternatives/{prefix}.json"


def derive_alternatives(index: dict, details: dict, generated_at: str) -> dict:
    """Group every eligible list's parsed entries by `(list_id, category)`, then, for every
    distinct project, record which other projects share at least one such heading with it.

    Performs no I/O; trusts nothing it wasn't handed (mirrors `awesome.projects.derive_projects`).
    Returns `{"index": <small published index>, "shards": {prefix: <shard document>}}`.
    """
    projects: dict[str, dict] = {}
    heading_buckets: dict[tuple[str, str], dict] = {}
    for item in index["lists"]:
        if item.get("state") != "eligible" or not item.get("detail"):
            continue
        detail = details[item["detail"]]
        for entry in detail["entries"]:
            url = entry["url"]
            canonical = safe_url(url)
            if not canonical or canonical != url:
                raise ValueError("Non-canonical or unsafe project URL in shard")
            pid = project_id(canonical)
            project = projects.setdefault(pid, {"id": pid, "url": canonical, "title": entry["title"], "headings": {}})
            heading_key = (item["id"], entry["category"])
            bucket = heading_buckets.setdefault(heading_key, {
                "list_id": item["id"], "list_name": item["name"], "list_url": item["url"],
                "category": entry["category"], "members": {},
            })
            bucket["members"].setdefault(pid, {"id": pid, "url": canonical, "title": entry["title"]})
            project["headings"].setdefault(heading_key, bucket)

    # Sort each heading's members exactly once, not once per project that touches it -- a large
    # heading (a big list's single busy category) shared by many projects would otherwise cost
    # O(members^2 log members) if every member re-sorted and re-filtered the whole bucket.
    take = MAX_ALTERNATIVES_PER_HEADING + 1  # +1 headroom in case the project itself lands in it
    for bucket in heading_buckets.values():
        ordered = sorted(bucket["members"].values(), key=lambda m: (m["title"].casefold(), m["url"]))
        bucket["ordered_members"] = ordered[:take]
        bucket["total_members"] = len(ordered)

    records = []
    for pid, project in projects.items():
        heading_records = []
        alt_ids: set[str] = set()
        ordered_headings = sorted(project["headings"].values(),
                                   key=lambda bucket: (bucket["list_name"].casefold(), bucket["category"].casefold()))
        for bucket in ordered_headings:
            # Every project this loop visits is itself a member of `bucket`, so total members - 1
            # is the exact alternative count without re-scanning the (possibly large) bucket.
            total = bucket["total_members"] - 1
            # Alternatives carry only id + title, not each project's own url: the UI resolves an
            # alternative to its own Project profile by id (already-published data/projects/), so
            # duplicating a full url string per alternative per member of every heading would be
            # pure redundant bytes at this catalogue's scale (an earlier cut of this artifact, with
            # url included and no per-heading cap discipline, published at ~4 GB before this fix).
            capped = [{"id": m["id"], "title": m["title"]}
                      for m in bucket["ordered_members"] if m["id"] != pid][:MAX_ALTERNATIVES_PER_HEADING]
            alt_ids.update(a["id"] for a in capped)
            heading_records.append({
                "list_id": bucket["list_id"], "list_name": bucket["list_name"],
                "list_url": bucket["list_url"], "category": bucket["category"],
                "alternatives": capped, "total_alternatives": total,
                "truncated": total > len(capped),
            })
        records.append({"id": pid, "url": project["url"], "title": project["title"],
                         "headings": heading_records, "alternative_count": len(alt_ids)})
    records.sort(key=lambda r: (-r["alternative_count"], r["url"]))

    buckets: dict[str, list[dict]] = {}
    for record in records:
        buckets.setdefault(record["id"][:2], []).append(record)

    shards = {}
    for prefix, bucket_records in buckets.items():
        shard = {"format_version": FORMAT, "prefix": prefix, "source_index_digest": index["digest"],
                  "projects": bucket_records}
        shard["digest"] = digest(shard)
        shards[prefix] = shard

    top_index = {"format_version": FORMAT, "source_index_digest": index["digest"], "generated_at": generated_at,
                 "content_policy": CONTENT_POLICY, "max_alternatives_per_heading": MAX_ALTERNATIVES_PER_HEADING,
                 "counts": {"projects": len(records), "shards": len(shards),
                            "with_alternatives": sum(1 for r in records if r["alternative_count"])},
                 "shards": {prefix: shard["digest"] for prefix, shard in shards.items()}}
    top_index["digest"] = digest(top_index)
    return {"index": top_index, "shards": shards}


def _validate_heading(heading: dict, eligible_lists: dict) -> None:
    list_item = eligible_lists.get(heading.get("list_id"))
    if not list_item:
        raise ValueError("Heading references a non-eligible or unknown list")
    if heading.get("list_name") != list_item["name"] or heading.get("list_url") != list_item["url"]:
        raise ValueError("Heading list identity mismatch")
    if not heading.get("category"):
        raise ValueError("Heading missing category")
    alternatives = heading.get("alternatives") or []
    if len(alternatives) > MAX_ALTERNATIVES_PER_HEADING:
        raise ValueError("Heading exceeds the published alternatives cap")
    seen = set()
    for alt in alternatives:
        if not re.fullmatch(r"[0-9a-f]{20}", alt.get("id") or ""):
            raise ValueError("Invalid alternative project id")
        if not alt.get("title"):
            raise ValueError("Invalid alternative provenance")
        if alt["id"] in seen:
            raise ValueError("Duplicate alternative within one heading")
        seen.add(alt["id"])
    total = heading.get("total_alternatives")
    if total is None or total < len(alternatives):
        raise ValueError("Invalid total_alternatives")
    if heading.get("truncated") != (total > len(alternatives)):
        raise ValueError("Truncated flag does not match counted alternatives")


def validate_shard(shard: dict, prefix: str, index: dict, known_project_ids: set[str] | None = None) -> None:
    if shard.get("format_version") != FORMAT or shard.get("prefix") != prefix:
        raise ValueError("Unsupported or mismatched alternatives shard")
    if shard.get("digest") != digest({k: v for k, v in shard.items() if k != "digest"}):
        raise ValueError("Alternatives shard digest mismatch")
    if not shard.get("source_index_digest") or shard["source_index_digest"] != index.get("digest"):
        raise ValueError("Alternatives shard does not match the published list index")
    eligible_lists = {item["id"]: item for item in index["lists"] if item.get("state") == "eligible"}
    seen_ids = set()
    for record in shard.get("projects", []):
        url = record.get("url")
        if not safe_url(url) or url != record.get("url"):
            raise ValueError("Invalid project URL")
        if record.get("id") != project_id(url) or not record["id"].startswith(prefix):
            raise ValueError("Project identity or shard placement mismatch")
        if record["id"] in seen_ids or not record.get("title"):
            raise ValueError("Duplicate or unnamed project")
        seen_ids.add(record["id"])
        alt_ids: set[str] = set()
        for heading in record.get("headings") or []:
            _validate_heading(heading, eligible_lists)
            for alt in heading.get("alternatives", []):
                alt_ids.add(alt["id"])
                if known_project_ids is not None and alt["id"] not in known_project_ids:
                    raise ValueError("Alternative references an unknown project id")
        if record.get("alternative_count") != len(alt_ids):
            raise ValueError("alternative_count does not reconcile with headings")


def validate_alternatives(data: dict, index: dict, shards: dict | None = None) -> None:
    """Validate the tiny published index; pass `shards` to also validate shard content, global
    cross-shard uniqueness, and (once every shard is present) that every alternative id actually
    resolves to a project published in this same artifact."""
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported alternatives catalogue format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Alternatives catalogue digest mismatch")
    if not data.get("source_index_digest") or data["source_index_digest"] != index.get("digest"):
        raise ValueError("Alternatives catalogue does not match the published list index")
    shard_digests = data.get("shards") or {}
    for prefix, shard_digest in shard_digests.items():
        if not re.fullmatch(r"[0-9a-f]{2}", prefix) or not re.fullmatch(r"[0-9a-f]{64}", shard_digest or ""):
            raise ValueError("Invalid shard registry entry")
    if data.get("counts", {}).get("shards") != len(shard_digests):
        raise ValueError("Shard count does not reconcile")
    if shards is None:
        return
    if set(shards) != set(shard_digests):
        raise ValueError("Shard set does not match the published index")
    known_ids = {record["id"] for shard in shards.values() for record in shard.get("projects", [])}
    total_projects, with_alternatives = 0, 0
    seen_ids = set()
    for prefix, shard in shards.items():
        if shard.get("digest") != shard_digests[prefix]:
            raise ValueError("Shard digest does not match the index's registered shard digest")
        validate_shard(shard, prefix, index, known_ids)
        for record in shard["projects"]:
            if record["id"] in seen_ids:
                raise ValueError("Duplicate project identity across shards")
            seen_ids.add(record["id"])
            if record["alternative_count"]:
                with_alternatives += 1
        total_projects += len(shard["projects"])
    counts = data.get("counts", {})
    if counts.get("projects") != total_projects or counts.get("with_alternatives") != with_alternatives:
        raise ValueError("Project counts do not reconcile")
