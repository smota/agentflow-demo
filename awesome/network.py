"""Pure derivation and validation of the offline list<->project network exploration artifact
(D1, issue #50's secondary network exploration epic). No networking or runtime writes.

Built directly on top of A1's project<->list dedup structure (`awesome.projects`,
`data/project-index.json` + `data/projects/<prefix>.json`) and reuses #65's validated
title-similarity copy-lineage heuristic (`awesome.copy_lineage`) for both signals this module
derives -- never a second, silently-drifting copy of that classification rule:

- **Hub projects**: the `independent_list_count`-discounted top-cited projects (the same
  copy-lineage-discounted count `awesome.search_index` already publishes per project, reused here
  and ranked), so a project that looks like a "hub" only because several same-owner/forked sibling
  lists cite it under near-identical wording does not outrank a project genuinely cited by that many
  independently-curated lists. `hub_discount` (`list_count - independent_list_count`) is reported
  alongside so the discount itself stays a disclosed, inspectable fact, not a hidden adjustment.
- **List-to-list similarity / near-duplicate detection**: for every pair of eligible lists that cite
  at least `MIN_SHARED_PROJECTS` of the same canonical project URLs, a Jaccard similarity over their
  own distinct-project sets plus a `copy_fraction` -- the share of those SAME shared projects whose
  per-list occurrence titles classify as copy-lineage between that specific pair (reusing
  `awesome.copy_lineage.is_copy_lineage`, not a separate metric). A pair is flagged
  `near_duplicate` only when both the overlap is large (`jaccard >= NEAR_DUP_JACCARD`) AND most of
  that overlap is copy-lineage text (`copy_fraction >= NEAR_DUP_COPY_FRACTION`) -- high overlap
  alone is not sufficient (two large, unrelated "awesome-X" lists can share many popular hub
  projects while wording every entry independently), and high copy-fraction alone is not sufficient
  either (two lists sharing only two or three near-identically-worded entries is not evidence of
  list-level duplication).

Every number here traces to an observed fact already published by A1 (occurrences, titles, distinct
citing lists) -- there is no invented quality/trust score, consistent with the rest of this product
(see `awesome.projects.CONTENT_POLICY`, `awesome.search_index.CONTENT_POLICY`).

Threshold provenance (see `tools/derive_network.py`'s module docstring for the exact measurement
run against the real catalogue that grounded these numbers, issue #50 D1):

- `MIN_SHARED_PROJECTS = 5`: at the real catalogue's scale (6,377 eligible lists, 932,511 deduped
  projects), 229,981 distinct list pairs share at least one project, but the overwhelming majority
  of that is two large lists both coincidentally citing the same handful of extremely popular hub
  projects (e.g. "awesome", "Visual Studio Code") -- not a real curation-overlap signal. Requiring
  at least 5 shared projects keeps 32,820 pairs (about 14% of the shared>=1 population) while
  discarding that coincidental long tail; this is an evidence-driven cut applied to the observed
  distribution, not an arbitrary round number.
- `NEAR_DUP_JACCARD = 0.5` / `NEAR_DUP_COPY_FRACTION = 0.6`: at `MIN_SHARED_PROJECTS >= 5`, only 135
  pairs reach `jaccard >= 0.5` at all -- genuine near-total overlap is rare, so it is a meaningfully
  selective cut rather than one that would flag a large share of the catalogue. `>= 0.6` copy
  fraction requires most (not merely some) of that shared overlap to be copy-lineage text before a
  pair is called a near-duplicate, matching #65's own `COPY_THRESHOLD`-based classification
  discipline of requiring the dominant pattern, not an isolated match.
"""
from __future__ import annotations

import heapq

from awesome.catalogue import digest
from awesome.copy_lineage import independent_count, is_copy_lineage

FORMAT = 1

