"""Pure cross-list project search filtering/ranking; no networking or runtime writes.

Operates over the already-published, offline-computed search index records
(`awesome.search_index`) -- title, list_count, independent_list_count, topics -- loaded once by the
hosted session and cached; this module performs only lightweight text matching/scoring live,
consistent with this product's "no live computation in the hosted session" contract. Nothing here
recomputes `independent_list_count` or `topics`; those are offline, precomputed facts.

Ranking is text relevance ONLY (adapted from `awesome.catalogue.search`'s all-terms-must-match
filter, extended with a simple transparent score instead of filter-only). `list_count` and
`independent_list_count` never influence ranking or the match/no-match decision -- they are
surfaced strictly as separate, honestly-labeled provenance/context (see `citation_label`), per this
issue's redesign: raw or discounted citation counts must never function as an implicit
trust-based ranking signal (issue #65's finding).
"""
from __future__ import annotations


def _haystack(record: dict) -> str:
    return " ".join([record["title"], *record.get("topics", [])]).casefold()


def relevance(record: dict, terms: list[str]) -> int:
    """A small, transparent relevance score: an exact full-phrase title match scores highest, then
    per-term title hits, then per-term normalized-topic hits (the A4 semantic-matching signal)."""
    title = record["title"].casefold()
    topics_text = " ".join(record.get("topics", [])).casefold()
    score = 0
    phrase = " ".join(terms)
    if phrase and phrase in title:
        score += 10
    for term in terms:
        if term in title:
            score += 3
        if term in topics_text:
            score += 1
    return score


def search_projects(records: list[dict], query: str, limit: int = 50) -> list[dict]:
    """Filter to records matching every query term (title or normalized topics -- the same
    all-terms-must-match discipline as `awesome.catalogue.search`), rank by text relevance only,
    and cap to `limit` results. `query` is case-insensitive, whitespace-split, and capped like the
    rest of this product's search inputs. An empty query returns no results (this is a directed
    search view, not a full-catalogue browse -- `Discover`/`Insights` already cover that)."""
    terms = query[:200].casefold().split()
    if not terms:
        return []
    matches = [record for record in records if all(term in _haystack(record) for term in terms)]
    ranked = sorted(matches, key=lambda record: (-relevance(record, terms), record["title"].casefold(), record["id"]))
    return ranked[:limit]


def citation_label(list_count: int, independent_list_count: int) -> dict:
    """Honest secondary-signal labeling -- this issue's core redesign per #65's finding. Only ever
    claims independence when the copy-lineage-discounted count shows real evidence of it (>= 2
    independent clusters). Otherwise discloses the raw citation count with NO trust/quality
    framing at all -- it never silently falls back to presenting the raw list_count as if it were a
    validated agreement signal. Returns `{"kind", "text"}`; `kind` lets the UI style the three
    cases distinctly without re-deriving the classification."""
    if list_count <= 1:
        return {"kind": "single", "text": "Listed in 1 source."}
    if independent_list_count >= 2:
        return {
            "kind": "independent",
            "text": (f"Cited independently by {independent_list_count} of {list_count} listed "
                     "sources (sibling/copy-lineage citations discounted; see methodology)."),
        }
    return {
        "kind": "raw-only",
        "text": (f"Listed in {list_count} sources (citation text is shared/copy-lineage across "
                 "them; not shown as an independence signal -- see methodology)."),
    }
