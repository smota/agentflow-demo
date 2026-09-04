from awesome.insights import dashboard, comparison, entries_distribution, stars_distribution
from tests.test_explore import fixture_index


def test_dashboard_uses_only_eligible_population_and_explicit_unknowns():
    index, _ = fixture_index(); index["lists"][0]["state"] = "pending"
    index["lists"][1]["entry_count"] = None
    result = dashboard(index)
    assert result["population"] == 14
    assert result["freshness_known"] == 0 and result["freshness_unknown"] == 14
    assert sum(row["Lists"] for row in result["freshness"]) == 14
    assert result["entries_known"] == 13 and result["entries_unknown"] == 1
    assert next(row for row in result["scatter"] if row["List"] == "owner/awesome-1")["Entries"] is None
    assert result["topics"] and len(result["scatter"]) == 14
    subset = dashboard(index, [index["lists"][1], index["lists"][2], index["lists"][3]])
    assert subset["population"] == 3 and len(subset["scatter"]) == 3


def test_comparison_deduplicates_bounds_and_rejects_noneligible_ids():
    index, _ = fixture_index(); index["lists"][3]["state"] = "pending"
    rows = comparison(index, ["1", "1", "3", "2", "4", "5", "6"])
    assert [row["List"] for row in rows] == ["owner/awesome-1", "owner/awesome-2", "owner/awesome-4"]
    assert set(rows[0]) == {"List", "Stars", "Forks", "Entries", "Categories", "Contributors seen", "Freshness index", "Last content change", "GitHub"}


def test_stars_distribution_buckets_the_eligible_population():
    # fixture_index: 14 lists with stars 100..113 ("100-499"), one at 300,000 ("50k+").
    index, _ = fixture_index()
    result = stars_distribution(index["lists"])
    by_label = {row["Stars"]: row["Lists"] for row in result}
    assert by_label["100–499"] == 14
    assert by_label["50k+"] == 1
    assert sum(by_label.values()) == 15
    assert "Unknown" not in by_label  # stars is always known for a curation-eligible list


def test_stars_distribution_omits_empty_buckets():
    index, _ = fixture_index()
    result = stars_distribution(index["lists"])
    assert all(row["Lists"] > 0 for row in result)


def test_entries_distribution_buckets_known_and_unknown_counts_explicitly():
    index, _ = fixture_index()
    index["lists"][0]["entry_count"] = None
    result = entries_distribution(index["lists"])
    by_label = {row["Entries"]: row["Lists"] for row in result}
    assert by_label["1–24"] == 14  # remaining 14 lists all carry the 5-entry fixture README
    assert by_label["Unknown"] == 1
    assert sum(by_label.values()) == 15


def test_dashboard_includes_distribution_breakdowns():
    index, _ = fixture_index()
    result = dashboard(index)
    assert sum(row["Lists"] for row in result["stars_distribution"]) == 15
    assert sum(row["Lists"] for row in result["entries_distribution"]) == 15
