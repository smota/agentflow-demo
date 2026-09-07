import json
from pathlib import Path

from jsonschema import Draft202012Validator

from awesome.copy_lineage import is_copy_lineage
from awesome.landscape import (
    CONTENT_POLICY,
    FORMAT,
    PREVIEW_LIMIT,
    LandscapeAccumulator,
    list_shard_prefix,
    set_diff,
    shard_path,
    validate_landscape,
)
from awesome.landscape_layout import layout_landscape
from awesome.projects import derive_projects
from tests.test_network import GENERATED_AT, build_network, build_network_fixture

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("high quality", "trusted", "top rated", "best of")


def _projects_and_network():
    index, details = build_network_fixture()
    derived = derive_projects(index, details, GENERATED_AT)
    network, project_index = build_network()
    records = [record for shard in derived["shards"].values() for record in shard["projects"]]
    eligible = [item["id"] for item in index["lists"] if item.get("state") == "eligible"]
    return records, network, project_index, eligible, index


def build_landscape_artifact():
    records, network, project_index, eligible, _index = _projects_and_network()
    acc = LandscapeAccumulator(network["list_pairs"])
    for record in records:
        acc.add_project(record)
    layout = layout_landscape(eligible, network["list_pairs"])
    return acc.finalize(network, layout, eligible, GENERATED_AT), network, project_index


def test_policy_strings_ban_quality_trust_language():
    text = CONTENT_POLICY.casefold()
    assert "composition of citations" in text
    assert "not an ontology" in text
    assert "never a quality, trust, or best-list score" in text
    for banned in BANNED:
        assert banned not in text


def test_shard_path_is_stable_sha256_prefix():
    assert shard_path("ab") == "landscape/ab.json"
    prefix = list_shard_prefix("111")
    assert len(prefix) == 2 and prefix == list_shard_prefix("111")
    assert list_shard_prefix("111") != list_shard_prefix("222")


def test_schema_is_valid_draft_2020_12():
    schema = json.loads((ROOT / "schemas/landscape-index.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_validator_rejects_digest_and_format_mismatches():
    artifact, network, project_index = build_landscape_artifact()
    index = artifact["index"]
    shards = artifact["shards"]
    validate_landscape(index, network, project_index, shards)
    broken = dict(index)
    broken["format_version"] = 99
    try:
        validate_landscape(broken, network, project_index, shards)
        raise AssertionError("expected format mismatch")
    except ValueError as exc:
        assert "format" in str(exc).lower()
    broken = dict(index)
    broken["digest"] = "0" * 64
    try:
        validate_landscape(broken, network, project_index, shards)
        raise AssertionError("expected digest mismatch")
    except ValueError as exc:
        assert "digest" in str(exc).lower()
    broken_net = dict(network)
    broken_net["digest"] = "0" * 64
    try:
        validate_landscape(index, broken_net, project_index, shards)
        raise AssertionError("expected source digest mismatch")
    except ValueError as exc:
        assert "network" in str(exc).lower()


def test_ab_copy_lineage_ac_independent_ad_excluded_from_previews():
    artifact, _network, _project_index = build_landscape_artifact()
    shards = artifact["shards"]
    by_id = {}
    for shard in shards.values():
        for record in shard["lists"]:
            by_id[record["id"]] = record
    a_previews = {row["neighbor"]: row for row in by_id["111"]["neighbor_previews"]}
    assert "222" in a_previews and "333" in a_previews
    assert "444" not in a_previews
    ab = a_previews["222"]
    ac = a_previews["333"]
    assert ab["total"] == 6 and ab["copy_lineage"] and not ab["independent"]
    assert ac["total"] == 5 and ac["independent"] and not ac["copy_lineage"]
    assert all(not is_copy_lineage(item["title"], item["neighbor_title"]) for item in ac["independent"])


def test_signature_stacks_sum_to_distinct_and_unique_not_hub():
    artifact, network, _project_index = build_landscape_artifact()
    hub_ids = set(network["hub_projects"] and [row["id"] for row in network["hub_projects"]])
    shards = artifact["shards"]
    by_id = {}
    for shard in shards.values():
        for record in shard["lists"]:
            by_id[record["id"]] = record
    index_by_id = {row["id"]: row for row in artifact["index"]["lists"]}
    for lid, record in by_id.items():
        row = index_by_id[lid]
        total = row["unique"] + row["family"] + row["shared"] + row["hub"]
        assert total == len(record["membership"])
    memberships = {lid: rec["membership"] for lid, rec in by_id.items()}
    diff = set_diff({k: memberships[k] for k in ("111", "333")}, hub_ids)
    assert diff["unique_and_not_a_hub"]
    assert all(item["id"] not in hub_ids for item in diff["unique_and_not_a_hub"])
    assert diff["shared_independent"]
    assert diff["shared_copy_lineage"] == []
    a_only = {item["id"] for item in diff["unique_to_111"]}
    assert a_only


def test_set_diff_uses_compact_membership_only():
    artifact, network, _project_index = build_landscape_artifact()
    hub_ids = [row["id"] for row in network["hub_projects"]]
    memberships = {}
    for shard in artifact["shards"].values():
        for record in shard["lists"]:
            if record["id"] in {"111", "222"}:
                memberships[record["id"]] = record["membership"]
    diff = set_diff(memberships, hub_ids)
    assert diff["shared_copy_lineage"]
    assert f"unique_to_111" in diff and f"unique_to_222" in diff


def test_hosted_modules_do_not_import_layout_or_derive():
    list_ui = (ROOT / "awesome/list_ui.py").read_text(encoding="utf-8")
    view = (ROOT / "awesome/landscape_view.py").read_text(encoding="utf-8") if (ROOT / "awesome/landscape_view.py").exists() else ""
    landscape = (ROOT / "awesome/landscape.py").read_text(encoding="utf-8")
    for source in (list_ui, view, landscape):
        assert "landscape_layout" not in source
        assert "derive_landscape" not in source


def test_format_constant():
    assert FORMAT == 1
    assert PREVIEW_LIMIT >= 1
