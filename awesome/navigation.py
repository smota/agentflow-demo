"""Pure, allowlisted discovery state; no runtime network or persistence."""
from urllib.parse import urlencode
from awesome.catalogue import search

PUBLIC_URL = "https://awesomeawesomeness.streamlit.app/"
DEFAULTS = {"q": "", "source": "All sources", "topic": "All topics",
            "sort": "Title A–Z", "view": "Discover", "page": 1}
SORTS = ("Title A–Z", "Title Z–A")
VIEWS = ("Discover", "Sources", "Delivery story")


def normalize(params: dict, sources: list[str], topics: list[str]) -> dict:
    state = dict(DEFAULTS)
    for key, choices in (("source", sources), ("topic", topics),
                         ("sort", SORTS), ("view", VIEWS)):
        value = params.get(key)
        if isinstance(value, str) and value in choices:
            state[key] = value
    query = params.get("q", "")
    if isinstance(query, str):
        state["q"] = "".join(c for c in query[:200] if c.isprintable()).strip()
    page = str(params.get("page", "1"))
    if page.isascii() and page.isdigit() and len(page) <= 7:
        state["page"] = max(1, min(1_000_000, int(page)))
    return state


def share_url(state: dict) -> str:
    # Callers supply normalized state. Never include arbitrary query parameters.
    return PUBLIC_URL + "?" + urlencode({k: state[k] for k in DEFAULTS
                                          if k in state and state[k] != DEFAULTS[k]})


def matching_occurrences(item: dict, source: str, topic: str) -> list[dict]:
    return [o for o in item["occurrences"]
            if (source == "All sources" or o["source"] == source)
            and (topic == "All topics" or o["category"] == topic)]


def discover(resources: list[dict], state: dict) -> list[dict]:
    found = [r for r in search(resources, state["q"])
             if matching_occurrences(r, state["source"], state["topic"])]
    return sorted(found, key=lambda r: (r["title"].casefold(), r["url"]),
                  reverse=state["sort"] == "Title Z–A")


def page_slice(count: int, requested: int, size: int = 24) -> tuple[int, int, int, int]:
    pages = max(1, (count + size - 1) // size)
    page = max(1, min(requested, pages))
    return page, pages, (page - 1) * size, min(page * size, count)
