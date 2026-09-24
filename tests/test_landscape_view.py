from awesome.landscape import (
    SIGNATURE_CAPTION,
    UNKNOWN_POINT_SIZE,
    edge_inspector_rows,
    neighbors_filtered,
    scatter_rows,
    scatter_spec,
    set_diff_rows,
    signature_stack,
)
from tests.test_landscape import build_landscape_artifact
from tests.test_network import build_network, build_network_fixture


def test_hide_clones_drops_near_duplicate_neighbors():
    network, _project_index = build_network()
    shown = neighbors_filtered(network["list_pairs"], "111", hide_clones=False)
    hidden = neighbors_filtered(network["list_pairs"], "111", hide_clones=True)
    assert any(row["neighbor"] == "222" and row["near_duplicate"] for row in shown)
    assert all(row["neighbor"] != "222" for row in hidden)
    assert any(row["neighbor"] == "333" for row in hidden)


def test_signature_stack_sums_to_distinct():
    artifact, _network, _project_index = build_landscape_artifact()
    row = next(item for item in artifact["index"]["lists"] if item["id"] == "111")
    stack = signature_stack(row)
    assert sum(part["Projects"] for part in stack) == row["unique"] + row["family"] + row["shared"] + row["hub"]
    assert SIGNATURE_CAPTION == "composition of citations, not quality"
    assert "quality" in SIGNATURE_CAPTION and "not quality" in SIGNATURE_CAPTION


def test_altair_spec_encodes_color_and_size():
    artifact, _network, _project_index = build_landscape_artifact()
    index, _details = build_network_fixture()
    rows = scatter_rows(artifact["index"]["lists"], index, color_mode="community")
    assert all("color" in row and "size" in row for row in rows)
    unknown = next(row for row in rows)
    unknown["entry_count"] = None
    unknown_rows = scatter_rows(
        [{**artifact["index"]["lists"][0], "id": artifact["index"]["lists"][0]["id"]}],
        {"lists": [{"id": artifact["index"]["lists"][0]["id"], "name": "x", "topics": ["Other"], "entry_count": None}]},
        "topic",
    )
    assert unknown_rows[0]["size"] == UNKNOWN_POINT_SIZE
    spec = scatter_spec(rows, color_title="community")
    encoded = spec.to_dict()["encoding"]
    assert encoded["color"]["field"] == "color"
    assert encoded["size"]["field"] == "size"


def test_set_diff_and_edge_rows_split_independent_and_copy_lineage():
    artifact, network, _project_index = build_landscape_artifact()
    memberships = {}
    previews = {}
    for shard in artifact["shards"].values():
        for record in shard["lists"]:
            memberships[record["id"]] = record["membership"]
            previews[record["id"]] = {row["neighbor"]: row for row in record["neighbor_previews"]}
    hub_ids = [row["id"] for row in network["hub_projects"]]
    rows = set_diff_rows({k: memberships[k] for k in ("111", "333")}, hub_ids, names={"111": "A", "333": "C"})
    buckets = {row["Bucket"] for row in rows}
    assert "shared_independent" in buckets
    assert "unique_and_not_a_hub" in buckets
    ab = edge_inspector_rows(previews["111"]["222"])
    ac = edge_inspector_rows(previews["111"]["333"])
    assert any(row["Kind"] == "copy-lineage" for row in ab)
    assert any(row["Kind"] == "independent" for row in ac)
    rendered = SIGNATURE_CAPTION + str(rows)
    for banned in ("high quality", "trusted", "top rated"):
        assert banned not in rendered.lower()
