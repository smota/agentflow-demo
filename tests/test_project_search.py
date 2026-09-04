from awesome.project_search import citation_label, relevance, search_projects


def record(id_, title, list_count=1, independent_list_count=1, topics=None):
    return {"id": id_, "url": f"https://example.org/{id_}", "title": title,
            "list_count": list_count, "independent_list_count": independent_list_count,
            "topics": topics or []}


RECORDS = [
    record("a", "Awesome Photo Gallery", topics=["photos"]),
    record("b", "Self-Hosted Photo Manager", list_count=5, independent_list_count=1, topics=["photos", "self-hosting"]),
    record("c", "Totally Unrelated CLI Tool", topics=["devops"]),
]


def test_empty_query_returns_no_results():
    assert search_projects(RECORDS, "") == []


def test_matches_title_and_topic_terms():
    results = search_projects(RECORDS, "photo")
    assert {r["id"] for r in results} == {"a", "b"}


def test_all_terms_must_match():
    results = search_projects(RECORDS, "photo self-hosting")
    assert [r["id"] for r in results] == ["b"]


def test_ranking_never_uses_list_count_or_independent_count():
    """Record 'b' has list_count=5 (much higher than 'a's 1) but must not outrank 'a' for a query
    that matches 'a' more strongly on text alone -- ranking is text relevance only."""
    results = search_projects(RECORDS, "awesome photo gallery")
    assert results[0]["id"] == "a"


def test_relevance_scores_exact_phrase_title_match_highest():
    terms = "photo gallery".split()
    assert relevance(RECORDS[0], terms) > relevance(RECORDS[2], terms)


def test_citation_label_single_source_no_trust_framing():
    label = citation_label(1, 1)
    assert label["kind"] == "single"
    assert "trust" not in label["text"].lower() and "quality" not in label["text"].lower()


def test_citation_label_independent_evidence_claims_independence_honestly():
    label = citation_label(5, 3)
    assert label["kind"] == "independent"
    assert "3" in label["text"] and "5" in label["text"]


def test_citation_label_no_independent_evidence_shows_raw_count_without_trust_claim():
    """Regression guard for the redesign's core requirement: when the discount collapses all
    citations into one copy-lineage cluster, the raw count must be shown honestly, never framed
    as validated independent agreement."""
    label = citation_label(4, 1)
    assert label["kind"] == "raw-only"
    assert "independent" not in label["text"].lower().split("not shown as an")[0]
    assert "4" in label["text"]
