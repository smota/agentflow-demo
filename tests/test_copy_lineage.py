from awesome.copy_lineage import (COPY_THRESHOLD, INDEPENDENT_THRESHOLD, independent_clusters,
                                   independent_count, is_copy_lineage, title_similarity)


def occ(list_id, list_name, title):
    return {"list_id": list_id, "list_name": list_name, "title": title}


def test_title_similarity_identical_normalizes_to_one():
    assert title_similarity("Awesome  Tool", "awesome tool") == 1.0


def test_is_copy_lineage_uses_validated_threshold():
    assert COPY_THRESHOLD == 0.92 and INDEPENDENT_THRESHOLD == 0.60
    assert is_copy_lineage("Photo Gallery Tool", "Photo Gallery Tool") is True
    assert is_copy_lineage("Photo Gallery Tool", "A totally different description here") is False


def test_independent_count_single_list_is_one():
    occs = [occ("1", "list-a", "Tool"), occ("1", "list-a", "Tool (dup mention)")]
    assert independent_count(occs) == 1


def test_independent_count_two_lists_near_identical_titles_collapses_to_one():
    """Same-owner/forked sibling lists citing with near-identical text (#65's dominant finding)
    must not count as two independent citations."""
    occs = [occ("1", "uhub/awesome-c", "Tool"), occ("2", "uhub/awesome-cpp", "Tool")]
    assert independent_count(occs) == 1
    clusters = independent_clusters(occs)
    assert len(clusters) == 1 and set(clusters[0]) == {"uhub/awesome-c", "uhub/awesome-cpp"}


def test_independent_count_two_lists_differing_titles_counts_as_two():
    occs = [occ("1", "list-a", "A Great Photo Tool"), occ("2", "list-b", "Wildly Different Wording Entirely")]
    assert independent_count(occs) == 2
    clusters = independent_clusters(occs)
    assert len(clusters) == 2


def test_independent_count_three_lists_two_siblings_one_independent():
    occs = [occ("1", "owner/awesome-a", "Great Tool"),
            occ("2", "owner/awesome-b", "Great Tool"),
            occ("3", "other/curated-list", "A Completely Different Description")]
    assert independent_count(occs) == 2
