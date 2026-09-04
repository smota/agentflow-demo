"""Entry-level category/topic normalization for cross-list semantic matching (A4).

Individual Awesome lists label the same kind of resource with different free-text category names
(e.g. "Machine Learning", "ML", "Artificial Intelligence", "Self Hosted" vs "Selfhosted"). Free-text
substring search over these raw labels misses matches that share meaning but not spelling. This
module normalizes each occurrence's own, already-published `category` string (captured per
occurrence in `awesome.projects.derive_projects`, never invented) into a small set of canonical
topic tags via light normalization plus a disclosed synonym table -- entry-level, not list-level:
`awesome/lists.py` already derives separate list-level `topics` from repository metadata; this is a
different, per-entry signal used only for search matching.

This is a deliberately small, disclosed heuristic (like `awesome.lists.classify`), not a claim of
authoritative taxonomy. Unmapped category labels still normalize (casefold, de-punctuate,
hyphenate) rather than being dropped, so search matching degrades gracefully to normalized-text
matching for categories outside the synonym table.
"""
from __future__ import annotations

import re

_STOPWORDS = {"and", "the", "a", "an", "of", "for", "with", "your"}

# Deliberately small and reviewable; extend as real cross-list category variance is observed.
# Keys are the fully-normalized (casefolded, stopword-stripped, space-joined) source phrase.
_SYNONYMS = {
    "ml": "machine-learning",
    "machine learning": "machine-learning",
    "artificial intelligence": "machine-learning",
    "ai": "machine-learning",
    "deep learning": "machine-learning",
    "neural networks": "machine-learning",
    "self hosted": "self-hosting",
    "selfhosted": "self-hosting",
    "self hosting": "self-hosting",
    "devops": "devops",
    "ci cd": "devops",
    "continuous integration": "devops",
    "js": "javascript",
    "javascript": "javascript",
    "typescript": "javascript",
    "nodejs": "javascript",
    "node js": "javascript",
    "py": "python",
    "python": "python",
    "front end": "frontend",
    "frontend": "frontend",
    "user interface": "frontend",
    "ui": "frontend",
    "back end": "backend",
    "backend": "backend",
    "server side": "backend",
    "database": "databases",
    "databases": "databases",
    "db": "databases",
    "security": "security",
    "infosec": "security",
    "cybersecurity": "security",
    "cloud computing": "cloud",
    "cloud": "cloud",
    "containers": "containers",
    "docker": "containers",
    "kubernetes": "containers",
    "k8s": "containers",
    "data science": "data-science",
    "data analysis": "data-science",
    "photo gallery": "photos",
    "photography": "photos",
    "photos": "photos",
    "images": "photos",
}


def normalize_topic(label: str) -> str:
    """Map one raw category/topic label to a single canonical tag, or "" for an empty label."""
    if not label:
        return ""
    text = re.sub(r"[/_]+", " ", label.casefold())
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [word for word in text.split() if word not in _STOPWORDS]
    if not words:
        return ""
    joined = " ".join(words)
    return _SYNONYMS.get(joined, "-".join(words))


def normalized_topics(occurrences: list[dict], limit: int = 6) -> list[str]:
    """Deduplicated, order-preserving canonical topic tags aggregated across a project's
    occurrences' own `category` text -- capped at `limit` so a heavily-cited project's topic list
    stays small and reviewable rather than accumulating every raw category variant seen."""
    tags: list[str] = []
    for occurrence in occurrences:
        tag = normalize_topic(occurrence.get("category", ""))
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags
