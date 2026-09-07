"""Deterministic offline 2D coordinates and Louvain communities for the landscape map.

Never imported by the hosted UI. numpy.linalg.eigh only (numpy is already a hosted
transitive dependency). Isolated lists — no qualifying published pair — still receive
coordinates (hash of list_id) and a disclosed singleton/unclustered community_id.
Communities are a coloring lens / candidate clustering (issue #86), never an ontology
or a quality score, and they do not replace list topics.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

RESOLUTION = 1.0
LAYOUT_ALGORITHM = "normalized-laplacian-spectral"
COMMUNITY_ALGORITHM = "louvain"


def layout_landscape(eligible_ids: list[str], list_pairs: list[dict]) -> dict:
    nodes = sorted(eligible_ids)
    edges = []
    connected: set[str] = set()
    for row in list_pairs:
        a, b = row["a"], row["b"]
        if a not in set(nodes) or b not in set(nodes) or a == b:
            continue
        lo, hi = (a, b) if a < b else (b, a)
        edges.append((lo, hi, float(row["jaccard"])))
        connected.add(a)
        connected.add(b)
    edges.sort(key=lambda e: (e[0], e[1]))
    coords = _spectral_coords(nodes, edges, connected)
    raw_communities = _louvain(nodes, edges, connected)
    communities = {}
    labels = {}
    clustered = []
    isolated = 0
    for node in nodes:
        if node not in connected:
            cid = f"unclustered:{node}"
            communities[node] = cid
            labels[cid] = "unclustered (no qualifying pair)"
            isolated += 1
        else:
            clustered.append(node)
    cluster_ids = sorted({raw_communities[n] for n in clustered})
    remap = {old: f"c{i}" for i, old in enumerate(cluster_ids)}
    for node in clustered:
        cid = remap[raw_communities[node]]
        communities[node] = cid
        labels.setdefault(cid, f"candidate cluster {cid[1:]}")
    return {
        "coords": coords,
        "communities": communities,
        "method": {
            "algorithm": LAYOUT_ALGORITHM,
            "eigenvectors": [1, 2],
            "isolated_placement": "sha256(list_id)",
        },
        "community_meta": {
            "algorithm": COMMUNITY_ALGORITHM,
            "resolution": RESOLUTION,
            "labels": labels,
            "isolated": isolated,
        },
    }


def _hash_point(list_id: str) -> tuple[float, float]:
    digest = hashlib.sha256(list_id.encode()).digest()
    x = int.from_bytes(digest[:8], "big") / 2**64
    y = int.from_bytes(digest[8:16], "big") / 2**64
    return (0.88 + 0.11 * x, 0.88 + 0.11 * y)


def _spectral_coords(nodes: list[str], edges: list[tuple[str, str, float]], connected: set[str]) -> dict:
    coords = {node: _hash_point(node) for node in nodes if node not in connected}
    active = [node for node in nodes if node in connected]
    if len(active) == 1:
        coords[active[0]] = (0.5, 0.5)
        return coords
    if len(active) == 2:
        coords[active[0]] = (0.2, 0.5)
        coords[active[1]] = (0.8, 0.5)
        return coords
    if not active:
        return coords
    index = {node: i for i, node in enumerate(active)}
    n = len(active)
    adjacency = np.zeros((n, n), dtype=np.float64)
    for a, b, weight in edges:
        i, j = index[a], index[b]
        adjacency[i, j] = weight
        adjacency[j, i] = weight
    degree = adjacency.sum(axis=1)
    scale = np.diag(1.0 / np.sqrt(np.maximum(degree, 1e-12)))
    laplacian = np.eye(n) - scale @ adjacency @ scale
    _evals, evecs = np.linalg.eigh(laplacian)
    xy = np.array(evecs[:, 1:3], copy=True)
    for axis in range(min(2, xy.shape[1])):
        if xy[0, axis] < 0:
            xy[:, axis] *= -1
        lo, hi = float(xy[:, axis].min()), float(xy[:, axis].max())
        if hi > lo:
            xy[:, axis] = (xy[:, axis] - lo) / (hi - lo)
        else:
            xy[:, axis] = 0.5
    if xy.shape[1] == 1:
        xy = np.column_stack([xy[:, 0], np.full(n, 0.5)])
    for i, node in enumerate(active):
        coords[node] = (float(xy[i, 0]) * 0.82 + 0.04, float(xy[i, 1]) * 0.82 + 0.04)
    return coords


def _louvain(nodes: list[str], edges: list[tuple[str, str, float]], connected: set[str]) -> dict[str, int]:
    active = [node for node in nodes if node in connected]
    community = {node: i for i, node in enumerate(active)}
    if len(active) < 2:
        return community
    weights: dict[tuple[str, str], float] = {}
    neighbors: dict[str, set[str]] = defaultdict(set)
    for a, b, weight in edges:
        weights[(a, b)] = weight
        weights[(b, a)] = weight
        neighbors[a].add(b)
        neighbors[b].add(a)
    m = sum(weight for (a, b), weight in weights.items() if a < b)
    if m <= 0:
        return community
    strength = {node: sum(weights[(node, other)] for other in neighbors[node]) for node in active}

    def tot_and_inner(comm: int, node: str) -> tuple[float, float]:
        members = [n for n in active if community[n] == comm]
        tot = sum(strength[n] for n in members)
        inner = 0.0
        for other in neighbors[node]:
            if community[other] == comm:
                inner += weights[(node, other)]
        return tot, inner

    moved = True
    while moved:
        moved = False
        for node in active:
            current = community[node]
            best = current
            best_gain = 0.0
            tot_cur, k_in_cur = tot_and_inner(current, node)
            remove_gain = k_in_cur / m - RESOLUTION * strength[node] * (tot_cur - strength[node]) / (2 * m * m)
            seen = set()
            for other in sorted(neighbors[node]):
                target = community[other]
                if target in seen or target == current:
                    continue
                seen.add(target)
                tot_t, k_in_t = tot_and_inner(target, node)
                gain = (k_in_t / m - RESOLUTION * strength[node] * tot_t / (2 * m * m)) - remove_gain
                if gain > best_gain + 1e-15 or (abs(gain - best_gain) <= 1e-15 and target < best):
                    best_gain = gain
                    best = target
            if best != current:
                community[node] = best
                moved = True
    compact = {}
    next_id = 0
    assigned = {}
    for node in active:
        old = community[node]
        if old not in assigned:
            assigned[old] = next_id
            next_id += 1
        compact[node] = assigned[old]
    return compact
