"""Pure derivation and validation of the offline cross-list search index; no networking or runtime
writes.

A3 (cross-list project search) and A4 (entry-level topic normalization) were redesigned after A2
(issue #65) found raw cross-list citation count is predominantly copy-lineage, not independent
curation. This module derives, per project (from the already-published, already-validated
`data/projects/<prefix>.json` shards `awesome.projects` produces), a small "search record" carrying
only what the hosted "Search projects" view needs to filter, rank, and honestly label results:

- `title`/`url`/`list_count`: copied unmodified from the project record.
- `independent_list_count`: the copy-lineage-discounted citation count, reusing #65's validated
  detection heuristic (`awesome.copy_lineage`) -- never a synthesized trust/quality score.
- `topics`: entry-level normalized category tags (`awesome.topics`, A4) for semantic search
  matching, not an authoritative taxonomy.

Sharded the same way `data/projects/` is (by project id prefix), but each record is much smaller
(no per-occurrence detail -- the UI fetches citation/provenance detail on demand from the existing
project shard for just the displayed result page, never duplicating that data here). See
`tools/derive_search_index.py` for the streaming, one-project-shard-at-a-time offline build that
keeps this module free of any large-corpus memory footprint.
"""
from __future__ import annotations

import re

from awesome.catalogue import digest
from awesome.copy_lineage import independent_count
from awesome.topics import normalized_topics

FORMAT = 1
CONTENT_POLICY = (
    "title/url/list_count are copied unmodified from the published project record "
    "(awesome/projects.py, data/project-index.json). independent_list_count is a "
    "copy-lineage-discounted count -- the number of independence clusters among citing lists, per "
    "issue #65's validated title-similarity heuristic (awesome/copy_lineage.py) -- never a "
    "synthesized quality/trust score, and equal to list_count only when no two citing lists' entry "
    "text was classified as copy-lineage. topics are entry-level normalized category labels "
    "(awesome/topics.py), a search-matching aid, not an authoritative taxonomy. See issue #65 for "
    "the finding that raw cross-list citation count is predominantly copy-lineage."
)


def shard_path(prefix: str) -> str:
    return f"search/{prefix}.json"


def derive_shard_record(project_record: dict, topic_overrides: dict | None = None) -> dict:
    occurrences = project_record["occurrences"]
    return {
        "id": project_record["id"],
        "url": project_record["url"],
        "title": project_record["title"],
        "list_count": project_record["list_count"],
        "independent_list_count": independent_count(occurrences),
        "topics": normalized_topics(occurrences, overrides=topic_overrides),
    }


def derive_search_shard(project_shard: dict, source_project_digest: str, topic_overrides: dict | None = None) -> dict:
    """`project_shard` is one already-validated `data/projects/<prefix>.json` shard document (see
    `awesome.projects.validate_shard`). A pure, single-shard transform -- callers own streaming
    shard-by-shard from disk so the full 900k+-project corpus is never held in memory at once (see
    `tools/derive_search_index.py`). `topic_overrides` is H3 (issue #53)'s optional headless-CLI
    overlay (`awesome.interpret_topics.as_overrides`); omitted or `None` reproduces the exact
    heuristic-only output this module always produced before H3 existed."""
    records = [derive_shard_record(record, topic_overrides) for record in project_shard["projects"]]
    shard = {"format_version": FORMAT, "prefix": project_shard["prefix"],
              "source_project_digest": source_project_digest, "projects": records}
    shard["digest"] = digest(shard)
    return shard


def build_top_index(source_project_digest: str, generated_at: str, shard_digests: dict[str, str],
                     counts: dict) -> dict:
    top_index = {"format_version": FORMAT, "source_project_digest": source_project_digest,
                 "generated_at": generated_at, "content_policy": CONTENT_POLICY,
                 "counts": counts, "shards": dict(shard_digests)}
    top_index["digest"] = digest(top_index)
    return top_index


def validate_search_shard(shard: dict, prefix: str, project_index: dict) -> None:
    if shard.get("format_version") != FORMAT or shard.get("prefix") != prefix:
        raise ValueError("Unsupported or mismatched search shard")
    if shard.get("digest") != digest({k: v for k, v in shard.items() if k != "digest"}):
        raise ValueError("Search shard digest mismatch")
    if not shard.get("source_project_digest") or shard["source_project_digest"] != project_index.get("digest"):
        raise ValueError("Search shard does not match the published project index")
    seen_ids, seen_urls = set(), set()
    for record in shard.get("projects", []):
        record_id = record.get("id", "")
        if not re.fullmatch(r"[0-9a-f]{20}", record_id) or not record_id.startswith(prefix):
            raise ValueError("Invalid or misplaced search record id")
        if record_id in seen_ids or record.get("url") in seen_urls or not record.get("title"):
            raise ValueError("Duplicate or unnamed search record")
        seen_ids.add(record_id)
        seen_urls.add(record.get("url"))
        list_count = record.get("list_count")
        independent = record.get("independent_list_count")
        if not isinstance(list_count, int) or list_count < 1:
            raise ValueError("Invalid list_count in search record")
        if not isinstance(independent, int) or independent < 1 or independent > list_count:
            raise ValueError("Invalid independent_list_count in search record")
        if not isinstance(record.get("topics"), list) or len(record["topics"]) > 6:
            raise ValueError("Invalid topics in search record")


def validate_search_index(data: dict, project_index: dict, shards: dict | None = None) -> None:
    """Validate the tiny published top index (counts + prefix -> shard-digest map). Pass `shards`
    (prefix -> loaded shard document) to also validate every shard's content and global
    cross-shard uniqueness -- callers own loading shard files from disk, matching
    `awesome.projects.validate_projects`'s own optional-`shards` pattern."""
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported search index format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Search index digest mismatch")
    if not data.get("source_project_digest") or data["source_project_digest"] != project_index.get("digest"):
        raise ValueError("Search index does not match the published project index")
    shard_digests = data.get("shards") or {}
    for prefix, shard_digest in shard_digests.items():
        if not re.fullmatch(r"[0-9a-f]{2}", prefix) or not re.fullmatch(r"[0-9a-f]{64}", shard_digest or ""):
            raise ValueError("Invalid search shard registry entry")
    counts = data.get("counts", {})
    if counts.get("shards") != len(shard_digests):
        raise ValueError("Search shard count does not reconcile")
    if shards is None:
        return
    if set(shards) != set(shard_digests):
        raise ValueError("Search shard set does not match the published index")
    total = 0
    seen_ids, seen_urls = set(), set()
    for prefix, shard in shards.items():
        if shard.get("digest") != shard_digests[prefix]:
            raise ValueError("Search shard digest does not match the index's registered digest")
        validate_search_shard(shard, prefix, project_index)
        for record in shard["projects"]:
            if record["id"] in seen_ids or record["url"] in seen_urls:
                raise ValueError("Duplicate search record identity or URL across shards")
            seen_ids.add(record["id"])
            seen_urls.add(record["url"])
        total += len(shard["projects"])
    if counts.get("projects") != total:
        raise ValueError("Search record count does not reconcile")
