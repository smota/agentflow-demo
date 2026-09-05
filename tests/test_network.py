import pytest

from awesome.catalogue import digest
from awesome.lists import FORMAT as LIST_FORMAT, parse_readme, profile
from awesome.network import (FORMAT, HUB_LIMIT, MIN_HUB_LIST_COUNT, MIN_SHARED_PROJECTS,
                              NEAR_DUP_COPY_FRACTION, NEAR_DUP_JACCARD, NetworkAccumulator,
                              neighbors_of, validate_network)
from awesome.projects import derive_projects
from tests.test_lists import REV, meta

GENERATED_AT = "2026-09-04T00:00:00Z"


def _md(entries):
    lines = ["# A curated list\n## Tools"]
    for title, url in entries:
        lines.append(f"- [{title}]({url}) - Descriptive prose not republished.")
    return "\n".join(lines)


def _list(list_id, name, entries):
    data = meta(id=list_id, name=name, url=f"https://github.com/{name}")
    md = _md(entries)
    return profile(data, parse_readme(md, name, REV), md)


def build_network_fixture():
    """Four eligible lists engineered against real thresholds (`MIN_SHARED_PROJECTS = 5`,
    `NEAR_DUP_JACCARD = 0.5`, `NEAR_DUP_COPY_FRACTION = 0.6`):

    - A and B share 6 projects, all titled identically -> high jaccard AND high copy_fraction ->
      near_duplicate (the "same-owner/forked sibling list" case #65 and this module's docstring
      describe).
    - A and C share 5 projects (right at the threshold), each titled differently in C -> shared
      count clears the minimum but neither near-duplicate condition fires (genuine independent
      overlap, not a copy).
    - A and D share only 2 projects -> below `MIN_SHARED_PROJECTS`, must not appear in list_pairs
      at all.
    - `tool/0` is cited by A, B and C: A/B use identical wording (one copy-lineage cluster), C uses
      different wording (a second cluster) -> independent_list_count == 2 while list_count == 3,
      giving a real, non-trivial hub_discount to assert on.
    """
    shared_ab = [(f"Tool {i}", f"https://example.org/tool/{i}") for i in range(6)]
    a_entries = shared_ab + [("A only 1", "https://example.org/a-only-1"),
                              ("A only 2", "https://example.org/a-only-2")]
    b_entries = shared_ab + [("B only 1", "https://example.org/b-only-1"),
                              ("B only 2", "https://example.org/b-only-2")]
    shared_ac = [(f"Different wording {i}", f"https://example.org/tool/{i}") for i in range(5)]
    c_entries = shared_ac + [("C only 1", "https://example.org/c-only-1"),
                              ("C only 2", "https://example.org/c-only-2"),
                              ("C only 3", "https://example.org/c-only-3")]
    shared_ad = [("Shared with D 1", "https://example.org/tool/0"),
                 ("Shared with D 2", "https://example.org/tool/1")]
    d_entries = shared_ad + [("D only 1", "https://example.org/d-only-1"),
                              ("D only 2", "https://example.org/d-only-2"),
                              ("D only 3", "https://example.org/d-only-3")]

    item_a, detail_a = _list("111", "owner/awesome-a", a_entries)
    item_b, detail_b = _list("222", "owner/awesome-b", b_entries)
    item_c, detail_c = _list("333", "other/curated-c", c_entries)
    item_d, detail_d = _list("444", "other/curated-d", d_entries)
    items = [item_a, item_b, item_c, item_d]
    index = {"format_version": LIST_FORMAT, "min_stars": 100, "lists": items,
              "counts": {"eligible": 4}}
    index["digest"] = digest(index)
    details = {item_a["detail"]: detail_a, item_b["detail"]: detail_b,
               item_c["detail"]: detail_c, item_d["detail"]: detail_d}
    return index, details


def build_network():
    index, details = build_network_fixture()
    derived = derive_projects(index, details, GENERATED_AT)
    accumulator = NetworkAccumulator()
    for shard in derived["shards"].values():
        for record in shard["projects"]:
            accumulator.add_project(record)
    return accumulator.finalize(derived["index"]["digest"], GENERATED_AT), derived["index"]


def pair(list_pairs, a, b):
    key = {a, b}
    return next(row for row in list_pairs if {row["a"], row["b"]} == key)


def test_ab_pair_is_near_duplicate_on_identical_wording():
    network, _ = build_network()
    row = pair(network["list_pairs"], "111", "222")
    assert row["shared"] == 6
    assert row["jaccard"] == pytest.approx(6 / (8 + 8 - 6))
    assert row["copy_fraction"] == 1.0
    assert row["near_duplicate"] is True


