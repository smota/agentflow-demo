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


# --- H3 (issue #53): headless-CLI overlay is a fallback only, never overrides _SYNONYMS ---

def test_normalize_topic_overrides_fill_a_gap_synonyms_leaves_unmapped():
    overrides = {"weird niche category": "machine-learning"}
    assert normalize_topic("Weird Niche Category", overrides) == "machine-learning"


def test_normalize_topic_overrides_never_shadow_a_synonym_hit():
    # "ML" already resolves via _SYNONYMS; an override claiming something else must be ignored.
    overrides = {"ml": "self-hosting"}
    assert normalize_topic("ML", overrides) == "machine-learning"


def test_normalize_topic_missing_overrides_key_falls_back_as_before():
    assert normalize_topic("Weird Niche Category", {"unrelated": "frontend"}) == "weird-niche-category"


def test_normalized_topics_threads_overrides_through():
    occurrences = [{"category": "Weird Niche Category"}]
    assert normalized_topics(occurrences) == ["weird-niche-category"]
    assert normalized_topics(occurrences, overrides={"weird niche category": "machine-learning"}) == ["machine-learning"]
