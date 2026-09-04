"""Pure project<->list dedup derivation and validation; no networking or runtime writes.

Derives a project-level view from the existing list-first catalogue: every eligible list's
parsed entries are grouped by canonical URL (the same `awesome.catalogue.safe_url`
canonicalization `awesome.lists.parse_readme` already applies), producing, for each distinct
project, the set of independent eligible lists that include it. This is a factual dedup/count
structure only -- see A2 (issue tracking the cross-list co-occurrence validation spike) before
any consensus/trust framing is attached to `list_count` in the UI.

Sharded like `data/lists/`: full per-project detail (which can run into hundreds of millions of
bytes across 900k+ projects -- too large for one committed JSON file, and past GitHub's 100 MB
single-file limit) lives in `data/projects/<2-hex-prefix>.json` shards, bucketed by the first two
hex characters of each project's `id` (256 buckets; a sha256-derived id is close to uniformly
distributed, so no bucket concentrates a meaningful share of the total). Even a *summary-only* row
per project (no occurrence detail) for 900k+ projects would itself exceed 100 MB, so the published
top-level `data/project-index.json` carries no per-project rows at all -- only counts and a
prefix -> shard-digest map (256 entries). Every per-project field, including the summary fields a
future UI would page over, lives only in its shard.
"""
from __future__ import annotations

import hashlib
import re

from awesome.catalogue import digest, safe_url

FORMAT = 2
SHARD_PATH = re.compile(r"projects/[0-9a-f]{2}\.json")
CONTENT_POLICY = ("Factual titles/categories/source links copied from each citing list's own parsed "
                   "entry; no invented or merged descriptions. list_count counts distinct citing "
                   "lists (occurrence_count counts raw parsed entries, which can exceed list_count "
                   "when one list cites a URL more than once). Neither is a validated trust/quality "
                   "signal -- see the cross-list co-occurrence validation issue before treating "
                   "either as one.")


def project_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def shard_path(prefix: str) -> str:
    return f"projects/{prefix}.json"


def _occurrence(list_item: dict, entry: dict) -> dict:
    return {
        "list_id": list_item["id"],
        "list_name": list_item["name"],
        "list_url": list_item["url"],
        "title": entry["title"],
        "category": entry["category"],
        "source_url": entry["source_url"],
    }


def derive_projects(index: dict, details: dict, generated_at: str) -> dict:
    """Deduplicate entries across eligible lists by canonical project URL.

    `details` maps each eligible list item's `detail` path (as it appears on the index item) to
    that list's already-loaded, already-validated detail shard. This function performs no I/O and
    trusts nothing it wasn't handed -- callers own loading and validating both the index and its
    referenced shards (`awesome.lists.validate_index` / `validate_detail`) before calling this.

    Returns `{"index": <small published index>, "shards": {prefix: <shard document>}}`.
    """
    projects: dict[str, dict] = {}
    for item in index["lists"]:
        if item.get("state") != "eligible" or not item.get("detail"):
            continue
        detail = details[item["detail"]]
        for entry in detail["entries"]:
            url = entry["url"]
            canonical = safe_url(url)
            if not canonical or canonical != url:
                # parse_readme already canonicalizes entry URLs; a mismatch here means the shard
                # was tampered with or is stale relative to the current safe_url() rules.
                raise ValueError("Non-canonical or unsafe project URL in shard")
            bucket = projects.get(canonical)
            if bucket is None:
                bucket = {"id": project_id(canonical), "url": canonical, "title": entry["title"],
                          "occurrences": []}
                projects[canonical] = bucket
            bucket["occurrences"].append(_occurrence(item, entry))

    records = []
    for bucket in projects.values():
        bucket["occurrences"].sort(key=lambda occurrence: (occurrence["list_name"].casefold(), occurrence["source_url"]))
        # `list_count` is the number of DISTINCT eligible lists citing this URL -- the epic's actual
        # requirement ("the number of independent eligible lists that include a given project").
        # `occurrence_count` is the raw number of parsed entries (>= list_count): one list can cite
        # the same URL more than once (e.g. under two categories, or once in a table of contents and
        # once in the body). Collapsing that distinction would silently inflate a single list's
        # internal repetition into what looks like cross-list agreement.
        bucket["list_count"] = len({occurrence["list_id"] for occurrence in bucket["occurrences"]})
        bucket["occurrence_count"] = len(bucket["occurrences"])
        records.append(bucket)
    records.sort(key=lambda record: (-record["list_count"], -record["occurrence_count"], record["url"]))

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
                 "content_policy": CONTENT_POLICY,
                 "counts": {"projects": len(records), "occurrences": sum(r["occurrence_count"] for r in records),
                            "shards": len(shards)},
                 "shards": {prefix: shard["digest"] for prefix, shard in shards.items()}}
    top_index["digest"] = digest(top_index)
    return {"index": top_index, "shards": shards}