def test_ac_pair_clears_threshold_but_is_not_near_duplicate():
    network, _ = build_network()
    row = pair(network["list_pairs"], "111", "333")
    assert row["shared"] == 5
    assert row["copy_fraction"] == 0.0
    assert row["near_duplicate"] is False


def test_ad_pair_below_minimum_shared_is_excluded():
    network, _ = build_network()
    ids = {frozenset((row["a"], row["b"])) for row in network["list_pairs"]}
    assert frozenset(("111", "444")) not in ids


def test_list_pairs_sorted_by_shared_descending():
    network, _ = build_network()
    shared_values = [row["shared"] for row in network["list_pairs"]]
    assert shared_values == sorted(shared_values, reverse=True)


def test_hub_project_cited_by_four_lists_has_discounted_independent_count():
    network, _ = build_network()
    tool0 = next(row for row in network["hub_projects"] if row["url"] == "https://example.org/tool/0")
    assert tool0["list_count"] == 4  # cited by A, B, C and D (D's "shared with D" overlap)
    # A/B copy-lineage cluster (identical wording) + C's cluster + D's cluster = 3 independent.
    assert tool0["independent_list_count"] == 3
    assert tool0["hub_discount"] == 1


def test_hub_projects_sorted_by_independent_list_count_desc():
    network, _ = build_network()
    ranks = [(row["independent_list_count"], row["list_count"]) for row in network["hub_projects"]]
    assert ranks == sorted(ranks, reverse=True)


def test_hub_projects_exclude_single_list_projects():
    network, _ = build_network()
    assert all(row["list_count"] >= MIN_HUB_LIST_COUNT for row in network["hub_projects"])


def test_counts_reconcile():
    network, _ = build_network()
    assert network["counts"]["hub_projects"] == len(network["hub_projects"])
    assert network["counts"]["pairs"] == len(network["list_pairs"])
    assert network["counts"]["near_duplicate_pairs"] == sum(
        1 for row in network["list_pairs"] if row["near_duplicate"])


def test_neighbors_of_returns_directed_rows_ranked_by_similarity():
    network, _ = build_network()
    rows = neighbors_of(network["list_pairs"], "111")
    neighbors = [row["neighbor"] for row in rows]
    assert neighbors[0] == "222"  # highest jaccard/shared neighbor of A
    assert "444" not in neighbors  # below MIN_SHARED_PROJECTS, never a neighbor
    assert all(row["a"] == "111" or row["b"] == "111" for row in rows)


def test_neighbors_of_respects_limit():
    network, _ = build_network()
    assert len(neighbors_of(network["list_pairs"], "111", limit=1)) == 1


def test_validate_network_round_trips():
    network, project_index = build_network()
    validate_network(network, project_index)  # no raise


def test_validate_rejects_stale_source_project_index():
    network, project_index = build_network()
    other = dict(project_index, digest="0" * 64)
    with pytest.raises(ValueError, match="does not match"):
        validate_network(network, other)


def test_validate_rejects_tampered_digest():
    network, project_index = build_network()
    network["counts"]["pairs"] = 999
    with pytest.raises(ValueError, match="digest"):
        validate_network(network, project_index)


def test_validate_rejects_near_duplicate_flag_tampering():
    network, project_index = build_network()
    row = pair(network["list_pairs"], "111", "333")
    row["near_duplicate"] = True
    network["digest"] = digest({k: v for k, v in network.items() if k != "digest"})
    with pytest.raises(ValueError, match="near_duplicate"):
        validate_network(network, project_index)


def test_validate_rejects_hub_discount_tampering():
    network, project_index = build_network()
    network["hub_projects"][0]["hub_discount"] = 999
    network["digest"] = digest({k: v for k, v in network.items() if k != "digest"})
    with pytest.raises(ValueError, match="Hub discount"):
        validate_network(network, project_index)


def test_module_thresholds_match_documented_values():
    # Guards against silent threshold drift -- these are cited by name in the module docstring's
    # threshold-provenance section and in `docs` referencing D1; a change here should be deliberate.
    assert (FORMAT, HUB_LIMIT, MIN_HUB_LIST_COUNT, MIN_SHARED_PROJECTS,
            NEAR_DUP_JACCARD, NEAR_DUP_COPY_FRACTION) == (1, 100, 2, 5, 0.5, 0.6)
