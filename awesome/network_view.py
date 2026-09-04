"""Pure layout and rendering helpers for D3's opt-in secondary network view (issue #50). No
Streamlit imports here -- `awesome/list_ui.py` is the only module that talks to `st`, matching this
codebase's existing split between pure logic modules (`insights.py`, `explore.py`,
`project_search.py`) and the Streamlit rendering layer.

**Why this is a filtered-neighborhood view, not a whole-catalogue graph.** The real catalogue has
6,377 eligible lists; a naive force-directed layout of the whole list<->list similarity graph in the
browser was measured (see `tests/test_network_view.py`'s explicit performance test, and the
Tester role-pass notes for issue #50/D3) to be exactly the kind of thing that hangs a browser tab at
that scale. Rather than ship that, this module renders only one selected list's bounded neighborhood
(`awesome.network.neighbor_graph`, capped at `NEIGHBOR_LIMIT` neighbors) -- consistent with the
epic's own instruction to scope down and document the constraint honestly rather than ship something
that does not actually work at real scale.

**Why a hand-rolled layout instead of a graph/plotting library.** This product deliberately carries a
minimal dependency footprint (see `requirements.txt`: Streamlit, pandas, altair and their own
transitive deps only -- no networkx, plotly, or system Graphviz binary). Adding one of those just for
a ~16-node illustrative graph was not judged worth the new dependency surface. `layout_positions`
below is a small, deterministic Fruchterman-Reingold-style force-directed layout with a fixed,
bounded iteration count over a bounded node count -- fast and predictable by construction (see the
timing assertion in `tests/test_network_view.py`) -- and `render_svg` emits plain inline SVG,
rendered via `st.html` the same way `awesome/list_ui.py` already renders `identity_footer()`.
"""
from __future__ import annotations

import html
import math

NEIGHBOR_LIMIT = 15
CANVAS_WIDTH = 640
CANVAS_HEIGHT = 440
_ITERATIONS = 60


def layout_positions(node_ids: list[str], edges: list[dict], center_id: str,
                      width: float = CANVAS_WIDTH, height: float = CANVAS_HEIGHT,
                      iterations: int = _ITERATIONS) -> dict[str, tuple[float, float]]:
    """Deterministic force-directed layout, `center_id` pinned at the canvas center so the selected
    list stays visually central regardless of how the other nodes settle. Deterministic circular
    initial placement (no randomness) keeps this reproducible for tests. Bounded by construction:
    callers keep `node_ids` small (`awesome.network.neighbor_graph`'s `limit`), and `iterations` is
    fixed, so cost is O(iterations * (nodes^2 + edges)) over a small, capped `nodes` -- never
    proportional to the whole catalogue."""
    others = [node for node in node_ids if node != center_id]
    positions: dict[str, tuple[float, float]] = {center_id: (width / 2, height / 2)}
    radius = min(width, height) * 0.42
    for i, node in enumerate(others):
        angle = 2 * math.pi * i / max(1, len(others))
        positions[node] = (width / 2 + radius * math.cos(angle), height / 2 + radius * math.sin(angle))
    if len(others) < 2:
        return positions

    area = width * height
    k = math.sqrt(area / max(1, len(node_ids)))
    temperature = width / 10
    cooling = temperature / (iterations + 1)
    relevant_edges = [edge for edge in edges if edge["a"] in positions and edge["b"] in positions]

    for _ in range(iterations):
        disp = {node: [0.0, 0.0] for node in others}
        for i in range(len(others)):
            for j in range(i + 1, len(others)):
                a, b = others[i], others[j]
                dx = positions[a][0] - positions[b][0]
                dy = positions[a][1] - positions[b][1]
                dist = max(0.01, math.hypot(dx, dy))
                force = k * k / dist
                disp[a][0] += dx / dist * force
                disp[a][1] += dy / dist * force
                disp[b][0] -= dx / dist * force
                disp[b][1] -= dy / dist * force
        for edge in relevant_edges:
            a, b = edge["a"], edge["b"]
            dx = positions[a][0] - positions[b][0]
            dy = positions[a][1] - positions[b][1]
            dist = max(0.01, math.hypot(dx, dy))
            force = dist * dist / k
            fx, fy = dx / dist * force, dy / dist * force
            if a in disp:
                disp[a][0] -= fx
                disp[a][1] -= fy
            if b in disp:
                disp[b][0] += fx
                disp[b][1] += fy
        for node in others:
            dx, dy = disp[node]
            dist = max(0.01, math.hypot(dx, dy))
            limited = min(dist, temperature)
            x, y = positions[node]
            x += dx / dist * limited
            y += dy / dist * limited
            x = min(width - 24, max(24, x))
            y = min(height - 24, max(24, y))
            positions[node] = (x, y)
        temperature = max(1.0, temperature - cooling)
    return positions


def render_svg(graph: dict, positions: dict[str, tuple[float, float]], labels: dict[str, str],
               width: float = CANVAS_WIDTH, height: float = CANVAS_HEIGHT) -> str:
    """Render `graph` (`awesome.network.neighbor_graph`'s output) as inline SVG. `labels` maps list
    id -> display name (callers resolve this from the already-loaded list index; this module never
    looks up list identity itself). Escapes every label; never trusts `labels` values as safe HTML."""
    center_id = graph["center"]
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
             f'role="img" aria-label="Network neighborhood of {html.escape(labels.get(center_id, center_id))}">']
    for edge in graph["edges"]:
        a, b = edge["a"], edge["b"]
        if a not in positions or b not in positions:
            continue
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        stroke = "#bd7210" if edge["near_duplicate"] else "#9fb8b2"
        stroke_width = 1 + min(3.0, edge["jaccard"] * 4)
        dash = ' stroke-dasharray="4 2"' if edge["near_duplicate"] else ""
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{stroke}" stroke-width="{stroke_width:.2f}"{dash} opacity="0.85"/>')
    for node_id in graph["nodes"]:
        if node_id not in positions:
            continue
        x, y = positions[node_id]
        is_center = node_id == center_id
        radius = 16 if is_center else 10
        fill = "#087f73" if is_center else "#ffffff"
        stroke = "#173c35" if is_center else "#087f73"
        text_color = "#ffffff" if is_center else "#173c35"
        label = labels.get(node_id, node_id)
        short = label if len(label) <= 22 else label[:21] + "…"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" '
                     f'stroke="{stroke}" stroke-width="2"/>')
        text_y = y + radius + 12
        parts.append(f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="9" text-anchor="middle" '
                     f'fill="{text_color}" font-family="sans-serif">{"★" if is_center else ""}</text>')
        parts.append(f'<text x="{x:.1f}" y="{text_y:.1f}" font-size="10" text-anchor="middle" '
                     f'fill="#173c35" font-family="sans-serif">{html.escape(short)}</text>')
    parts.append("</svg>")
    return "".join(parts)
