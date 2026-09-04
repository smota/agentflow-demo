from awesome.topics import normalize_topic, normalized_topics


def test_normalize_topic_maps_known_synonyms_to_one_canonical_tag():
    assert normalize_topic("Machine Learning") == "machine-learning"
    assert normalize_topic("ML") == "machine-learning"
    assert normalize_topic("Artificial Intelligence") == "machine-learning"
    assert normalize_topic("Self Hosted") == "self-hosting"
    assert normalize_topic("Selfhosted") == "self-hosting"


def test_normalize_topic_degrades_gracefully_for_unmapped_labels():
    assert normalize_topic("Weird Niche Category") == "weird-niche-category"


def test_normalize_topic_empty_label():
    assert normalize_topic("") == ""
    assert normalize_topic(None) == ""


def test_normalized_topics_dedupes_and_preserves_order():
    occurrences = [{"category": "ML"}, {"category": "Machine Learning"}, {"category": "Self Hosted"}]
    assert normalized_topics(occurrences) == ["machine-learning", "self-hosting"]


def test_normalized_topics_respects_limit():
    occurrences = [{"category": f"Topic {i}"} for i in range(10)]
    assert len(normalized_topics(occurrences, limit=3)) == 3
