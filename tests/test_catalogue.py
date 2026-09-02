import copy
import hashlib
import json
from pathlib import Path

import pytest
from awesome.catalogue import digest, load_catalogue, qualifies, safe_url, search, validate_catalogue
from tools.crawl import MAX_README, extract, merge_records, publish


@pytest.mark.parametrize("url", ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x",
    "file:///etc/passwd", "//example.com/x", "https://user:pass@example.com", "https://localhost/a",
    "https://127.0.0.1", "http://10.0.0.1", "http://[::1]", "https://a.local", "http://127.1",
    "https://example.com/%0a", "https://example.com\\evil", "https://bad_host.com", "https://example.com:bad", ""])
def test_unsafe_urls(url):
    assert safe_url(url) is None


def test_conservative_url_normalization():
    assert safe_url("HTTPS://Example.COM:443/Case?q=X#section") == "https://example.com/Case?q=X#section"
    assert safe_url("https://example.com/Case") != safe_url("https://example.com/case")
    assert safe_url("https://example.com/?q=x") != safe_url("https://example.com/?q=y")


@pytest.mark.parametrize("stars,expected", [(49999, False), (50000, True), (50001, True), (None, False), ("50000", False), (True, False)])
def test_threshold(stars, expected):
    assert qualifies({"stars": stars, "public": True, "is_resource_list": True}) is expected


def test_private_and_nonlist_rejected():
    assert not qualifies({"stars": 90000, "public": False, "is_resource_list": True})
    assert not qualifies({"stars": 90000, "public": True, "is_resource_list": False})


def test_markdown_coverage_and_safety():
    markdown = """# Tools
- [**Café**](https://example.com/Case) - Useful `code`.
  - [Nested][ref]
- ![Badge](https://example.com/image.png) [Real](https://example.com/real)
- <script>alert('x')</script><a href="https://example.com/html">HTML</a>
- [Unsafe](javascript:alert(1))
- [Anchor](#section)
- [Relative](docs/local.md)

```md
- [Code](https://example.com/code)
```

[ref]: https://example.com/ref
"""
    records = extract(markdown, "owner/list")
    assert [r["title"] for r in records] == ["Café", "Nested", "Real"]
    assert records[0]["line"] == 2
    assert records[0]["category"] == "Tools"
    assert records[0]["description"] == "Useful code."
    assert not extract("", "x")
    with pytest.raises(ValueError, match="budget"):
        extract("x" * (MAX_README + 1), "x")


def test_dedup_preserves_occurrences_and_determinism():
    first = extract("- [Thing](https://example.com/a)", "a/list")
    second = extract("- [Thing](https://example.com/a)", "b/list")
    merged = merge_records(first + second + first)
    assert len(merged) == 1
    assert len(merged[0]["occurrences"]) == 2
    assert merge_records(first + second) == merge_records(first + second)


def test_search_literal_unicode_and_source():
    items = merge_records(extract("- [Café [tool]](https://example.com/a) - Rust testing", "a/list"))
    assert search(items, "CAFÉ testing") == items
    assert search(items, "   ") == items
    assert search(items, "[tool]") == items
    assert not search(items, ".*")
    assert not search(items, "", "other/list")


def test_published_provenance_and_digest():
    data = load_catalogue(Path("data/catalogue.json"))
    assert len(data["sources"]) == 3
    assert len(data["resources"]) > 100
    tampered = copy.deepcopy(data)
    tampered["resources"][0]["title"] = "changed"
    with pytest.raises(ValueError, match="digest"):
        validate_catalogue(tampered)
    for field, value in [("stars", 49999), ("revision", "main"), ("license", "unknown")]:
        tampered = copy.deepcopy(data)
        tampered["sources"][0][field] = value
        tampered["digest"] = digest({k: v for k, v in tampered.items() if k != "digest"})
        with pytest.raises(ValueError):
            validate_catalogue(tampered)


def test_stale_publication_preserves_last_good(tmp_path, monkeypatch):
    import tools.crawl as crawler
    data = load_catalogue(Path("data/catalogue.json"))
    stage, published = tmp_path / "candidate.json", tmp_path / "published.json"
    stage.write_text(json.dumps(data), encoding="utf-8")
    published.write_text("last-good", encoding="utf-8")
    monkeypatch.setattr(crawler, "STAGING", stage)
    monkeypatch.setattr(crawler, "PUBLISHED", published)
    with pytest.raises(ValueError, match="Stale acceptance"):
        publish("not-the-reviewed-digest")
    assert published.read_text() == "last-good"


@pytest.mark.parametrize("field", ["title", "description", "category"])
def test_occurrence_text_shape(field):
    data = load_catalogue(Path("data/catalogue.json"))
    data["resources"][0]["occurrences"][0][field] = None
    data["digest"] = digest({k: v for k, v in data.items() if k != "digest"})
    with pytest.raises(ValueError, match="occurrence text"):
        validate_catalogue(data)
