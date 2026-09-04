"""H3 (issue #53): headless-CLI-assisted entry-level category/topic normalization for raw category
labels `awesome.topics.normalize_topic`'s disclosed synonym table does not already cover -- feeding
Epic A's/D's existing topic surfaces (`awesome.search_index.derive_shard_record`, A3/A4) WITHOUT
replacing the deterministic synonym table: `normalize_topic()` always tries `_SYNONYMS` first, and
only ever consults this module's CLI-derived overlay for a label the synonym table itself declined
to map (see `awesome.topics.normalize_topic`'s `overrides` parameter). A synonym-table hit is never
overridden by this module's output, and this module never mutates `awesome.topics._SYNONYMS` itself.

Bounded, closed-vocabulary output: unlike H2's free-text eligibility opinion, this module constrains
the CLI to choose ONE tag from the SAME small canonical vocabulary `awesome.topics._SYNONYMS`
already publishes (or the literal string "none" when no existing canonical tag plausibly fits) --
never an invented new tag -- so the normalized topic vocabulary stays the same small, reviewable set
`awesome/topics.py`'s own docstring commits to, and this CLI step cannot silently grow taxonomy
sprawl. A label is cached forever once classified (a raw label string's own meaning never changes),
unlike H2's per-repository record, which can go stale when the repository's own content changes.
"""
from __future__ import annotations

import re

from awesome.catalogue import digest
from awesome.topics import _SYNONYMS, _STOPWORDS

FORMAT = 1
CANONICAL_TAGS = sorted(set(_SYNONYMS.values()))
CONFIDENCES = ("high", "medium", "low")

SCHEMA = {
    "type": "object",
    "properties": {
        "tag": {"type": "string", "enum": CANONICAL_TAGS + ["none"]},
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
    },
    "required": ["tag", "confidence"],
}

CONTENT_POLICY = (
    "Each record maps one raw, already-normalized-to-phrase category label (the same casefolded, "
    "stopword-stripped phrase awesome.topics.normalize_topic() computes before consulting its own "
    "_SYNONYMS table) to a headless-CLI-chosen tag from that SAME closed canonical vocabulary, or "
    "'none' if no existing tag plausibly fits -- the CLI can never introduce a tag outside this "
    "fixed set. Records are consulted by normalize_topic() only as a fallback AFTER _SYNONYMS -- a "
    "label already resolved by _SYNONYMS is never looked up here, and this module never overrides "
    "that table's own output. A label maps to 'none' means the CLI found no plausible canonical fit "
    "for it, not that it was skipped."
)


def normalized_label(label: str) -> str:
    """The exact fallback lookup key `awesome.topics.normalize_topic` computes for an unmapped
    label, duplicated here (not imported) only because `normalize_topic` does not expose its
    internal joined-phrase form as a standalone function; kept in lockstep by
    `tests/test_interpret_topics.py`'s direct comparison against `awesome.topics.normalize_topic`'s
    own observed fallback behaviour."""
    text = re.sub(r"[/_]+", " ", (label or "").casefold())
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [word for word in text.split() if word not in _STOPWORDS]
    return " ".join(words)


def label_digest(label_key: str) -> str:
    return digest({"label": label_key})


def build_prompt(label_key: str) -> str:
    vocab = ", ".join(CANONICAL_TAGS)
    return (
        "You are assisting an offline catalogue pipeline that tags curated 'Awesome list' README "
        "entries with a small, fixed set of canonical topic tags for search matching.\n\n"
        f"Canonical tags (choose exactly one, or \"none\"): {vocab}\n\n"
        f"Raw entry category label (already lowercased, punctuation-stripped): \"{label_key}\"\n\n"
        "Which single canonical tag best matches this raw label's likely subject area? If none of "
        "the canonical tags plausibly fit, answer \"none\" rather than guessing. Respond with the "
        "requested JSON object only."
    )


def validate_interpretations(data: dict) -> None:
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported topic interpretations artifact format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Topic interpretations artifact digest mismatch")
    seen = set()
    for record in data.get("records", []):
        label_key = record.get("label")
        if not label_key or label_key in seen:
            raise ValueError("Duplicate or missing topic interpretation label")
        seen.add(label_key)
        tag = record.get("tag")
        if tag != "none" and tag not in CANONICAL_TAGS:
            raise ValueError("Topic interpretation tag outside the closed canonical vocabulary")
        if record.get("confidence") not in CONFIDENCES:
            raise ValueError("Invalid topic interpretation confidence")
        if not isinstance(record.get("model"), str) or record.get("source") != "headless-cli":
            raise ValueError("Incomplete topic interpretation record")
        if record.get("label_digest") != label_digest(label_key):
            raise ValueError("Topic interpretation label digest does not match its own label")
    if data.get("counts", {}).get("records") != len(data.get("records", [])):
        raise ValueError("Topic interpretation counts do not reconcile")


def as_overrides(data: dict) -> dict:
    """The small `{label_key: tag}` overlay `awesome.topics.normalize_topic(..., overrides=...)`
    consumes -- 'none' records are dropped (an explicit non-match is not an override)."""
    return {record["label"]: record["tag"] for record in data.get("records", []) if record["tag"] != "none"}