HUB_LIMIT = 100
MIN_HUB_LIST_COUNT = 2
MIN_SHARED_PROJECTS = 5
NEAR_DUP_JACCARD = 0.5
NEAR_DUP_COPY_FRACTION = 0.6

CONTENT_POLICY = (
    "hub_projects are the top "
    f"{HUB_LIMIT} projects by independent_list_count (the copy-lineage-discounted citation count "
    "already used by awesome/search_index.py, issue #65's validated heuristic) among projects cited "
    f"by at least {MIN_HUB_LIST_COUNT} distinct eligible lists; hub_discount is list_count minus "
    "independent_list_count, an observed fact about how much of the raw citation count was "
    "copy-lineage, never a hidden adjustment. list_pairs cover eligible-list pairs sharing at least "
    f"{MIN_SHARED_PROJECTS} distinct cited projects (a threshold chosen from the observed shared-pair "
    "distribution to exclude coincidental overlap on a handful of extremely popular hub projects, "
    "see awesome/network.py); jaccard is shared / (unique projects in A + unique projects in B - "
    "shared); copy_fraction is the share of that SAME shared set whose per-list occurrence titles "
    "classify as copy-lineage between that pair; near_duplicate requires both jaccard and "
    "copy_fraction to clear their own disclosed thresholds. None of these numbers are a quality, "
    "trust, or authority score -- see issue #65 and #50 for the full methodology."
)


def distinct_occurrences_by_list(occurrences: list[dict]) -> dict[str, dict]:
    """Collapse a project record's occurrences to one per distinct citing list, keeping the first
    occurrence seen per list -- the same collapse `awesome.copy_lineage.independent_clusters`
    performs, reused here so both modules treat repeated same-list citations identically."""
    by_list: dict[str, dict] = {}
    for occurrence in occurrences:
        by_list.setdefault(occurrence["list_id"], occurrence)
    return by_list


class NetworkAccumulator:
    """Streaming accumulator over the project corpus, one already-validated project record at a
    time -- mirrors `tools/derive_search_index.py`'s one-shard-at-a-time discipline so the full
    932,511-project corpus (723 MB across 256 shards as of A1) is never held in memory at once.
    Only the derived counters are kept resident: per-list distinct-project totals, per-pair shared/
    copy-lineage counts, and a size-bounded top-`HUB_LIMIT` heap -- all small relative to the corpus
    even at this catalogue's real scale (6,377 lists, 229,981 interacting list pairs observed)."""

    def __init__(self) -> None:
        self._list_totals: dict[str, int] = {}
        self._pair_shared: dict[tuple[str, str], int] = {}
        self._pair_copy: dict[tuple[str, str], int] = {}
        self._hub_heap: list[tuple[int, int, str, str, str]] = []

    def add_project(self, record: dict) -> None:
        occurrences = record["occurrences"]
        by_list = distinct_occurrences_by_list(occurrences)
        list_ids = sorted(by_list)
        for list_id in list_ids:
            self._list_totals[list_id] = self._list_totals.get(list_id, 0) + 1
        for i in range(len(list_ids)):
            for j in range(i + 1, len(list_ids)):
                a, b = list_ids[i], list_ids[j]
                key = (a, b)
                self._pair_shared[key] = self._pair_shared.get(key, 0) + 1
                if is_copy_lineage(by_list[a]["title"], by_list[b]["title"]):
                    self._pair_copy[key] = self._pair_copy.get(key, 0) + 1
        if record["list_count"] >= MIN_HUB_LIST_COUNT:
            independent = independent_count(occurrences)
            # Tie-broken by list_count then a stable id-descending order so the size-bounded heap
            # is deterministic; final publication order is re-sorted explicitly in finalize().
            entry = (independent, record["list_count"], record["id"], record["url"], record["title"])
            if len(self._hub_heap) < HUB_LIMIT:
                heapq.heappush(self._hub_heap, entry)
            elif entry > self._hub_heap[0]:
                heapq.heapreplace(self._hub_heap, entry)

    def finalize(self, source_project_digest: str, generated_at: str) -> dict:
        hub_records = [
            {"id": pid, "url": url, "title": title, "list_count": list_count,
             "independent_list_count": independent, "hub_discount": list_count - independent}
            for independent, list_count, pid, url, title in
            sorted(self._hub_heap, key=lambda e: (-e[0], -e[1], e[3]))
        ]
        list_pairs = []
        for (a, b), shared in self._pair_shared.items():
            if shared < MIN_SHARED_PROJECTS:
                continue
            union = self._list_totals[a] + self._list_totals[b] - shared
            jaccard = round(shared / union, 4) if union else 0.0
            copy_fraction = round(self._pair_copy.get((a, b), 0) / shared, 4)
            near_duplicate = jaccard >= NEAR_DUP_JACCARD and copy_fraction >= NEAR_DUP_COPY_FRACTION
            list_pairs.append({"a": a, "b": b, "shared": shared, "jaccard": jaccard,
                                "copy_fraction": copy_fraction, "near_duplicate": near_duplicate})
        list_pairs.sort(key=lambda row: (-row["shared"], row["a"], row["b"]))
        data = {
            "format_version": FORMAT, "source_project_digest": source_project_digest,
            "generated_at": generated_at, "content_policy": CONTENT_POLICY,
            "counts": {"lists": len(self._list_totals), "pairs": len(list_pairs),
                       "hub_projects": len(hub_records),
                       "near_duplicate_pairs": sum(1 for row in list_pairs if row["near_duplicate"])},
            "hub_projects": hub_records, "list_pairs": list_pairs,
        }
        data["digest"] = digest(data)
        return data


