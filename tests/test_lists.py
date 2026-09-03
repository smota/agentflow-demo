import copy
import json
from pathlib import Path

import pytest

from awesome.catalogue import digest
from awesome.lists import classify, parse_readme, profile, freshness, validate_index, validate_detail, topics

REV = "a" * 40
MD = "# Awesome things\nA curated list of useful resources.\n\n## Tools\n" + "\n".join(
    f"- [Tool {i}](https://example.org/tool/{i}) - Descriptive prose not republished." for i in range(5))


def meta(**values):
    return {"id": "123", "name": "owner/awesome-tools", "url": "https://github.com/owner/awesome-tools",
            "description": "A curated list of tools", "public": True, "stars": 100, "forks": 0,
            "observed_at": "2026-09-03T00:00:00Z", "revision": REV, "readme_path": "README.md",
            "readme_sha256": "b" * 64, "github_topics": [], **values}


@pytest.mark.parametrize("stars,state", [(99, "excluded"), (100, "eligible"), (50000, "eligible"), (None, "pending"), (True, "pending")])
def test_threshold(stars, state):
    parsed = parse_readme(MD, "owner/awesome-tools", REV)
    assert classify(meta(stars=stars), parsed, MD)[0] == state


def test_selfhosted_no_allowlist_or_license_requirement():
    data = meta(name="awesome-selfhosted/awesome-selfhosted", description="A list of Free Software network services and web applications which can be hosted on your own servers", license="NOASSERTION")
    assert classify(data, parse_readme(MD, data["name"], REV), MD)[0] == "eligible"


def test_awesome_app_with_documentation_is_not_eligible():
    app = "# Awesome App\nAn application to manage projects.\n## Documentation\n" + "\n".join(f"- [Guide {i}](https://docs.example.com/{i})" for i in range(10))
    assert classify(meta(description="A project management application"), parse_readme(app, "owner/awesome-app", REV), app)[0] == "pending"


def test_incidental_curated_phrase_is_not_primary_purpose():
    app = "# Awesome App\nAn app to manage projects. See our curated list of plugins below.\n## Documentation\n" + "\n".join(f"- [Guide {i}](https://docs.example.com/{i})" for i in range(5))
    assert classify(meta(description="A project management application"), parse_readme(app, "owner/awesome-app", REV), app)[0] == "pending"


def test_private_profile_never_contains_content():
    item, detail = profile(meta(public=False), parse_readme(MD, "owner/awesome-tools", REV), MD)
    assert detail is None and item["detail"] is None and item["entry_count"] is None


def test_unsupported_and_private():
    assert classify(meta(), None)[0] == "pending"
    assert classify(meta(public=False), None)[0] == "excluded"


def test_hierarchy_and_description_not_copied():
    parsed = parse_readme(MD + "\n### Subcategory\n- [Other](https://other.example.org)\n", "owner/awesome-tools", REV)
    assert parsed["entry_count"] == 6
    assert parsed["sections"][-1]["path"] == ["Awesome things", "Tools", "Subcategory"]
    assert parsed["entries"][-1]["category"] == "subcategory"
    assert "Descriptive prose" not in json.dumps(parsed)


def test_tables_properties_and_unsafe_badges():
    table = "# A curated list\n## Databases\n| Name | Language | Description |\n|---|---|---|\n| [Database](https://example.org/db) | Rust | Copyrighted long prose |\n"
    parsed = parse_readme(table, "owner/awesome-db", REV)
    assert parsed["entries"][0]["properties"] == {"Language": "Rust"}
    assert parsed["entry_count"] == 1
    assert parse_readme("- [![Badge](https://img.example/a.svg)](https://badgen.net/x)\n- [Bad](javascript:alert(1))\n- [Internal](#contents)", "a/b", REV)["entry_count"] == 0


def test_skip_contents_and_installation():
    text = "## Contents\n- [Index](#index)\n## Installation\n- [Installer](https://example.org/install)\n" + MD
    assert parse_readme(text, "a/b", REV)["entry_count"] == 5


def test_duplicate_heading_anchor_and_nested_list():
    parsed = parse_readme("## Tools\n- [First](https://example.org/a)\n  - [Second](https://example.org/b)\n## Tools\n- [Third](https://example.org/c)", "a/b", REV)
    assert parsed["entry_count"] == 3
    assert parsed["sections"][-1]["id"] == "tools-1"


def test_invalid_identity():
    with pytest.raises(ValueError):
        parse_readme(MD, "../evil", REV)
    with pytest.raises(ValueError):
        parse_readme("x" * (2 * 1024 * 1024 + 1), "a/b", REV)


def test_freshness_unknown_and_half_life():
    assert freshness(None, "2026-09-03T00:00:00Z")["index"] is None
    assert freshness("bad", "bad")["days"] is None
    assert freshness("2026-03-07T00:00:00Z", "2026-09-03T00:00:00Z")["index"] == 50


def test_topics_additional_not_replacing_taxonomy():
    assert "Self-hosting & infrastructure" in topics(meta(description="A list of self-hosted tools"))


def build_index():
    item, detail = profile(meta(), parse_readme(MD, "owner/awesome-tools", REV), MD)
    index = {"format_version": 2, "min_stars": 100, "lists": [item], "counts": {"eligible": 1}}
    index["digest"] = digest(index)
    return index, detail


def test_validation_and_unknown_metrics(tmp_path):
    index, detail = build_index(); item = index["lists"][0]
    assert item["contributors_count"] is None and item["forks"] == 0
    path = tmp_path / item["detail"]; path.parent.mkdir(); path.write_text(json.dumps(detail), encoding="utf-8")
    validate_index(index, tmp_path)
    detail["entries"][0]["title"] = "tampered"
    with pytest.raises(ValueError):
        validate_detail(detail, item)


@pytest.mark.parametrize("field,value", [("detail", "../../secret"), ("stars", -1), ("url", "http://127.0.0.1/x")])
def test_malformed_index(field, value):
    index, _ = build_index(); index["lists"][0][field] = value
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    with pytest.raises(ValueError):
        validate_index(index)
