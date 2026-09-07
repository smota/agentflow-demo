# Landscape: Network as a map of lists

Explore **Network** is the list landscape. Discover stays list-first. This page is the
product slice for the optional offline landscape artifact (`data/landscape-index.json`
plus compact `data/landscape/<2-hex>.json` shards).

## What you see

- A map of eligible lists at precomputed `(x, y)`, not a selectbox-first 15-node star.
- Color by **community** (issue #86 candidate clustering) or **topic**. Communities color
  the map; they do not replace list topics and are not an authoritative ontology.
- Size by indexed entries. Unknown entry counts use a disclosed default size — unknown
  is not zero.
- Hide near-duplicate families (`hide_clones`) as a filter/lens, not a quality rank.
- An inspector: Unique · Family · Shared · Hub (composition of citations, not quality),
  neighbor table, and edge previews split independent vs copy-lineage (`truncated`/`total`
  disclosed, same discipline as alternatives).
- The existing 15-node neighborhood SVG remains optional **detail after a list is
  selected**, not the landing chart.

## What this is not

- Not a hosted crawler, database, or model.
- Not a trust, quality, or best-list score. Citation counts stay provenance.
- Copy-lineage / near-duplicate (`jaccard >= 0.5` and `copy_fraction >= 0.6` via
  `awesome.copy_lineage`) is a lens over already-published network pairs.
- Caps and digest publication remain: stage under `data/staging/`, promote only with
  `--expected-digest`.

## Derivation

Offline only (`python -m tools.derive_landscape`). Streams published project shards one
at a time; the hosted session never loads `data/projects/` to compute set-diff or edge
contents. Layout uses a normalized Laplacian spectral embedding (`numpy.linalg.eigh`)
and pure-Python Louvain. Isolated lists still get coordinates and a disclosed
singleton/unclustered `community_id`.

See `docs/demo/list-data.md` for the stage / publish / validate commands beside
`derive_network`.
