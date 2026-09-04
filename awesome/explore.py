"""Pure list discovery state, filtering and share links."""
from __future__ import annotations
import math
from urllib.parse import urlencode

APP_URL = "https://awesomeawesomeness.streamlit.app/"
SORTS = ("Most starred", "Name A–Z", "Most indexed entries", "Recently updated")
STATES = ("Curated lists", "Needs review", "All candidates")
FRESHNESS = ("Any freshness", "Within 30 days", "Within 90 days", "Within 180 days", "Within 365 days", "Older than a year", "Unknown")
DEFAULTS = {"q": "", "topic": "All topics", "min_stars": 100, "state": "Curated lists",
            "freshness": "Any freshness", "archived": "Include archived", "forks": "Include forks",
            "sort": "Most starred", "page": 1, "view": "Discover", "list": "", "layout": "Cards",
            "content_q": "", "content_category": "all", "compare": "", "search_q": "", "network_list": ""}
PAGE_SIZE = 12


def normalize(params: dict, index: dict) -> dict:
    result = dict(DEFAULTS)
    for key, value in params.items():
        if key not in result or isinstance(value, (list, tuple, dict, bool)): continue
        if key in {"page", "min_stars"}:
            try: result[key] = max(1 if key == "page" else 100, min(1_000_000_000, int(value)))
            except (ValueError, TypeError, OverflowError): pass
        elif isinstance(value, str): result[key] = value[:400] if key == "compare" else (value[:200] if key in {"q", "content_q", "content_category", "search_q"} else value)
    options = {"topic": {"All topics", *(t for item in index["lists"] for t in item["topics"])},
               "state": STATES, "freshness": FRESHNESS, "sort": SORTS,
               "archived": ("Include archived", "Active only"), "forks": ("Include forks", "Originals only"),
               "view": ("Discover", "Search projects", "Insights", "List", "Delivery story", "Network"),
               "layout": ("Cards", "Table")}
    for key, values in options.items():
        if result[key] not in values: result[key] = DEFAULTS[key]
    valid_ids = {x["id"] for x in index["lists"]}
    if result["list"] not in valid_ids:
        result["list"] = ""
        if result["view"] == "List": result["view"] = "Discover"
    if result["network_list"] not in valid_ids:
        result["network_list"] = ""
    result["q"] = " ".join(result["q"].split())
    result["search_q"] = " ".join(result["search_q"].split())
    eligible = {x["id"] for x in index["lists"] if x.get("state") == "eligible" and x.get("public") is True}
    result["compare"] = ",".join(list(dict.fromkeys(x for x in result["compare"].split(",") if x in eligible))[:4])
    return result


def filtered(index: dict, state: dict) -> list[dict]:
    words = state["q"].casefold().split(); results = []
    for item in index["lists"]:
        if item.get("public") is not True: continue
        if state["state"] == "Curated lists" and item["state"] != "eligible": continue
        if state["state"] == "Needs review" and item["state"] != "pending": continue
        if item.get("stars") is None or item["stars"] < state["min_stars"]: continue
        if state["topic"] != "All topics" and state["topic"] not in item["topics"]: continue
        if state["archived"] == "Active only" and item.get("archived"): continue
        if state["forks"] == "Originals only" and item.get("is_fork"): continue
        fresh_range = item.get("freshness", {}).get("range", "Unknown"); freshness = state["freshness"]
        order = {"Within 30 days": 0, "Within 90 days": 1, "Within 180 days": 2,
                 "Within 365 days": 3, "Older than a year": 4}
        if freshness.startswith("Within") and (fresh_range not in order or order[fresh_range] > order[freshness]): continue
        if freshness == "Unknown" and fresh_range != "Unknown": continue
        if freshness == "Older than a year" and fresh_range != "Older than a year": continue
        text = " ".join([item["name"], item.get("scope") or "", item.get("description") or "", *item["topics"], *item.get("github_topics", [])]).casefold()
        if all(word in text for word in words): results.append(item)
    sort = state["sort"]
    if sort == "Name A–Z": key = lambda x: (x["name"].casefold(), x["id"])
    elif sort == "Most indexed entries": key = lambda x: (-(x.get("entry_count") if x.get("entry_count") is not None else -1), x["name"].casefold())
    elif sort == "Recently updated": key = lambda x: (x.get("freshness", {}).get("days") if x.get("freshness", {}).get("days") is not None else float("inf"), x["name"].casefold())
    else: key = lambda x: (-x["stars"], x["name"].casefold())
    return sorted(results, key=key)


def page_slice(total: int, page: int):
    pages = max(1, math.ceil(total / PAGE_SIZE)); page = max(1, min(page, pages))
    return page, pages, (page - 1) * PAGE_SIZE, min(page * PAGE_SIZE, total)


def share_url(state: dict):
    params = {k: v for k, v in state.items() if k in DEFAULTS and v != DEFAULTS[k]}
    return APP_URL + ("?" + urlencode(params) if params else "")


def content_filter(detail, query="", category="all"):
    words = query.casefold().split()
    return [entry for entry in detail["entries"] if (category == "all" or entry["category"] == category)
            and all(word in (entry["title"] + " " + " ".join(entry.get("properties", {}).values())).casefold() for word in words)]


def number(value):
    return "Unknown" if value is None else f"{value:,}"
