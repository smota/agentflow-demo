from urllib.parse import parse_qs, urlsplit
from pathlib import Path
from awesome.catalogue import load_catalogue
import pytest
from awesome.navigation import DEFAULTS, discover, matching_occurrences, normalize, page_slice, share_url


@pytest.mark.parametrize("page", ["-1", "0", "1.5", "no", "999999999999999999", "١", ["2", "3"]])
def test_invalid_pages(page):
    assert normalize({"page": page}, [], [])["page"] == 1


@pytest.mark.parametrize("count,page,expected", [(0,1,(1,1,0,0)), (1,3,(1,1,0,1)),
    (24,2,(1,1,0,24)), (25,2,(2,2,24,25)), (48,2,(2,2,24,48)), (48,-1,(1,2,0,24))])
def test_page_boundaries(count, page, expected):
    assert page_slice(count, page) == expected


def test_normalization_and_round_trip():
    state = normalize({"q": " café & rust / <b> ", "source": "A", "topic": "X", "page": "2",
                       "view": "Sources", "sort": "Title Z–A", "token": "must-not-share"}, ["A"], ["X"])
    params = {k: v[0] for k, v in parse_qs(urlsplit(share_url(state)).query).items()}
    assert normalize(params, ["A"], ["X"]) == state
    assert "token" not in params
    assert len(normalize({"q": "x" * 201}, [], [])["q"]) == 200
    assert normalize({"q": "\n\r\t", "source": "bad", "sort": "bad"}, [], []) == DEFAULTS


def test_same_occurrence_and_deterministic_sort():
    item = {"title": "a", "url": "https://a.example/", "description": "", "occurrences":
            [{"source": "A", "category": "X", "title": "a", "description": ""},
             {"source": "B", "category": "Y", "title": "a", "description": ""}]}
    assert not discover([item], {**DEFAULTS, "source": "A", "topic": "Y"})
    assert matching_occurrences(item, "B", "Y") == [item["occurrences"][1]]
    other = {**item, "url": "https://b.example/"}
    assert [r["url"] for r in discover([other, item], DEFAULTS)] == [item["url"], other["url"]]
    assert [r["url"] for r in discover([item, other], {**DEFAULTS, "sort": "Title Z–A"})] == [other["url"], item["url"]]


def test_real_corpus_uses_filtered_occurrence_text_and_search():
    data = load_catalogue(Path(__file__).resolve().parents[1] / "data/catalogue.json")
    state = {**DEFAULTS, "source": "rust-unofficial/awesome-rust", "topic": "Registries"}
    result = next(r for r in discover(data["resources"], state) if r["url"] == "https://crates.io/")
    assert result["title"] == "Crates"
    assert result["description"] == "The official public registry for Rust/Cargo."
    assert discover([result], {**state, "q": "official public registry"})
