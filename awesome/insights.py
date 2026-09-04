"""Pure, index-only catalogue analytics for dashboards and comparison."""
from __future__ import annotations

from collections import Counter
from statistics import median

FRESHNESS_ORDER = ("Within 30 days", "Within 90 days", "Within 180 days", "Within 365 days", "Older than a year", "Unknown")

# D2 (issue #50): extended distribution visualizations, index-only like the rest of this module --
# no dependency on D1's offline network artifact, so these stay simple and fast to compute on every
# session load. Buckets are open, observed-value ranges over the population's own stars/entry_count
# fields (never an invented score); "Unknown" is kept explicit rather than folded into a zero bucket,
# matching this module's existing freshness/topic aggregation discipline.
STAR_BUCKETS = (
    ("100–499", 100, 500), ("500–999", 500, 1_000), ("1k–4.9k", 1_000, 5_000),
    ("5k–9.9k", 5_000, 10_000), ("10k–49.9k", 10_000, 50_000), ("50k+", 50_000, None),
)
ENTRY_BUCKETS = (
    ("1–24", 1, 25), ("25–99", 25, 100), ("100–299", 100, 300),
    ("300–999", 300, 1_000), ("1,000+", 1_000, None),
)


def _bucket(value, buckets):
    if value is None:
        return "Unknown"
    for label, low, high in buckets:
        if value >= low and (high is None or value < high):
            return label
    return "Unknown"


def eligible_lists(index: dict) -> list[dict]:
    return [item for item in index["lists"] if item.get("public") is True and item.get("state") == "eligible"]


def dashboard(index: dict, lists: list[dict] | None = None) -> dict:
    lists = eligible_lists(index) if lists is None else [
        item for item in lists if item.get("public") is True and item.get("state") == "eligible"
    ]
    known_freshness = [item for item in lists if item.get("freshness", {}).get("days") is not None]
    known_entries = [item for item in lists if item.get("entry_count") is not None]
    topics = Counter(topic for item in lists for topic in item.get("topics", []))
    ranges = Counter(item.get("freshness", {}).get("range", "Unknown") for item in lists)
    scatter = [{"List": item["name"], "Stars": item["stars"], "Entries": item.get("entry_count"),
                "Topic": (item.get("topics") or ["Other"])[0]} for item in lists]
    return {"population": len(lists), "observed_at": index["generated_at"][:10],
            "total_entries": sum(item["entry_count"] for item in known_entries),
            "entries_known": len(known_entries), "entries_unknown": len(lists) - len(known_entries),
            "median_stars": round(median(item["stars"] for item in lists)) if lists else 0,
            "fresh_30": ranges["Within 30 days"],
            "freshness_known": len(known_freshness), "freshness_unknown": len(lists) - len(known_freshness),
            "topics": [{"Topic": key, "Lists": value} for key, value in topics.most_common()],
            "freshness": [{"Range": key, "Lists": ranges[key]} for key in FRESHNESS_ORDER if ranges[key]],
            "scatter": scatter,
            "stars_distribution": stars_distribution(lists), "entries_distribution": entries_distribution(lists)}


def stars_distribution(lists: list[dict]) -> list[dict]:
    """D2: how the (already-filtered) eligible population spreads across observed star-count
    ranges -- every list has a known `stars` value (the curation-eligibility gate requires it), so
    there is no "Unknown" bucket here, unlike `entries_distribution`."""
    counts = Counter(_bucket(item["stars"], STAR_BUCKETS) for item in lists)
    order = [label for label, _, _ in STAR_BUCKETS]
    return [{"Stars": label, "Lists": counts[label]} for label in order if counts[label]]


def entries_distribution(lists: list[dict]) -> list[dict]:
    """D2: how the population spreads across observed indexed-entry-count ranges. `entry_count` can
    be unknown (content indexing pending/unsupported), which is kept as its own explicit bucket
    rather than silently dropped or folded into "1–24", matching this module's "unknown is not
    zero" discipline elsewhere."""
    counts = Counter(_bucket(item.get("entry_count"), ENTRY_BUCKETS) for item in lists)
    order = [label for label, _, _ in ENTRY_BUCKETS] + ["Unknown"]
    return [{"Entries": label, "Lists": counts[label]} for label in order if counts[label]]


def comparison(index: dict, ids: list[str]) -> list[dict]:
    wanted = list(dict.fromkeys(ids))[:4]
    by_id = {item["id"]: item for item in eligible_lists(index)}
    rows = []
    for rid in wanted:
        if rid not in by_id:
            continue
        item = by_id[rid]
        rows.append({"List": item["name"], "Stars": item["stars"], "Forks": item.get("forks"),
                     "Entries": item.get("entry_count"), "Categories": item.get("category_count"),
                     "Contributors seen": item.get("contributors_count"),
                     "Freshness index": item.get("freshness", {}).get("index"),
                     "Last content change": (item.get("content_updated_at") or "Unknown")[:10],
                     "GitHub": item["url"]})
    return rows