def neighbors_of(list_pairs: list[dict], list_id: str, limit: int = 15) -> list[dict]:
    """Directed view of `list_pairs` from one list's perspective for the D3 filtered-neighborhood
    UI: every pair touching `list_id`, ranked by similarity, each carrying an explicit `neighbor`
    id. Never used by the offline pipeline itself -- a small, read-only convenience for callers
    (the Streamlit network view) that already hold the published `list_pairs` array in memory."""
    rows = []
    for pair in list_pairs:
        if pair["a"] == list_id:
            rows.append({**pair, "neighbor": pair["b"]})
        elif pair["b"] == list_id:
            rows.append({**pair, "neighbor": pair["a"]})
    rows.sort(key=lambda row: (-row["jaccard"], -row["shared"], row["neighbor"]))
    return rows[:limit]


def neighbor_graph(list_pairs: list[dict], center_id: str, limit: int = 15) -> dict:
    """D3's bounded-neighborhood graph for one selected list: the center plus up to `limit` of its
    strongest neighbors (`neighbors_of`), PLUS any qualifying edges the published data also has
    directly between two of those neighbors -- so the rendered graph is a genuine small neighborhood
    rather than a pure hub-and-spoke star. Node/edge count is bounded by `limit + 1` nodes and never
    scans more of the catalogue than one linear pass over `list_pairs`; callers own keeping `limit`
    small (the Streamlit view defaults to 15 -- see `awesome/network_view.py`)."""
    top = neighbors_of(list_pairs, center_id, limit=limit)
    node_ids = [center_id] + [row["neighbor"] for row in top]
    node_set = set(node_ids)
    edges = [{"a": center_id, "b": row["neighbor"], "jaccard": row["jaccard"], "shared": row["shared"],
              "copy_fraction": row["copy_fraction"], "near_duplicate": row["near_duplicate"]}
             for row in top]
    seen_pairs = {frozenset((center_id, row["neighbor"])) for row in top}
    for pair_row in list_pairs:
        if pair_row["a"] not in node_set or pair_row["b"] not in node_set:
            continue
        key = frozenset((pair_row["a"], pair_row["b"]))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        edges.append({"a": pair_row["a"], "b": pair_row["b"], "jaccard": pair_row["jaccard"],
                       "shared": pair_row["shared"], "copy_fraction": pair_row["copy_fraction"],
                       "near_duplicate": pair_row["near_duplicate"]})
    return {"center": center_id, "nodes": node_ids, "edges": edges}


