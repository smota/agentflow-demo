"""Pure, index-only catalogue analytics for dashboards and comparison."""
from __future__ import annotations

from collections import Counter
from statistics import median

FRESHNESS_ORDER = ("Within 30 days", "Within 90 days", "Within 180 days", "Within 365 days", "Older than a year", "Unknown")


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
            "scatter": scatter}


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
