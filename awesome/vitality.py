"""Pure Epic E aggregation (E1/#70): joins a deduplicated project record (#69) with the published
liveness (#71), usage (#72) and alternatives (#73) artifacts into one profile object, plus a pure
liveness classification used to give liveness the most visually prominent treatment of any Epic E
signal (the maintainer-confirmed gate). No network calls, no Streamlit imports, no file I/O --
`awesome/list_ui.py` owns loading shards and rendering; this module only defines the join and the
disclosed liveness buckets so both stay independently testable.
"""
from __future__ import annotations

from datetime import datetime, timezone

LIVENESS_BUCKETS = ("active", "slowing", "stale", "archived", "unknown")


def project_profile(project_record: dict, liveness_record: dict | None = None,
                     usage_record: dict | None = None, alternatives_record: dict | None = None) -> dict:
    """Join already-loaded, already-validated per-project records for the same project id.

    Each of `liveness_record`/`usage_record`/`alternatives_record` may be `None` -- "not yet
    observed/computed", never a synthesized zero or default. Callers own resolving and loading each
    artifact for this exact project id before calling this."""
    return {
        "id": project_record["id"], "url": project_record["url"], "title": project_record["title"],
        "list_count": project_record["list_count"], "occurrence_count": project_record["occurrence_count"],
        "occurrences": project_record["occurrences"],
        "liveness": liveness_record, "usage": usage_record, "alternatives": alternatives_record,
    }


def liveness_status(liveness_record: dict | None, now: datetime | None = None) -> dict:
    """Bucket a liveness record for a consistent, prominent UI treatment. The bucket is a disclosed
    classification of an observed fact (push recency / archived flag), never an invented score --
    the same convention this app already uses for list content freshness ranges."""
    if liveness_record is None:
        return {"bucket": "unknown", "label": "Not yet observed", "days_since_commit": None}
    if liveness_record.get("archived"):
        return {"bucket": "archived", "label": "Archived by its owner", "days_since_commit": None}
    last = liveness_record.get("last_commit_at")
    if not last:
        return {"bucket": "unknown", "label": "No push activity observed", "days_since_commit": None}
    reference = now or datetime.now(timezone.utc)
    observed = datetime.fromisoformat(last.replace("Z", "+00:00"))
    days = (reference - observed).days
    if days <= 90:
        bucket, label = "active", "Active"
    elif days <= 365:
        bucket, label = "slowing", "Slowing down"
    else:
        bucket, label = "stale", "Inactive"
    return {"bucket": bucket, "label": label, "days_since_commit": days}


def usage_total(usage_record: dict | None) -> dict:
    """Sum observed counts across matched registries for a compact display total, while keeping
    every individual source (registry, metric, count) intact and inspectable -- the total is a
    convenience view over disclosed facts, not a new synthesized number."""
    if not usage_record or not usage_record.get("sources"):
        return {"observed": False, "sources": []}
    return {"observed": True, "sources": usage_record["sources"]}
