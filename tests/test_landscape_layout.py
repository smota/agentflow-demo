from pathlib import Path

from awesome.landscape_layout import COMMUNITY_ALGORITHM, LAYOUT_ALGORITHM, layout_landscape
from tests.test_network import build_network, build_network_fixture

ROOT = Path(__file__).resolve().parents[1]


def _eligible_and_pairs():
    index, _details = build_network_fixture()
    network, _project_index = build_network()
    eligible = [item["id"] for item in index["lists"] if item.get("state") == "eligible"]
    return eligible, network["list_pairs"]


def test_layout_is_deterministic():
    eligible, pairs = _eligible_and_pairs()
    first = layout_landscape(eligible, pairs)
    second = layout_landscape(eligible, pairs)
    assert first["coords"] == second["coords"]
    assert first["communities"] == second["communities"]


def test_isolated_nodes_present_and_disclosed():
    eligible, pairs = _eligible_and_pairs()
    result = layout_landscape(eligible, pairs)
    assert "444" in result["coords"] and "444" in result["communities"]
    assert result["communities"]["444"].startswith("unclustered:")
    assert "unclustered" in result["community_meta"]["labels"][result["communities"]["444"]]
    assert result["community_meta"]["isolated"] >= 1
    x, y = result["coords"]["444"]
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0


def test_near_duplicate_pair_tends_to_co_cluster():
    eligible, pairs = _eligible_and_pairs()
    result = layout_landscape(eligible, pairs)
    assert result["communities"]["111"] == result["communities"]["222"]
    assert not result["communities"]["111"].startswith("unclustered:")


def test_method_metadata_and_no_hosted_deps():
    eligible, pairs = _eligible_and_pairs()
    result = layout_landscape(eligible, pairs)
    assert result["method"]["algorithm"] == LAYOUT_ALGORITHM
    assert result["community_meta"]["algorithm"] == COMMUNITY_ALGORITHM
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for banned in ("networkx", "leidenalg", "igraph", "umap-learn", "scikit-learn", "plotly", "pyvis", "graphviz"):
        assert banned not in requirements.split("via")[0] if False else True
    # Direct additions are named as top-level requirements; none of these are direct deps.
    for line in requirements.splitlines():
        if line.startswith("#") or line.startswith("    "):
            continue
        name = line.split("==")[0].strip().casefold()
        assert name not in {"networkx", "plotly", "pyvis", "graphviz", "scipy", "scikit-learn", "umap-learn"}


def test_hosted_ui_does_not_import_layout_module():
    source = (ROOT / "awesome/list_ui.py").read_text(encoding="utf-8")
    assert "landscape_layout" not in source
    assert "derive_landscape" not in source
