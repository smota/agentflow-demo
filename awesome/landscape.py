"""Pure landscape membership, signatures, pair previews, and set-diff.

Offline artifact for the Explore network map (issue #86 candidate clustering as map color).
No I/O and no Streamlit. Hosted UI may import this module for validation, shard paths, and
set-diff over already-loaded compact shards — never to scan `data/projects/`.

Copy-lineage and near-duplicate reuse `awesome.copy_lineage` and `awesome.network` thresholds
exactly; they are a filter/lens, never a quality, trust, or best-list score. Unique · Family ·
Shared · Hub counts are a composition of citations, not a ranking.

Observed on the committed catalogue snapshot that first published this artifact: 6,377 eligible
lists, 256 shards, 3,311 community ids including 2,643 isolated/unclustered lists. The index stays
about 1.5 MB; shards are compact membership and previews, not a copy of the project corpus.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from awesome.catalogue import digest
from awesome.copy_lineage import is_copy_lineage
from awesome.network import (
    MIN_SHARED_PROJECTS,
    NEAR_DUP_COPY_FRACTION,
    NEAR_DUP_JACCARD,
    neighbors_of,
)
from awesome.network_view import NEIGHBOR_LIMIT

FORMAT = 1
PREVIEW_LIMIT = 8
CONTENT_POLICY = (
    "Landscape coordinates, communities, Unique/Family/Shared/Hub counts, and copy-lineage "
    "previews are observed composition of already-published citations. Communities are a "
    "disclosed candidate clustering used as map color (issue #86); they do not replace list "
    "topics and are not an ontology. Near-duplicate (jaccard >= "
    f"{NEAR_DUP_JACCARD} and copy_fraction >= {NEAR_DUP_COPY_FRACTION}, via awesome.copy_lineage) "
    "is a filter/lens, never a quality, trust, or best-list score. Unique · Family · Shared · Hub "
    "partition a list's distinct cited projects (composition of citations, not quality). "
    f"Pair previews cover published list_pairs (shared >= {MIN_SHARED_PROJECTS}) capped at "
    f"{PREVIEW_LIMIT} per independent/copy-lineage split with truncated/total disclosed. "
    "Unknown entry counts keep a disclosed default map size, never zero-as-unknown."
)


def list_shard_prefix(list_id: str) -> str:
    return hashlib.sha256(list_id.encode()).hexdigest()[:2]


def shard_path(prefix: str) -> str:
    return f"landscape/{prefix}.json"


def set_diff(memberships: dict[str, list[dict]], hub_ids) -> dict:
    """Content set-diff for 2–4 lists from compact membership shards only."""
    hub = set(hub_ids)
    list_ids = list(memberships)
    by_list = {lid: {row["id"]: row["title"] for row in memberships[lid]} for lid in list_ids}
    projects: set[str] = set()
    for titles in by_list.values():
        projects.update(titles)
    result: dict[str, list] = {
        "shared_independent": [],
        "shared_copy_lineage": [],
        "unique_and_not_a_hub": [],
    }
    for lid in list_ids:
        result[f"unique_to_{lid}"] = []
    for pid in sorted(projects):
        citing = [lid for lid in list_ids if pid in by_list[lid]]
        if len(citing) == 1:
            lid = citing[0]
            item = {"id": pid, "title": by_list[lid][pid]}
            result[f"unique_to_{lid}"].append(item)
            if pid not in hub:
                result["unique_and_not_a_hub"].append({"id": pid, "title": item["title"], "list_id": lid})
            continue
        copy_flags = []
        for i, a in enumerate(citing):
            for b in citing[i + 1:]:
                copy_flags.append(is_copy_lineage(by_list[a][pid], by_list[b][pid]))
        item = {"id": pid, "titles": {lid: by_list[lid][pid] for lid in citing}}
        if copy_flags and all(copy_flags):
            result["shared_copy_lineage"].append(item)
        else:
            result["shared_independent"].append(item)
    return result


class LandscapeAccumulator:
    """Stream one project record at a time. Never holds `data/projects/` shards."""

    def __init__(self, list_pairs: list[dict]) -> None:
        self._published_pairs = {frozenset((row["a"], row["b"])) for row in list_pairs}
        self._membership: dict[str, list[dict]] = defaultdict(list)
        self._citing: dict[str, list[str]] = {}
        self._titles: dict[tuple[str, str], str] = {}
        self._pair_items: dict[frozenset, list[dict]] = defaultdict(list)

    def add_project(self, record: dict) -> None:
        by_list: dict[str, dict] = {}
        for occurrence in record["occurrences"]:
            by_list.setdefault(occurrence["list_id"], occurrence)
        list_ids = sorted(by_list)
        pid = record["id"]
        self._citing[pid] = list_ids
        for list_id in list_ids:
            title = by_list[list_id]["title"]
            self._titles[(list_id, pid)] = title
            self._membership[list_id].append({"id": pid, "title": title})
        for i, a in enumerate(list_ids):
            for b in list_ids[i + 1:]:
                key = frozenset((a, b))
                if key not in self._published_pairs:
                    continue
                a_title, b_title = by_list[a]["title"], by_list[b]["title"]
                self._pair_items[key].append({
                    "id": pid,
                    "title_a": a_title if a < b else b_title,
                    "title_b": b_title if a < b else a_title,
                    "copy_lineage": is_copy_lineage(a_title, b_title),
                })

    def finalize(self, network: dict, layout: dict, eligible_ids: list[str], generated_at: str) -> dict:
        hub_ids = [row["id"] for row in network.get("hub_projects", [])]
        hub_set = set(hub_ids)
        near_dup: dict[str, set[str]] = defaultdict(set)
        for row in network.get("list_pairs", []):
            if row.get("near_duplicate"):
                near_dup[row["a"]].add(row["b"])
                near_dup[row["b"]].add(row["a"])
        coords = layout["coords"]
        communities = layout["communities"]
        lists_out = []
        shard_lists: dict[str, list[dict]] = defaultdict(list)
        for list_id in sorted(eligible_ids):
            membership = sorted(self._membership.get(list_id, []), key=lambda r: (r["title"].casefold(), r["id"]))
            project_ids = [row["id"] for row in membership]
            unique = family = shared = hub = 0
            for pid in project_ids:
                others = [lid for lid in self._citing.get(pid, []) if lid != list_id]
                if pid in hub_set:
                    hub += 1
                elif not others:
                    unique += 1
                elif all(other in near_dup[list_id] for other in others):
                    family += 1
                else:
                    shared += 1
            if unique + family + shared + hub != len(project_ids):
                raise ValueError("Signature buckets do not sum to distinct-project total")
            x, y = coords[list_id]
            community_id = communities[list_id]
            lists_out.append({
                "id": list_id, "x": x, "y": y, "community_id": community_id,
                "unique": unique, "family": family, "shared": shared, "hub": hub,
            })
            neighbor_rows = neighbors_of(network.get("list_pairs", []), list_id, limit=NEIGHBOR_LIMIT)
            previews = []
            for row in neighbor_rows:
                neighbor = row["neighbor"]
                key = frozenset((list_id, neighbor))
                items = sorted(self._pair_items.get(key, []), key=lambda r: (r["id"], r["title_a"]))
                independent = [item for item in items if not item["copy_lineage"]]
                copies = [item for item in items if item["copy_lineage"]]
                previews.append({
                    "neighbor": neighbor,
                    "independent": _cap_preview(independent, list_id, neighbor),
                    "copy_lineage": _cap_preview(copies, list_id, neighbor),
                    "truncated": len(independent) > PREVIEW_LIMIT or len(copies) > PREVIEW_LIMIT,
                    "total": len(items),
                })
            shard_lists[list_shard_prefix(list_id)].append({
                "id": list_id,
                "membership": membership,
                "neighbor_previews": previews,
            })
        shards = {}
        shard_digests = {}
        for prefix, records in sorted(shard_lists.items()):
            shard = {
                "format_version": FORMAT, "prefix": prefix,
                "lists": sorted(records, key=lambda r: r["id"]),
            }
            shard["digest"] = digest(shard)
            shards[prefix] = shard
            shard_digests[prefix] = shard["digest"]
        data = {
            "format_version": FORMAT,
            "generated_at": generated_at,
            "source_network_digest": network["digest"],
            "source_project_digest": network["source_project_digest"],
            "content_policy": CONTENT_POLICY,
            "layout": layout["method"],
            "communities": layout["community_meta"],
            "hub_ids": hub_ids,
            "counts": {
                "lists": len(lists_out),
                "shards": len(shard_digests),
                "communities": len({row["community_id"] for row in lists_out}),
                "isolated": layout["community_meta"].get("isolated", 0),
            },
            "lists": lists_out,
            "shards": shard_digests,
        }
        data["digest"] = digest({k: v for k, v in data.items() if k != "digest"})
        return {"index": data, "shards": shards}


def _cap_preview(items: list[dict], list_id: str, neighbor: str) -> list[dict]:
    a, b = (list_id, neighbor) if list_id < neighbor else (neighbor, list_id)
    out = []
    for item in items[:PREVIEW_LIMIT]:
        out.append({
            "id": item["id"],
            "title": item["title_a"] if list_id == a else item["title_b"],
            "neighbor_title": item["title_b"] if list_id == a else item["title_a"],
        })
    return out


def validate_landscape(data: dict, network: dict, project_index: dict, shards: dict | None = None) -> None:
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported landscape artifact format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Landscape artifact digest mismatch")
    if data.get("source_network_digest") != network.get("digest"):
        raise ValueError("Landscape artifact does not match the published network index")
    if data.get("source_project_digest") != project_index.get("digest"):
        raise ValueError("Landscape artifact does not match the published project index")
    if data.get("source_project_digest") != network.get("source_project_digest"):
        raise ValueError("Landscape source_project_digest does not match the network artifact")
    lists = data.get("lists")
    if not isinstance(lists, list):
        raise ValueError("Invalid landscape lists")
    seen = set()
    for row in lists:
        lid = row.get("id")
        if not lid or lid in seen:
            raise ValueError("Invalid landscape list identity")
        seen.add(lid)
        for key in ("unique", "family", "shared", "hub"):
            if not isinstance(row.get(key), int) or row[key] < 0:
                raise ValueError("Invalid signature count")
        if not isinstance(row.get("x"), (int, float)) or not isinstance(row.get("y"), (int, float)):
            raise ValueError("Invalid landscape coordinates")
        if not row.get("community_id"):
            raise ValueError("Missing community_id")
    counts = data.get("counts", {})
    if counts.get("lists") != len(lists):
        raise ValueError("Landscape counts do not reconcile")
    shard_map = data.get("shards")
    if not isinstance(shard_map, dict):
        raise ValueError("Invalid landscape shard map")
    if counts.get("shards") != len(shard_map):
        raise ValueError("Landscape shard counts do not reconcile")
    if shards is None:
        return
    if set(shards) != set(shard_map):
        raise ValueError("Landscape shard set does not match the index")
    listed_ids = {row["id"] for row in lists}
    shard_ids = set()
    for prefix, shard in shards.items():
        if shard.get("prefix") != prefix:
            raise ValueError("Landscape shard prefix mismatch")
        if shard.get("digest") != shard_map[prefix]:
            raise ValueError("Landscape shard digest does not match the index")
        if shard.get("digest") != digest({k: v for k, v in shard.items() if k != "digest"}):
            raise ValueError("Landscape shard digest mismatch")
        if shard.get("format_version") != FORMAT:
            raise ValueError("Unsupported landscape shard format")
        for record in shard.get("lists", []):
            lid = record["id"]
            if list_shard_prefix(lid) != prefix:
                raise ValueError("Landscape list is in the wrong shard")
            if lid in shard_ids:
                raise ValueError("Duplicate landscape list in shards")
            shard_ids.add(lid)
            membership = record.get("membership")
            if not isinstance(membership, list):
                raise ValueError("Invalid membership")
            index_row = next(row for row in lists if row["id"] == lid)
            total = index_row["unique"] + index_row["family"] + index_row["shared"] + index_row["hub"]
            if total != len(membership):
                raise ValueError("Signature counts do not match membership")
            for preview in record.get("neighbor_previews", []):
                if preview.get("total", 0) < 0:
                    raise ValueError("Invalid neighbor preview")
                shown = len(preview.get("independent", [])) + len(preview.get("copy_lineage", []))
                if preview.get("truncated") is False and shown != preview.get("total"):
                    raise ValueError("Preview truncated flag does not reconcile")
    if shard_ids != listed_ids:
        raise ValueError("Landscape shards do not cover every indexed list")


UNKNOWN_POINT_SIZE = 12
SIGNATURE_CAPTION = "composition of citations, not quality"


def scatter_rows(landscape_lists: list[dict], list_index: dict, color_mode: str = "community") -> list[dict]:
    by_id = {item["id"]: item for item in list_index.get("lists", [])}
    rows = []
    for row in landscape_lists:
        item = by_id.get(row["id"], {})
        entries = item.get("entry_count")
        size = UNKNOWN_POINT_SIZE if entries is None else entries
        topic = (item.get("topics") or ["Other"])[0]
        color = row["community_id"] if color_mode == "community" else topic
        rows.append({
            "id": row["id"],
            "name": item.get("name", row["id"]),
            "x": row["x"],
            "y": row["y"],
            "color": color,
            "size": size,
            "entry_count": entries,
            "community_id": row["community_id"],
            "topic": topic,
            "unique": row["unique"],
            "family": row["family"],
            "shared": row["shared"],
            "hub": row["hub"],
        })
    return rows


def scatter_spec(rows: list[dict], color_title: str = "community"):
    import altair as alt
    data = rows
    return (
        alt.Chart(alt.Data(values=data))
        .mark_circle(opacity=0.75)
        .encode(
            x=alt.X("x:Q", title=None, axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y("y:Q", title=None, axis=alt.Axis(labels=False, ticks=False)),
            color=alt.Color("color:N", title=color_title),
            size=alt.Size("size:Q", title="Indexed entries"),
            tooltip=["name:N", "id:N", "topic:N", "community_id:N"],
        )
        .properties(height=480)
        .interactive()
    )


def signature_stack(row: dict) -> list[dict]:
    return [
        {"Part": "Unique", "Projects": row["unique"]},
        {"Part": "Family", "Projects": row["family"]},
        {"Part": "Shared", "Projects": row["shared"]},
        {"Part": "Hub", "Projects": row["hub"]},
    ]


def neighbors_filtered(list_pairs: list[dict], list_id: str, hide_clones: bool, limit: int = 15) -> list[dict]:
    rows = neighbors_of(list_pairs, list_id, limit=limit * 4 if hide_clones else limit)
    if hide_clones:
        rows = [row for row in rows if not row.get("near_duplicate")]
    return rows[:limit]


def edge_inspector_rows(preview: dict) -> list[dict]:
    rows = []
    for item in preview.get("independent", []):
        rows.append({"Project": item["title"], "This list": item["title"],
                     "Neighbor list": item.get("neighbor_title", ""), "Kind": "independent"})
    for item in preview.get("copy_lineage", []):
        rows.append({"Project": item["title"], "This list": item["title"],
                     "Neighbor list": item.get("neighbor_title", ""), "Kind": "copy-lineage"})
    return rows


def set_diff_rows(memberships: dict[str, list[dict]], hub_ids, names: dict[str, str] | None = None) -> list[dict]:
    names = names or {}
    diff = set_diff(memberships, hub_ids)
    rows = []
    for item in diff["shared_independent"]:
        rows.append({"Bucket": "shared_independent", "Project": next(iter(item["titles"].values())),
                     "Id": item["id"]})
    for item in diff["shared_copy_lineage"]:
        rows.append({"Bucket": "shared_copy_lineage", "Project": next(iter(item["titles"].values())),
                     "Id": item["id"]})
    for key, items in diff.items():
        if not key.startswith("unique_to_"):
            continue
        lid = key[len("unique_to_"):]
        label = names.get(lid, lid)
        for item in items:
            rows.append({"Bucket": f"unique_to_{label}", "Project": item["title"], "Id": item["id"]})
    for item in diff["unique_and_not_a_hub"]:
        rows.append({"Bucket": "unique_and_not_a_hub", "Project": item["title"], "Id": item["id"]})
    return rows
