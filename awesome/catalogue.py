"""Pure catalogue validation and search; no networking or runtime writes."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

MAX_BYTES = 10 * 1024 * 1024
MAX_RESOURCES = 10_000
MIN_STARS = 50_000


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def safe_url(value) -> str | None:
    """Conservative canonicalization, not an endorsement of destination content.

    Callers across this codebase pass arbitrary, sometimes-untrusted JSON values (any type, not
    just `str`) -- the type/length guard below must run uncached and outside `lru_cache` so a
    non-hashable value (a `list`/`dict` from malformed input) returns `None` exactly as before
    instead of raising `TypeError` when used as a cache key. Only validated, hashable strings reach
    the cached implementation, which memoizes the expensive part (IDNA encoding, `ipaddress`
    parsing, regex) -- a real win at this catalogue's scale, where the same handful of popular
    project URLs are revalidated many times over (e.g. once per list that cites them, and once per
    place they appear as another project's "see alternatives" match)."""
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    return _safe_url_cached(value)


@lru_cache(maxsize=2_000_000)
def _safe_url_cached(value: str) -> str | None:
    if "\\" in value or any(ord(c) < 33 or ord(c) == 127 for c in value):
        return None
    decoded = unquote(value)
    if "\\" in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or parts.username or parts.password:
            return None
        host = (parts.hostname or "").rstrip(".").encode("idna").decode().lower()
        port = parts.port
        if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return None
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
            netloc = f"[{host}]" if address.version == 6 else host
        except ValueError:
            labels = host.split(".")
            if len(labels) < 2 or len(host) > 253 or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            ) or labels[-1].isdigit():
                return None
            netloc = host
        scheme = parts.scheme.lower()
        if port and port != (443 if scheme == "https" else 80):
            netloc += f":{port}"
        return urlunsplit((scheme, netloc, parts.path or "/", parts.query, parts.fragment))
    except (ValueError, UnicodeError):
        return None


def qualifies(source: dict) -> bool:
    stars = source.get("stars")
    return (type(stars) is int and stars >= MIN_STARS
            and source.get("public") is True and source.get("is_resource_list") is True)


def validate_catalogue(data: dict) -> None:
    if data.get("format_version") != 1:
        raise ValueError("Unsupported catalogue format")
    if data.get("digest") != digest({k: v for k, v in data.items() if k != "digest"}):
        raise ValueError("Catalogue digest mismatch")
    sources = {s["id"]: s for s in data["sources"]}
    if not sources or len(sources) != len(data["sources"]):
        raise ValueError("Missing or duplicate sources")
    for source in sources.values():
        if not qualifies(source) or source.get("license") != "CC0-1.0":
            raise ValueError("Unqualified source")
        for field in ("observed_at", "extracted_at", "readme_path", "license_path", "queries"):
            if not source.get(field):
                raise ValueError(f"Missing source provenance: {field}")
        if not re.fullmatch(r"[0-9a-f]{40}", source.get("revision", "")):
            raise ValueError("Unpinned source")
        if not re.fullmatch(r"[0-9a-f]{64}", source.get("readme_sha256", "")):
            raise ValueError("Missing README digest")
        license_hash = hashlib.sha256(source["license_text"].encode()).hexdigest()
        if license_hash != source.get("license_sha256"):
            raise ValueError("License digest mismatch")
    records = data["resources"]
    if not records or len(records) > MAX_RESOURCES:
        raise ValueError("Catalogue count outside budget")
    ids, urls = set(), set()
    for item in records:
        url = safe_url(item["url"])
        if not url or url != item["url"] or item["id"] != hashlib.sha256(url.encode()).hexdigest()[:20]:
            raise ValueError("Invalid resource identity or URL")
        if item["id"] in ids or url in urls or not item.get("title"):
            raise ValueError("Duplicate or unnamed resource")
        ids.add(item["id"])
        urls.add(url)
        if not item.get("occurrences"):
            raise ValueError("Unattributed resource")
        for occurrence in item["occurrences"]:
            if occurrence["source"] not in sources or occurrence.get("line", 0) < 1:
                raise ValueError("Invalid occurrence provenance")
            if (not occurrence.get("title") or
                    any(not isinstance(occurrence.get(field), str)
                        for field in ("title", "description", "category"))):
                raise ValueError("Invalid occurrence text")
    if len(json.dumps(data, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("Catalogue byte budget exceeded")


def load_catalogue(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Catalogue too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_catalogue(data)
    return data


def search(resources: list[dict], query: str = "", source: str = "All sources") -> list[dict]:
    terms = query[:200].casefold().split()
    return [r for r in resources
            if (source == "All sources" or any(o["source"] == source for o in r["occurrences"]))
            and all(term in " ".join([r["title"], r["description"], r["url"],
                                     *[o["category"] for o in r["occurrences"]]]).casefold()
                    for term in terms)]
