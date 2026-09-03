import copy
import json
from pathlib import Path

import pytest

from awesome.catalogue import digest
from awesome.lists import FORMAT, classify, parse_readme, profile, freshness, validate_index, validate_detail, topics, source_data_links

REV = "a" * 40
@pytest.mark.parametrize("name", ["gege-circle/.github", "owner/_resources", "owner/-resources"])
def test_valid_repository_punctuation(name):
    assert parse_readme("# Resources", name, REV)["entry_count"] == 0


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


@pytest.mark.parametrize("name,description", [
    ("vinta/awesome-python", 'The definitive list that answers "I want to do X in Python, which tool should I use?"'),
    ("Solido/awesome-flutter", "An awesome list that curates the best Flutter libraries and tools."),
    ("sindresorhus/awesome-nodejs", "Delightful Node.js packages and resources"),
])
def test_general_awesome_identity_is_list_evidence(name, description):
    data = meta(name=name, description=description)
    assert classify(data, parse_readme(MD, name, REV), MD)[0] == "eligible"


def test_named_awesome_product_still_guarded():
    data = meta(name="owner/awesome-control", description="A local control plane for deploying applications")
    assert classify(data, parse_readme(MD, data["name"], REV), MD)[0] == "pending"


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
    derived = topics(meta(description="A list of self-hosted development tools"))
    assert derived[0] == "Self-hosting & infrastructure"


def test_labelled_source_data_only():
    assert source_data_links("Generated from [the public source data](https://example.org/data.json).") == ["https://example.org/data.json"]
    assert source_data_links("Unlabelled [link](https://example.org/data.json).") == []


def build_index():
    item, detail = profile(meta(), parse_readme(MD, "owner/awesome-tools", REV), MD)
    index = {"format_version": FORMAT, "min_stars": 100, "lists": [item], "counts": {"eligible": 1}}
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


def test_bounded_public_contributor_profile():
    observation = {"status": "observed", "description": "Sampled, not all-time.", "commit_limit": 100,
                   "observed_commits": 100, "has_more": True, "path_commit_count": 150,
                   "public_contributors": 2, "observed_at": "2026-09-03T00:00:00Z"}
    data = meta(content_updated_at="2026-09-02T00:00:00Z", contributors=[
        {"login": "alice", "url": "https://github.com/alice", "contributions": 70},
        {"login": "bob", "url": "https://github.com/bob", "contributions": 30}],
        contributor_observation=observation,
        contributing_url=f"https://github.com/owner/awesome-tools/blob/{REV}/CONTRIBUTING.md")
    item, detail = profile(data, parse_readme(MD, data["name"], REV), MD)
    assert item["contributors_count"] == 2 and item["freshness"]["days"] == 1
    assert "email" not in json.dumps(detail).casefold()
    validate_detail(detail, item)
    detail["contributors"][0]["email"] = "not-allowed@example.org"
    detail["digest"] = digest({k: v for k, v in detail.items() if k != "digest"})
    item["detail_digest"] = detail["digest"]
    with pytest.raises(ValueError, match="contributor"):
        validate_detail(detail, item)


@pytest.mark.parametrize("field,value", [("observed_commits", 101), ("path_commit_count", 99),
                                           ("public_contributors", -1), ("public_contributors", 101)])
def test_contributor_observation_bounds(field, value):
    index, detail = build_index(); item = index["lists"][0]
    observation = {"status": "observed", "description": "Bounded observation.", "commit_limit": 100,
                   "observed_commits": 100, "has_more": True, "path_commit_count": 150,
                   "public_contributors": 0, "observed_at": "2026-09-03T00:00:00Z"}
    observation[field] = value
    item["contributors_count"] = observation["public_contributors"]
    detail["contributor_observation"] = observation
    detail["digest"] = digest({k: v for k, v in detail.items() if k != "digest"})
    item["detail_digest"] = detail["digest"]
    with pytest.raises(ValueError, match="contributor observation"):
        validate_detail(detail, item)


@pytest.mark.parametrize("field,value", [("detail", "../../secret"), ("stars", -1), ("url", "http://127.0.0.1/x")])
def test_malformed_index(field, value):
    index, _ = build_index(); index["lists"][0][field] = value
    index["digest"] = digest({k: v for k, v in index.items() if k != "digest"})
    with pytest.raises(ValueError):
        validate_index(index)


@pytest.mark.parametrize("field,value", [("name", "different/repo"), ("revision", "c"*40), ("readme_path", "other.md"), ("readme_sha256", "d"*64)])
def test_detail_binds_exact_source_identity(field, value):
    index, detail = build_index(); item = index["lists"][0]
    detail[field] = value
    detail["digest"] = digest({k: v for k, v in detail.items() if k != "digest"})
    item["detail_digest"] = detail["digest"]
    with pytest.raises(ValueError, match="source identity"):
        validate_detail(detail, item)


@pytest.mark.parametrize("target", ["sections", "entries"])
@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://example.org/not-the-source", "https://github.com/owner/awesome-tools/blob/main/README.md"])
def test_detail_binds_safe_pinned_provenance(target, url):
    index, detail = build_index(); item = index["lists"][0]
    detail[target][0]["source_url"] = url
    detail["digest"] = digest({k: v for k, v in detail.items() if k != "digest"})
    item["detail_digest"] = detail["digest"]
    with pytest.raises(ValueError): validate_detail(detail, item)
