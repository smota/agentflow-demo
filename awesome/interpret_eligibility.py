"""H2 (issue #53): headless-CLI-assisted classification for ambiguous `pending` list-eligibility
candidates.

Deliberate scope decision, disclosed here rather than silently assumed: this module's output is an
ADVISORY, SEPARATELY PUBLISHED annotation (`data/interpretations-index.json`), never an automatic
promotion of a `pending` item to `eligible`/`excluded` in the deterministic pipeline.
`awesome.lists.classify()` (issue #47's original heuristic: star threshold, curated-list-intent
regex, link-count) remains the sole author of `data/list-index.json`'s `state` field, completely
unchanged and untouched by this module -- matching issue #53's own bound ("do not let this become
open-ended agent orchestration of the whole pipeline"). Promoting a CLI-interpreted candidate into
the deterministic index would need its own explicitly scoped follow-up story with its own review,
not a side effect of this one.

Scope of "ambiguous": exactly the `pending` state's own candidates -- i.e. every list already
carrying `state == "pending"` in the published index, for whichever of `classify()`'s four
pending-reasons applies. `eligible`/`excluded` lists are never candidates; this module adds
interpretation only where the deterministic heuristic itself already declined to decide.

Traceability (issue #53 acceptance criteria: "every model-assisted decision ... is traceable"):
PRESENCE in `data/interpretations-index.json` -- not `data/list-index.json` -- is the signal. A
`pending` list absent from this artifact has never received CLI interpretation and remains
heuristic-only; a list present here carries `invoked_at`, `model`, and the exact
`candidate_digest` of what it was shown, so a stale record (candidate content changed since) is
detectable and never silently reused (see `tools/derive_interpretations.py`'s cache-key discipline).
"""
from __future__ import annotations

import re

from awesome.catalogue import digest

FORMAT = 1
CONFIDENCES = ("high", "medium", "low")

SCHEMA = {
    "type": "object",
    "properties": {
        "eligible": {"type": "boolean"},
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
        "reasoning": {"type": "string"},
    },
    "required": ["eligible", "confidence", "reasoning"],
}

CONTENT_POLICY = (
    "Every record here is an ADVISORY, headless-CLI-assisted eligibility opinion for one repository "
    "already classified 'pending' by awesome.lists.classify() (the deterministic heuristic, "
    "unchanged and unaffected by this module -- see awesome/interpret_eligibility.py). "
    "candidate_digest ties each record to the exact published list-index.json fields (and up to 8 "
    "sample README entry titles+categories from the list's own already-published detail shard) it "
    "was shown; a record whose candidate_digest no longer matches the currently published candidate "
    "is stale and must be recomputed, never reused. Presence in THIS artifact -- not "
    "data/list-index.json -- is the traceability signal for 'heuristic-only vs CLI-assisted, and "
    "when' (issue #53's acceptance criteria): a pending list absent here has never received CLI "
    "interpretation, and this artifact never changes list-index.json's own published state."
)

MAX_SAMPLE_ENTRIES = 8


def sample_entries(detail: dict | None, limit: int = MAX_SAMPLE_ENTRIES) -> list[dict]:
    if not detail:
        return []
    return [{"title": entry["title"], "category": entry["category"]}
            for entry in detail.get("entries", [])[:limit]]


def candidate_fields(item: dict, detail: dict | None) -> dict:
    """The exact, minimal, disclosed subset of a `pending` list-index item (+ its own already-
    published detail shard) shown to the headless CLI -- never more than what's already public in
    the published catalogue itself."""
    return {
        "name": item["name"], "description": item.get("description") or "",
        "github_topics": sorted(item.get("github_topics", [])), "stars": item.get("stars"),
        "reason": item.get("reason"), "entry_count": item.get("entry_count"),
        "unique_links": item.get("unique_links"), "category_count": item.get("category_count"),
        "sample_entries": sample_entries(detail),
    }


def candidate_digest(fields: dict) -> str:
    return digest(fields)


def build_prompt(fields: dict) -> str:
    lines = [
        "You are assisting an offline, deterministic catalogue pipeline for a directory of GitHub "
        "'Awesome' curated-resource lists. A heuristic classifier already marked this repository "
        "'pending' (ambiguous) rather than eligible or excluded, for the stated reason below. "
        "Decide, from the facts given ONLY, whether this repository is genuinely a curated resource "
        "list (an 'Awesome'-style list of links to other resources) as opposed to, e.g., a single "
        "software project, a tutorial, or a book. Do not browse the web or invent facts beyond what "
        "is given below.",
        "",
        f"Repository: {fields['name']}",
        f"Description: {fields['description'] or '(none)'}",
        f"GitHub topics: {', '.join(fields['github_topics']) or '(none)'}",
        f"Heuristic reason for 'pending': {fields['reason']}",
        f"Parsed README stats: entry_count={fields['entry_count']}, "
        f"unique_links={fields['unique_links']}, category_count={fields['category_count']}",
    ]
    if fields["sample_entries"]:
        lines.append("Sample parsed README entries (title -- category):")
        lines += [f"  - {entry['title']} -- {entry['category']}" for entry in fields["sample_entries"]]
    else:
        lines.append("No parsed README entries are available for this repository.")
    lines += ["", "Respond with the requested JSON object only."]
    return "\n".join(lines)


def validate_interpretations(data: dict, list_index: dict) -> None:
    if data.get("format_version") != FORMAT:
        raise ValueError("Unsupported interpretations artifact format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Interpretations artifact digest mismatch")
    lists_by_id = {item["id"]: item for item in list_index.get("lists", [])}
    seen = set()
    for record in data.get("records", []):
        list_id = record.get("list_id")
        if not list_id or list_id in seen:
            raise ValueError("Duplicate or missing interpretation record identity")
        seen.add(list_id)
        source_item = lists_by_id.get(list_id)
        if not source_item or source_item.get("state") != "pending":
            raise ValueError("Interpretation record does not match a currently pending list")
        if record.get("confidence") not in CONFIDENCES or not isinstance(record.get("eligible"), bool):
            raise ValueError("Invalid interpretation payload")
        if not record.get("reasoning") or not isinstance(record.get("model"), str):
            raise ValueError("Incomplete interpretation record")
        if not re.fullmatch(r"[0-9a-f]{64}", record.get("candidate_digest", "")):
            raise ValueError("Invalid candidate digest")
        if record.get("source") != "headless-cli":
            raise ValueError("Unknown interpretation source")
    if data.get("counts", {}).get("records") != len(data.get("records", [])):
        raise ValueError("Interpretation counts do not reconcile")
