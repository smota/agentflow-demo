"""A2 spike: sample high cross-list-occurrence projects and score independent-curation vs.
copy-lineage evidence in the citing lists' own parsed entry text.

Local-only analysis tool; not part of the publish pipeline and never imported by the hosted UI.
Reuses `tools.derive_projects`'s already-validated in-memory derivation (never re-parses the large
published `data/project-index.json` file) so this can be re-run cheaply against any generation.

Method (see issue: qa: validate cross-list co-occurrence as a curation-independence signal):

1. Sample N projects by highest `list_count` (the population most likely to matter for a ranked
   view) plus a separate stratified random sample at lower occurrence counts (>=2), so the finding
   is not just about the most-viral tail.
2. For each sampled project, compare every pair of citing lists' own entry text for that project:
   - `title_similarity`: difflib.SequenceMatcher ratio on normalized (casefolded,
     whitespace-collapsed) entry titles. Near-1.0 across a pair is a copy-lineage signal (the same
     wording was reused); a meaningfully lower ratio is an independent-curation signal (a different
     curator described/titled the entry differently).
   - `category_match`: whether the two lists filed the entry under the same-looking category label
     (weak signal on its own; wording/category conventions can coincidentally converge).
   - `explicit_source_link`: whether either citing list's own README declares (via
     `awesome.lists.source_data_links`, already captured in its detail shard as
     `source_data_links`) a link to the other citing list's repository -- the strongest, most direct
     copy-lineage evidence when present, since it is the list's own stated provenance, not inferred.
3. Classify each sampled project's strongest pairwise evidence as `likely-copy-lineage`
   (title_similarity >= 0.92, or an explicit_source_link is present),
   `likely-independent-curation` (title_similarity < 0.6), or `ambiguous` (in between).

This is a factual, disclosed heuristic -- like every other classification in this pipeline
(`awesome/lists.py`'s `classify`) -- not a claim of certainty about actual curator behavior.
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import re
from pathlib import Path

from tools.derive_projects import load_details, load_index
from awesome.projects import derive_projects
from tools.lists import now

ROOT = Path(__file__).resolve().parents[1]
COPY_THRESHOLD = 0.92
INDEPENDENT_THRESHOLD = 0.60


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def pairwise_evidence(occurrences: list[dict], list_source_links: dict[str, list[str]],
                       list_urls: dict[str, str]) -> dict:
    """Compare every pair of DIFFERENT citing lists. Two entries from the same list (a URL cited
    twice in one README, e.g. under two categories) are not cross-list co-occurrence evidence at
    all and must not be compared here -- see the list_count/occurrence_count split in
    awesome.projects.derive_projects."""
    best = {"title_similarity": 0.0, "pair": None, "explicit_source_link": False}
    for i in range(len(occurrences)):
        for j in range(i + 1, len(occurrences)):
            a, b = occurrences[i], occurrences[j]
            if a["list_id"] == b["list_id"]:
                continue
            ratio = difflib.SequenceMatcher(None, normalize(a["title"]), normalize(b["title"])).ratio()
            explicit = (list_urls.get(a["list_id"]) in list_source_links.get(b["list_id"], [])
                        or list_urls.get(b["list_id"]) in list_source_links.get(a["list_id"], []))
            if explicit or ratio > best["title_similarity"]:
                best = {"title_similarity": round(ratio, 3),
                        "pair": [a["list_name"], b["list_name"]],
                        "category_match": a["category"] == b["category"],
                        "explicit_source_link": explicit}
    return best


def classify(evidence: dict) -> str:
    if evidence["explicit_source_link"] or evidence["title_similarity"] >= COPY_THRESHOLD:
        return "likely-copy-lineage"
    if evidence["title_similarity"] < INDEPENDENT_THRESHOLD:
        return "likely-independent-curation"
    return "ambiguous"


def sample_projects(projects: list[dict], top_n: int, random_n: int, min_count: int, seed: int) -> list[dict]:
    eligible = [p for p in projects if p["list_count"] >= min_count]
    top = sorted(eligible, key=lambda p: (-p["list_count"], p["url"]))[:top_n]
    remaining = [p for p in eligible if p not in top]
    rng = random.Random(seed)
    random_sample = rng.sample(remaining, min(random_n, len(remaining)))
    return top, random_sample


def run(data_root: Path = ROOT / "data", top_n: int = 30, random_n: int = 30, min_count: int = 2,
        seed: int = 20260904) -> dict:
    index = load_index(data_root)
    details = load_details(index, data_root)
    derived = derive_projects(index, details, generated_at=now())
    # Occurrence detail (needed for the sampling/scoring below) lives only in the shards -- the
    # published top-level index carries no per-project rows at all (see
    # awesome.projects.derive_projects docstring: even a summary-only row per project would exceed
    # GitHub's single-file size limit at this catalogue's scale). Concatenating shards in dict order
    # groups projects by id-hash-prefix bucket, not by list_count -- sort explicitly so sample
    # selection depends only on (seed, min_count, top_n, random_n), never on shard bucket ordering.
    full_projects = [record for shard in derived["shards"].values() for record in shard["projects"]]
    full_projects.sort(key=lambda record: (-record["list_count"], -record["occurrence_count"], record["url"]))

    list_source_links, list_urls = {}, {}
    for item in index["lists"]:
        if item.get("state") == "eligible":
            list_urls[item["id"]] = item["url"]
            list_source_links[item["id"]] = details.get(item.get("detail"), {}).get("source_data_links", [])

    top, random_sample = sample_projects(full_projects, top_n, random_n, min_count, seed)

    def evaluate(projects: list[dict]) -> list[dict]:
        results = []
        for project in projects:
            evidence = pairwise_evidence(project["occurrences"], list_source_links, list_urls)
            results.append({"url": project["url"], "title": project["title"],
                             "list_count": project["list_count"],
                             "citing_lists": [o["list_name"] for o in project["occurrences"]],
                             "evidence": evidence, "classification": classify(evidence)})
        return results

    top_results, random_results = evaluate(top), evaluate(random_sample)
    all_results = top_results + random_results
    tally = {"likely-copy-lineage": 0, "likely-independent-curation": 0, "ambiguous": 0}
    for result in all_results:
        tally[result["classification"]] += 1

    histogram = {}
    for project in full_projects:
        histogram[project["list_count"]] = histogram.get(project["list_count"], 0) + 1

    return {
        "source_index_digest": index["digest"], "source_project_digest": derived["index"]["digest"],
        "total_projects": derived["index"]["counts"]["projects"],
        "total_occurrences": derived["index"]["counts"]["occurrences"],
        "list_count_histogram": dict(sorted(histogram.items())),
        "sample": {"top_n": len(top_results), "random_n": len(random_results), "min_count": min_count, "seed": seed},
        "tally": tally, "top_sample": top_results, "random_sample": random_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--random-n", type=int, default=30)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = run(top_n=args.top_n, random_n=args.random_n, min_count=args.min_count, seed=args.seed)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"tally": result["tally"], "sample": result["sample"],
                       "total_projects": result["total_projects"]}, indent=2))


if __name__ == "__main__":
    main()