def validate_network(data: dict, project_index: dict) -> None:
    """Validate the published network artifact against the project index it was derived from.
    Unsharded (unlike `awesome.projects`/`awesome.search_index`) -- see `tools/derive_network.py`'s
    module docstring for why this artifact's real size does not need shard partitioning."""
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported network artifact format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Network artifact digest mismatch")
    if not data.get("source_project_digest") or data["source_project_digest"] != project_index.get("digest"):
        raise ValueError("Network artifact does not match the published project index")
    hub_projects = data.get("hub_projects")
    if not isinstance(hub_projects, list) or len(hub_projects) > HUB_LIMIT:
        raise ValueError("Invalid hub project list")
    seen_hub_ids: set[str] = set()
    previous_rank: tuple[int, int] | None = None
    for record in hub_projects:
        list_count, independent = record.get("list_count"), record.get("independent_list_count")
        if not isinstance(list_count, int) or list_count < MIN_HUB_LIST_COUNT:
            raise ValueError("Invalid hub project list_count")
        if not isinstance(independent, int) or independent < 1 or independent > list_count:
            raise ValueError("Invalid hub project independent_list_count")
        if record.get("hub_discount") != list_count - independent:
            raise ValueError("Hub discount does not reconcile with list_count/independent_list_count")
        if not record.get("id") or not record.get("url") or not record.get("title"):
            raise ValueError("Incomplete hub project record")
        if record["id"] in seen_hub_ids:
            raise ValueError("Duplicate hub project id")
        seen_hub_ids.add(record["id"])
        rank = (-independent, -list_count)
        if previous_rank is not None and rank < previous_rank:
            raise ValueError("Hub projects are not sorted by independent_list_count")
        previous_rank = rank
    list_pairs = data.get("list_pairs")
    if not isinstance(list_pairs, list):
        raise ValueError("Invalid list_pairs")
    seen_pairs: set[tuple[str, str]] = set()
    near_duplicate_count = 0
    previous_shared: int | None = None
    for row in list_pairs:
        a, b, shared = row.get("a"), row.get("b"), row.get("shared")
        if not a or not b or a == b:
            raise ValueError("Invalid list pair identity")
        if not isinstance(shared, int) or shared < MIN_SHARED_PROJECTS:
            raise ValueError("List pair below the minimum shared-project threshold")
        key = (a, b)
        if key in seen_pairs:
            raise ValueError("Duplicate list pair")
        seen_pairs.add(key)
        jaccard, copy_fraction = row.get("jaccard"), row.get("copy_fraction")
        if not isinstance(jaccard, (int, float)) or not 0 <= jaccard <= 1:
            raise ValueError("Invalid list pair jaccard")
        if not isinstance(copy_fraction, (int, float)) or not 0 <= copy_fraction <= 1:
            raise ValueError("Invalid list pair copy_fraction")
        expected_near_duplicate = jaccard >= NEAR_DUP_JACCARD and copy_fraction >= NEAR_DUP_COPY_FRACTION
        if row.get("near_duplicate") != expected_near_duplicate:
            raise ValueError("near_duplicate flag does not reconcile with its own thresholds")
        if expected_near_duplicate:
            near_duplicate_count += 1
        if previous_shared is not None and shared > previous_shared:
            raise ValueError("List pairs are not sorted by shared count")
        previous_shared = shared
    counts = data.get("counts", {})
    if (counts.get("hub_projects") != len(hub_projects) or counts.get("pairs") != len(list_pairs)
            or counts.get("near_duplicate_pairs") != near_duplicate_count):
        raise ValueError("Network artifact counts do not reconcile")
