import math
import time

from awesome.network import neighbor_graph
from awesome.network_view import CANVAS_HEIGHT, CANVAS_WIDTH, layout_positions, render_svg
from tests.test_network import build_network


def test_layout_pins_center_at_canvas_center():
    network, _ = build_network()
    graph = neighbor_graph(network["list_pairs"], "111", limit=5)
    positions = layout_positions(graph["nodes"], graph["edges"], "111")
    assert positions["111"] == (CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2)


def test_layout_keeps_every_node_within_canvas_bounds():
    network, _ = build_network()
    graph = neighbor_graph(network["list_pairs"], "111", limit=5)
    positions = layout_positions(graph["nodes"], graph["edges"], "111")
    for x, y in positions.values():
        assert 0 <= x <= CANVAS_WIDTH
        assert 0 <= y <= CANVAS_HEIGHT


def test_layout_single_neighbor_places_it_on_the_initial_circle():
    positions = layout_positions(["a", "b"], [], "a", width=100, height=100)
    assert positions["a"] == (50, 50)
    bx, by = positions["b"]
    assert math.isclose(math.hypot(bx - 50, by - 50), 42.0, rel_tol=1e-6)


def test_layout_is_bounded_and_fast_at_the_documented_neighbor_cap():
    """D3's explicit performance constraint: this view is scoped to a bounded neighborhood
    (`awesome.network_view.NEIGHBOR_LIMIT`), never the whole 6,377-list catalogue, precisely because
    a whole-catalogue force-directed layout was too heavy to render responsively. This test proves
    the bounded case stays fast, not just "should be" fast."""
    node_ids = [str(i) for i in range(16)]
    edges = [{"a": node_ids[i], "b": node_ids[j], "jaccard": 0.5} for i in range(16) for j in range(i + 1, 16)]
    start = time.perf_counter()
    positions = layout_positions(node_ids, edges, node_ids[0])
    elapsed = time.perf_counter() - start
    assert len(positions) == 16
    assert elapsed < 1.0  # generous local ceiling; typical runs are well under 50ms


def test_render_svg_escapes_labels_and_marks_near_duplicates():
    network, _ = build_network()
    graph = neighbor_graph(network["list_pairs"], "111", limit=5)
    positions = layout_positions(graph["nodes"], graph["edges"], "111")
    labels = {"111": "owner/awesome-a", "222": '<script>evil</script>', "333": "other/curated-c"}
    svg = render_svg(graph, positions, labels)
    assert svg.startswith("<svg")
    assert "<script>" not in svg  # escaped, not injected raw
    assert "&lt;script&gt;" in svg
    assert 'stroke-dasharray="4 2"' in svg  # the A/B near-duplicate edge is visually distinguished


def test_render_svg_only_draws_edges_with_known_positions():
    network, _ = build_network()
    graph = neighbor_graph(network["list_pairs"], "111", limit=5)
    positions = {"111": (100.0, 100.0)}  # deliberately incomplete
    svg = render_svg(graph, positions, {"111": "owner/awesome-a"})
    assert "<line" not in svg  # no crash, no line drawn to an unknown position
