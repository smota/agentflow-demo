"""Shared copy-lineage detection heuristics, reused (not reinvented) from the A2 cross-list
co-occurrence validation spike (issue #65: "validate cross-list co-occurrence as a
curation-independence signal").

#65 found that raw cross-list citation count is predominantly copy-lineage (same-owner, forked, or
templated sibling lists), not independent curator judgment: 90% of a 60-project sample. Its method
compared every pair of citing lists' own parsed entry text using three signals: title-text
similarity (`difflib.SequenceMatcher` on normalized titles), category-label agreement, and an
explicit `source_data_links` attribution from one list's README to another. `title_similarity` was
the signal that actually classified nearly every case in the sample; `explicit_source_link` fired
0/60 times even though the mechanism exists (see #65's "Disclosed limitations").

This module extracts the validated title-similarity thresholds and comparison logic into a shared,
importable form so both the original spike tool (`tools/analyze_cooccurrence.py`, which still runs
the complete three-signal method against a sample for future re-validation) and the new full-corpus
offline derivation (`awesome/search_index.py`, `tools/derive_search_index.py`, built for A3's
redesigned "independent citation count" secondary signal) use the exact same classification rule --
never two silently-drifting copies of the same heuristic.

Deliberate, disclosed scope decision for the full-corpus run: `independent_clusters`/
`independent_count` below use ONLY the title-similarity signal, not `explicit_source_link`. The
explicit-source-link check requires loading every eligible list's full detail shard (539 MB across
~thousands of lists) for a signal that fired zero times in #65's validation sample -- a low-yield,
high-cost check at 932,511-project scale. Omitting it here is a documented simplification, not a
silent one; it does not change the validated threshold values or the sampled spike tool's own
complete method.
"""
from __future__ import annotations

import difflib
import re

# Same thresholds #65 validated (see its "Finding": 90/10 copy-lineage/independent split, stable
# under a title-length control). Do not drift these without re-running the validation sample.
COPY_THRESHOLD = 0.92
INDEPENDENT_THRESHOLD = 0.60


def normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def is_copy_lineage(a_title: str, b_title: str) -> bool:
    return title_similarity(a_title, b_title) >= COPY_THRESHOLD


def independent_clusters(occurrences: list[dict]) -> list[list[str]]:
    """Union-find clustering of an `awesome.projects` project record's occurrences into
    independence clusters: any two DIFFERENT citing lists whose own entry titles for this project
    are near-identical (>= COPY_THRESHOLD) are treated as one sibling/copy-lineage source, not two
    independent citations -- e.g. #65's own examples, same-owner sibling lists
    (`uhub/awesome-c` + `uhub/awesome-cpp`) or forked/derivative pairs. Occurrences from the SAME
    list are never compared or clustered separately here; `awesome.projects.derive_projects`
    already collapses same-list repeats into a single distinct list_id, which is what this function
    clusters over.

    Returns one list of list_names per cluster (order not significant; callers needing a stable
    order should sort). An empty or single-list `occurrences` list returns clusters of size <= 1.
    """
    by_list: dict[str, dict] = {}
    for occurrence in occurrences:
        by_list.setdefault(occurrence["list_id"], occurrence)
    list_ids = list(by_list)
    parent = {list_id: list_id for list_id in list_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(list_ids)):
        for j in range(i + 1, len(list_ids)):
            a, b = list_ids[i], list_ids[j]
            if is_copy_lineage(by_list[a]["title"], by_list[b]["title"]):
                union(a, b)

    clusters: dict[str, list[str]] = {}
    for list_id in list_ids:
        clusters.setdefault(find(list_id), []).append(by_list[list_id]["list_name"])
    return list(clusters.values())


def independent_count(occurrences: list[dict]) -> int:
    """The copy-lineage-discounted citation count: the number of independence clusters, never the
    raw distinct-list count. For a single distinct citing list this is trivially 1 (or 0 for no
    occurrences) with no clustering needed."""
    distinct_lists = {o["list_id"] for o in occurrences}
    if len(distinct_lists) <= 1:
        return len(distinct_lists)
    return len(independent_clusters(occurrences))
