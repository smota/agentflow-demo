from awesome.insights import dashboard, comparison
from tests.test_explore import fixture_index


def test_dashboard_uses_only_eligible_population_and_explicit_unknowns():
    index, _ = fixture_index(); index["lists"][0]["state"] = "pending"
    result = dashboard(index)
    assert result["population"] == 14
    assert result["freshness_known"] == 0 and result["freshness_unknown"] == 14
    assert sum(row["Lists"] for row in result["freshness"]) == 14
    assert result["topics"] and len(result["scatter"]) == 14
    subset = dashboard(index, [index["lists"][1], index["lists"][2], index["lists"][3]])
    assert subset["population"] == 3 and len(subset["scatter"]) == 3


def test_comparison_deduplicates_bounds_and_rejects_noneligible_ids():
    index, _ = fixture_index(); index["lists"][3]["state"] = "pending"
    rows = comparison(index, ["1", "1", "3", "2", "4", "5", "6"])
    assert [row["List"] for row in rows] == ["owner/awesome-1", "owner/awesome-2", "owner/awesome-4"]
    assert set(rows[0]) == {"List", "Stars", "Forks", "Entries", "Categories", "Contributors seen", "Freshness index", "Last content change", "GitHub"}