def _validate_occurrences(record: dict, eligible_lists: dict) -> int:
    occurrences = record.get("occurrences") or []
    distinct_lists = {occurrence.get("list_id") for occurrence in occurrences}
    if (not occurrences or len(occurrences) != record.get("occurrence_count")
            or len(distinct_lists) != record.get("list_count")):
        raise ValueError("Occurrence count mismatch")
    seen_in_project = set()
    for occurrence in occurrences:
        list_item = eligible_lists.get(occurrence.get("list_id"))
        if not list_item:
            raise ValueError("Occurrence references a non-eligible or unknown list")
        if (occurrence.get("list_name") != list_item["name"]
                or occurrence.get("list_url") != list_item["url"]):
            raise ValueError("Occurrence list identity mismatch")
        if not occurrence.get("title") or not safe_url(occurrence.get("source_url") or ""):
            raise ValueError("Invalid occurrence provenance")
        key = (occurrence["list_id"], occurrence["source_url"])
        if key in seen_in_project:
            raise ValueError("Duplicate occurrence for the same list entry")
        seen_in_project.add(key)
    return len(occurrences)


def validate_shard(shard: dict, prefix: str, index: dict) -> None:
    if shard.get("format_version") != FORMAT or shard.get("prefix") != prefix:
        raise ValueError("Unsupported or mismatched project shard")
    if shard.get("digest") != digest({k: v for k, v in shard.items() if k != "digest"}):
        raise ValueError("Project shard digest mismatch")
    if not shard.get("source_index_digest") or shard["source_index_digest"] != index.get("digest"):
        raise ValueError("Project shard does not match the published list index")
    eligible_lists = {item["id"]: item for item in index["lists"] if item.get("state") == "eligible"}
    seen_ids, seen_urls = set(), set()
    for record in shard.get("projects", []):
        url = record.get("url")
        if not safe_url(url) or url != record.get("url"):
            raise ValueError("Invalid project URL")
        if record.get("id") != project_id(url) or not record["id"].startswith(prefix):
            raise ValueError("Project identity or shard placement mismatch")
        if record["id"] in seen_ids or url in seen_urls or not record.get("title"):
            raise ValueError("Duplicate or unnamed project")
        seen_ids.add(record["id"])
        seen_urls.add(url)
        _validate_occurrences(record, eligible_lists)


def validate_projects(data: dict, index: dict, shards: dict | None = None) -> None:
    """Validate the tiny published index (counts + prefix->shard-digest map only -- no per-project
    rows, see module docstring). Pass `shards` (prefix -> loaded shard document, as returned by
    `derive_projects`) to also validate every shard's content and global cross-shard uniqueness --
    callers own loading shard files from disk (see `tools.derive_projects.load_projects`), matching
    `awesome.lists.validate_index`'s own optional-`data_root` pattern for its list detail shards."""
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported project catalogue format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Project catalogue digest mismatch")
    if not data.get("source_index_digest") or data["source_index_digest"] != index.get("digest"):
        raise ValueError("Project catalogue does not match the published list index")
    shard_digests = data.get("shards") or {}
    for prefix, shard_digest in shard_digests.items():
        if not re.fullmatch(r"[0-9a-f]{2}", prefix) or not re.fullmatch(r"[0-9a-f]{64}", shard_digest or ""):
            raise ValueError("Invalid shard registry entry")
    counts = data.get("counts", {})
    if counts.get("shards") != len(shard_digests):
        raise ValueError("Shard count does not reconcile")
    if shards is None:
        return
    if set(shards) != set(shard_digests):
        raise ValueError("Shard set does not match the published index")
    total_projects, total_occurrences = 0, 0
    seen_ids, seen_urls = set(), set()
    for prefix, shard in shards.items():
        if shard.get("digest") != shard_digests[prefix]:
            raise ValueError("Shard digest does not match the index's registered shard digest")
        validate_shard(shard, prefix, index)
        for record in shard["projects"]:
            if record["id"] in seen_ids or record["url"] in seen_urls:
                raise ValueError("Duplicate project identity or URL across shards")
            seen_ids.add(record["id"])
            seen_urls.add(record["url"])
            total_occurrences += record["occurrence_count"]
        total_projects += len(shard["projects"])
    if counts.get("projects") != total_projects or counts.get("occurrences") != total_occurrences:
        raise ValueError("Project/occurrence counts do not reconcile")
