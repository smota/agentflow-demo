"""Read-only Streamlit list explorer. All ingestion stays in local tools."""
from __future__ import annotations
import base64
import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from awesome.catalogue import digest
from awesome.lists import load_index, validate_detail
from awesome.insights import dashboard, eligible_lists, comparison
from awesome.explore import (DEFAULTS, SORTS, STATES, FRESHNESS, normalize,
                             filtered, page_slice, share_url, content_filter, number)
from awesome.delivery import render_delivery
from awesome.network import (MIN_SHARED_PROJECTS, NEAR_DUP_COPY_FRACTION, NEAR_DUP_JACCARD,
                             neighbor_graph, neighbors_of, validate_network)
from awesome.network_view import CANVAS_HEIGHT, CANVAS_WIDTH, NEIGHBOR_LIMIT, layout_positions, render_svg
from awesome.project_search import citation_label, search_projects
from awesome.projects import project_id, shard_path as project_shard_path, validate_projects as validate_project_index
from awesome.search_index import shard_path as search_shard_path, validate_search_index
from awesome.liveness import shard_path as liveness_shard_path
from awesome.usage import shard_path as usage_shard_path
from awesome.alternatives import shard_path as alternatives_shard_path
from awesome.vitality import project_profile, liveness_status, usage_total

LIVENESS_COLORS = {"active": "#0e8a16", "slowing": "#bd7210", "stale": "#b42318",
                    "archived": "#53635e", "unknown": "#8a97a0"}


@st.cache_data(max_entries=2, show_spinner=False)
def catalogue(path: str, stamp: int):
    return load_index(Path(path))


@st.cache_data(max_entries=8, show_spinner=False)
def detail_file(directory: str, item: dict):
    path = Path(directory) / item["detail"]
    if path.is_symlink() or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Invalid detail file")
    detail = json.loads(path.read_text(encoding="utf-8"))
    validate_detail(detail, item)
    return detail


@st.cache_data(max_entries=2, show_spinner=False)
def project_top_index(path: str, stamp: int, list_index_digest: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # Cheap top-level linkage check only (small file, no per-project rows) -- the corpus itself
    # (data/projects/*.json) is validated by the offline pipeline (`python -m tools.derive_projects
    # validate`), not re-scanned live on every session load.
    validate_project_index(data, {"digest": list_index_digest})
    return data


@st.cache_data(max_entries=2, show_spinner=False)
def search_top_index(path: str, stamp: int, project_index_digest: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_search_index(data, {"digest": project_index_digest})  # same cheap top-level-only check
    return data


@st.cache_data(max_entries=2, show_spinner=False)
def network_data(path: str, stamp: int, project_index_digest: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # Unlike project_top_index/search_top_index (deliberately top-level-only checks against a
    # 900k+-project sharded corpus), D1's network artifact is small and unsharded (100 hub rows,
    # tens of thousands of list-pair rows -- see awesome/network.py), so a full validate_network()
    # here costs about as much as catalogue()'s own full validate_index() over ~8k list records, not
    # a corpus-scale re-scan.
    validate_network(data, {"digest": project_index_digest})
    return data


@st.cache_data(max_entries=2, show_spinner=False)
def search_records(directory: str, shard_digests: tuple):
    """Load every offline-computed search shard once per data version, cached across reruns for
    the whole session -- the only "live computation" this view performs is text filtering/ranking
    over these already-precomputed records (`awesome.project_search.search_projects`).

    Verifies each shard's own digest against the published top index's registry, the same
    lightweight per-file integrity check `detail_file` applies to list content, but does not
    re-run the full per-record validator (`awesome.search_index.validate_search_shard`) against
    every one of 900k+ records on every session load -- that full validation is the offline
    pipeline's own responsibility (`python -m tools.derive_search_index validate`, run as part of
    this product's CI-equivalent checks) and would be disproportionate to repeat on every cold
    Streamlit cache."""
    records = []
    for prefix, shard_digest in shard_digests:
        shard = json.loads((Path(directory) / search_shard_path(prefix)).read_text(encoding="utf-8"))
        if shard.get("digest") != shard_digest or digest({k: v for k, v in shard.items() if k != "digest"}) != shard_digest:
            raise ValueError("Search shard digest mismatch")
        records.extend(shard["projects"])
    return records


@st.cache_data(max_entries=32, show_spinner=False)
def project_citation_shard(directory: str, prefix: str, expected_shard_digest: str):
    """On-demand, per-shard lookup used only to fetch full citation/provenance detail (occurrence
    list with source_url links) for the small set of results actually displayed on a search results
    page -- never the whole corpus. Cached per shard, so results sharing a shard reuse one read.
    `expected_shard_digest` comes from the published project index's own `shards` registry (the
    same prefix -> shard-digest map `awesome.projects.validate_projects` checks), not the project
    shard's own `source_index_digest` field (which instead names the upstream *list* index)."""
    shard = json.loads((Path(directory) / project_shard_path(prefix)).read_text(encoding="utf-8"))
    if shard.get("digest") != expected_shard_digest or digest({k: v for k, v in shard.items() if k != "digest"}) != expected_shard_digest:
        raise ValueError("Project shard digest mismatch")
    return shard


def project_citations(directory: str, project_id: str, project_index: dict) -> dict | None:
    prefix = project_id[:2]
    expected_digest = project_index.get("shards", {}).get(prefix)
    if not expected_digest:
        return None
    shard = project_citation_shard(directory, prefix, expected_digest)
    return next((record for record in shard["projects"] if record["id"] == project_id), None)


def _stamp(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


@st.cache_data(max_entries=4, show_spinner=False)
def artifact_index(path: str, stamp: int):
    """Load a small versioned Epic E top-level index (project/liveness/usage/alternatives). `stamp`
    of 0 means the file does not exist yet -- an artifact whose story hasn't published anything for
    this shard yet, not an error. Returns None in that case; callers treat that as "not observed"."""
    if stamp == 0:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_data(max_entries=256, show_spinner=False)
def artifact_shard(path: str, stamp: int):
    if stamp == 0:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _project_record(directory: Path, index_name: str, shard_path_fn, pid: str) -> dict | None:
    index_path = directory / index_name
    index_data = artifact_index(str(index_path), _stamp(index_path))
    prefix = pid[:2]
    if not index_data or prefix not in index_data.get("shards", {}):
        return None
    shard_path_value = directory / shard_path_fn(prefix)
    shard = artifact_shard(str(shard_path_value), _stamp(shard_path_value))
    if not shard:
        return None
    return next((record for record in shard.get("projects", []) if record["id"] == pid), None)


def load_project_profile(directory: Path, pid: str) -> dict | None:
    """Resolve one deduplicated project's full Epic E profile: its #69 dedup record plus whatever
    E2 (liveness)/E3 (usage)/E4 (alternatives) artifacts already carry a record for it -- each
    independently optional. Returns None only when the project itself isn't in the published dedup
    catalogue at all (an invalid/unknown id), never when a signal is simply not yet computed."""
    project_record = _project_record(directory, "project-index.json", project_shard_path, pid)
    if not project_record:
        return None
    liveness_record = _project_record(directory, "liveness-index.json", liveness_shard_path, pid)
    usage_record = _project_record(directory, "usage-index.json", usage_shard_path, pid)
    alternatives_record = _project_record(directory, "alternatives-index.json", alternatives_shard_path, pid)
    return project_profile(project_record, liveness_record, usage_record, alternatives_record)


CSS = """<style>
.block-container{max-width:1200px;padding-top:3rem;padding-bottom:3rem}
.brand{font-size:1.1rem;font-weight:800;letter-spacing:-.04em;overflow-wrap:anywhere}
.brand span{color:#087f73;margin-right:.5rem}
.eyebrow{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:#087f73;font-weight:800;margin-top:1.2rem}
.hero{font-family:Georgia,serif;font-weight:400;font-size:clamp(2.1rem,4vw,3.2rem);line-height:1.08;letter-spacing:-.045em;margin:.4rem 0 .7rem;color:#173c35}
.hero em{color:#087f73;font-weight:400}
.intro{color:#53635e;max-width:650px;font-size:1rem;line-height:1.6}
.list-card{min-height:245px;overflow-wrap:anywhere}
.list-card .topic{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#087f73}
.list-card h3{font-size:1.12rem;line-height:1.4;margin:.7rem 0;color:#173c35}
.list-card p{font-size:.88rem;line-height:1.6;color:#53635e;min-height:70px}
.list-card .numbers{font-size:.8rem;color:#173c35;margin-top:1rem}
.list-card .fresh{font-size:.76rem;color:#53635e;margin-top:.5rem}
.identity-strip{display:flex;flex-wrap:wrap;gap:.75rem;margin:1.15rem 0 .65rem}
.identity-link{display:flex;align-items:center;gap:.65rem;min-width:210px;padding:.6rem .8rem;border:1px solid #dce8e4;border-radius:12px;background:#f7faf9;color:#173c35!important;text-decoration:none!important;transition:border-color .15s ease,transform .15s ease}
.identity-link:hover{border-color:#73b8ad;transform:translateY(-1px)}
.identity-link img{width:34px;height:34px;object-fit:contain;flex:0 0 34px}
.identity-link small{display:block;color:#62716c;font-size:.68rem;line-height:1.15;text-transform:uppercase;letter-spacing:.08em}
.identity-link strong{display:block;font-size:.86rem;line-height:1.25;margin-top:.12rem}
a:focus-visible,button:focus-visible{outline:3px solid #bd7210!important;outline-offset:3px}
@media(max-width:640px){.block-container{padding:3.5rem 1rem 2rem}.hero{font-size:clamp(2rem,10vw,2.35rem);overflow-wrap:anywhere}.hero em{display:inline-block;max-width:100%;overflow-wrap:anywhere}.list-card{min-height:0}.list-card p{min-height:0}h1:not(.hero){font-size:1.9rem}.identity-strip{display:grid}.identity-link{min-width:0}
.st-key-list_metrics [data-testid="stColumn"],.st-key-discovery_metrics [data-testid="stColumn"],.st-key-insight_metrics [data-testid="stColumn"]{min-width:calc(50% - 1rem)!important;flex:1 1 calc(50% - 1rem)!important}
[data-testid="stMetricValue"]{font-size:1.75rem}}
</style>"""


IDENTITY_LINKS = (
    ("Maintained by", "Move the Needle", "https://movetheneedle.info/", "move-the-needle-icon.png"),
    ("Built with", "AgentFlow", "https://movetheneedle.info/agent-sdlc/", "agentflow-icon.png"),
)


def identity_footer(asset_dir: Path | None = None) -> str:
    asset_dir = asset_dir or Path(__file__).resolve().parent / "assets"
    links = []
    for relationship, name, url, filename in IDENTITY_LINKS:
        encoded = base64.b64encode((asset_dir / filename).read_bytes()).decode("ascii")
        links.append(
            f'<a class="identity-link" href="{url}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="{relationship} {name} (opens in a new tab)">'
            f'<img src="data:image/png;base64,{encoded}" alt="{name} logo" width="34" height="34">'
            f'<span><small>{relationship}</small><strong>{name}</strong></span></a>'
        )
    return '<div class="identity-strip" aria-label="Application identity">' + "".join(links) + "</div>"


def render(root: Path, preview=False):
    st.set_page_config(page_title="AwesomeAwesomeness · Explore the lists", page_icon="✳", layout="wide")
    st.html(CSS)
    st.html('<div class="brand"><span>✳</span>AwesomeAwesomeness</div>')
    directory = root / (".cache/ui-preview" if preview else "data")
    try:
        path = directory / "list-index.json"
        index = catalogue(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError):
        st.error("The list catalogue is unavailable. Please try again later.")
        st.stop()
    if preview:
        st.warning("Local design preview · unaccepted working observations. Not a published release.")
    if "list_explorer" not in st.session_state:
        params = {k: st.query_params.get_all(k)[0] for k in st.query_params if len(st.query_params.get_all(k)) == 1}
        st.session_state.list_explorer = normalize(params, index)
    elif st.session_state.get("list_index_digest") != index["digest"]:
        st.session_state.list_explorer = normalize(st.session_state.list_explorer, index)
        st.session_state.pop("list_shared", None)
    st.session_state.list_index_digest = index["digest"]
    state = st.session_state.list_explorer

    def change(field, widget):
        state[field] = st.session_state[widget]
        if field != "view": state["page"] = 1
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def go(view, rid=""):
        if view == "List" and rid != state["list"]:
            state.update(content_q="", content_category="all")
        state.update(view=view, list=rid)
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def go_project(pid):
        state.update(view="Project", project=pid)
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def go_network(list_id):
        state.update(view="Network", network_list=list_id)
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def reset():
        st.session_state.list_explorer = dict(DEFAULTS)
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def compare_change():
        state["compare"] = ",".join(st.session_state.compare_ids[:4])
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def reset_insights():
        state.update(q="", topic="All topics", freshness="Any freshness", compare="")
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def choose(field, label, options, target=st):
        key = "le_" + field
        st.session_state[key] = state[field]
        return target.selectbox(label, options, key=key, on_change=change, args=(field, key))

    navigation = st.columns([1, 1, 1, 1, 1])
    navigation[0].button("Explore lists", on_click=go, args=("Discover",), width="stretch")
    navigation[1].button("Search projects", on_click=go, args=("Search projects",), width="stretch")
    navigation[2].button("Insights", on_click=go, args=("Insights",), width="stretch")
    navigation[3].button("Delivery story", on_click=go, args=("Delivery story",), width="stretch")
    navigation[4].button("Explore network", on_click=go, args=("Network",), width="stretch")
    if state["view"] == "Delivery story":
        render_delivery(root, index)
    elif state["view"] == "Search projects":
        st.html('<div class="eyebrow">Search across every list</div><h1 class="hero">One search.<br><em>Every eligible list.</em></h1><p class="intro">Search once and see matching projects from any curated list — ranked by text relevance, never by how many lists happen to cite a result. Citation counts, when shown, are a separate, honestly labeled fact, not a trust score.</p>')
        try:
            project_index_path = directory / "project-index.json"
            search_index_path = directory / "search-index.json"
            project_index = project_top_index(str(project_index_path), project_index_path.stat().st_mtime_ns, index["digest"])
            search_index = search_top_index(str(search_index_path), search_index_path.stat().st_mtime_ns, project_index["digest"])
            records = search_records(str(directory), tuple(sorted(search_index["shards"].items())))
        except (OSError, ValueError, KeyError):
            st.error("The cross-list search index is unavailable. Please try again later.")
        else:
            st.session_state.search_q = state["search_q"]
            st.text_input("Search projects across every eligible list",
                          placeholder="Try self-hosted photo gallery, machine learning, or a project name…",
                          max_chars=200, key="search_q", on_change=change, args=("search_q", "search_q"))
            query = state["search_q"]
            st.caption(f"{search_index['counts']['projects']:,} projects indexed across every eligible list · "
                       f"Snapshot {search_index['generated_at'][:10]}")
            if not query:
                st.info("Type a search term to see matching projects from across the whole catalogue — not just one list you happen to already know.")
            else:
                results = search_projects(records, query, limit=50)
                st.subheader(f"{len(results):,} matching projects" + (" (showing up to 50, ranked by text relevance)" if len(results) == 50 else ""))
                if not results:
                    st.info("No projects match. Try fewer or broader words.")
                for record in results:
                    with st.container(border=True):
                        st.markdown(f"**{html.escape(record['title'])}**")
                        if record.get("topics"):
                            st.caption("Topics: " + ", ".join(record["topics"]))
                        label = citation_label(record["list_count"], record["independent_list_count"])
                        (st.success if label["kind"] == "independent" else st.caption)(label["text"])
                        detail = project_citations(str(directory), record["id"], project_index)
                        cols = st.columns([1, 1])
                        cols[0].link_button("Open project ↗", record["url"], width="stretch")
                        if detail:
                            shown_occurrences = detail["occurrences"][:10]
                            for occurrence in shown_occurrences:
                                st.link_button(f"Also listed in {occurrence['list_name']} ↗",
                                              occurrence["source_url"], width="stretch")
                            if len(detail["occurrences"]) > len(shown_occurrences):
                                st.caption(f"+ {len(detail['occurrences']) - len(shown_occurrences)} more source list(s), all counted in the totals above.")
            with st.expander("How independent citation counts are derived"):
                st.write(search_index["content_policy"])
                st.caption("See issue #65 for the full validation method and finding behind this methodology.")
    elif state["view"] == "Insights":
        st.html('<div class="eyebrow">Catalogue intelligence</div><h1 class="hero">See the landscape.<br><em>Compare the curators.</em></h1><p class="intro">Understand what the Awesome community maintains, then compare a few lists side by side. Every measure comes from the current versioned snapshot—never an invented trend.</p>')
        filter_columns = st.columns([2, 1, 1, 1])
        st.session_state.insight_q = state["q"]
        filter_columns[0].text_input("Filter dashboard lists", key="insight_q", placeholder="Search scope, topic or list name",
                                     on_change=change, args=("q", "insight_q"))
        topics = ["All topics", *sorted({topic for item in eligible_lists(index) for topic in item.get("topics", [])})]
        choose("topic", "Topic", topics, filter_columns[1])
        choose("freshness", "Freshness", FRESHNESS, filter_columns[2])
        filter_columns[3].button("Reset dashboard", on_click=reset_insights, width="stretch")
        insight_state = {**DEFAULTS, "q": state["q"], "topic": state["topic"], "freshness": state["freshness"]}
        insight = dashboard(index, filtered(index, insight_state)); population = insight["population"]
        with st.container(key="insight_metrics"):
            metrics = st.columns(4)
        metrics[0].metric("Eligible lists", number(population))
        metrics[1].metric("Indexed entries", number(insight["total_entries"]))
        metrics[2].metric("Median stars", number(insight["median_stars"]))
        metrics[3].metric("Fresh ≤30 days", number(insight["fresh_30"]))
        st.caption(f"Population: {population:,} filtered eligible public lists · Freshness known: {insight['freshness_known']:,}; unknown: {insight['freshness_unknown']:,} · Snapshot observed {insight['observed_at']}")
        st.caption(f"Indexed-content counts known: {insight['entries_known']:,}; unknown: {insight['entries_unknown']:,}. Observed entry totals never convert unknown counts to zero.")
        if not population:
            st.info("No eligible lists match these dashboard filters. Reset them to restore the full catalogue view.")
        else:
            topics_tab, freshness_tab, relationship_tab, stars_tab, entries_tab = st.tabs(
                ("Topics", "Freshness", "Stars & content", "Stars distribution", "Entries distribution"))
            with topics_tab:
                topic_frame = pd.DataFrame(insight["topics"][:15])
                st.bar_chart(topic_frame, x="Topic", y="Lists", height=390)
                st.caption("Top 15 derived topics. A list may contribute to more than one topic; original categories remain on its profile.")
                with st.expander("Accessible topic data"): st.dataframe(topic_frame, hide_index=True, width="stretch")
            with freshness_tab:
                fresh_frame = pd.DataFrame(insight["freshness"])
                st.bar_chart(fresh_frame, x="Range", y="Lists", height=390)
                st.caption(f"All {population:,} matching lists by last pinned README content change; unknown values are retained explicitly.")
                with st.expander("Accessible freshness data"): st.dataframe(fresh_frame, hide_index=True, width="stretch")
            with relationship_tab:
                scatter_frame = pd.DataFrame(insight["scatter"])
                st.scatter_chart(scatter_frame, x="Stars", y="Entries", color="Topic", height=430)
                st.caption(f"Observed stars versus indexed entries for {population:,} matching lists. This is a current-snapshot relationship, not growth history.")
                with st.expander("Accessible stars and content data"): st.dataframe(scatter_frame, hide_index=True, width="stretch", height=360)
            with stars_tab:
                stars_frame = pd.DataFrame(insight["stars_distribution"])
                st.bar_chart(stars_frame, x="Stars", y="Lists", height=390)
                st.caption(f"How {population:,} matching lists spread across observed star-count ranges. Stars measure popularity, never quality.")
                with st.expander("Accessible stars-distribution data"): st.dataframe(stars_frame, hide_index=True, width="stretch")
            with entries_tab:
                entries_frame = pd.DataFrame(insight["entries_distribution"])
                st.bar_chart(entries_frame, x="Entries", y="Lists", height=390)
                st.caption("How matching lists spread across observed indexed-entry-count ranges. \"Unknown\" means content indexing is pending or unsupported for that list, never zero entries.")
                with st.expander("Accessible entries-distribution data"): st.dataframe(entries_frame, hide_index=True, width="stretch")

        st.subheader("Compare lists")
        eligible = eligible_lists(index); ids = [item["id"] for item in eligible]
        selected = [rid for rid in state["compare"].split(",") if rid in ids]
        if not selected: selected = ids[:2]; state["compare"] = ",".join(selected)
        st.session_state.compare_ids = selected
        st.multiselect("Choose 2–4 eligible lists", ids, format_func=lambda rid: next(x["name"] for x in eligible if x["id"] == rid),
                       max_selections=4, key="compare_ids", on_change=compare_change)
        rows = comparison(index, st.session_state.compare_ids)
        if len(rows) < 2:
            st.info("Choose at least two lists for a meaningful comparison.")
        else:
            compare_frame = pd.DataFrame(rows)
            st.dataframe(compare_frame, hide_index=True, width="stretch",
                column_config={"GitHub": st.column_config.LinkColumn(display_text="Open ↗")})
            metric = st.selectbox("Comparison metric", ("Stars", "Forks", "Entries", "Categories", "Contributors seen", "Freshness index"), key="compare_metric")
            chart_rows = compare_frame[["List", metric]].rename(columns={metric: "Value"})
            st.bar_chart(chart_rows, x="List", y="Value", height=360)
            st.caption("One metric and unit is charted at a time; the table above is the accessible exact-value reference.")
            target = st.selectbox("Open a compared list", st.session_state.compare_ids,
                                  format_func=lambda rid: next(x["name"] for x in eligible if x["id"] == rid), key="compare_open")
            st.button("Explore compared list →", on_click=go, args=("List", target))
    elif state["view"] == "Network":
        st.html('<div class="eyebrow">Opt-in secondary view</div><h1 class="hero">See how lists<br><em>relate to each other.</em></h1>'
               '<p class="intro">Explore one list’s nearest neighbors in the citation network — other lists citing many of the same projects. '
               'This is a secondary, filtered view: it never replaces list-first Discover/List browsing, and it never renders the whole catalogue at once '
               '(6,377+ lists would be too heavy to lay out responsively in a browser tab) — only a selected list’s bounded neighborhood.</p>')
        try:
            project_index_path = directory / "project-index.json"
            network_index_path = directory / "network-index.json"
            project_index = project_top_index(str(project_index_path), project_index_path.stat().st_mtime_ns, index["digest"])
            network = network_data(str(network_index_path), network_index_path.stat().st_mtime_ns, project_index["digest"])
        except (OSError, ValueError, KeyError):
            st.error("The network exploration data is unavailable. Please try again later.")
        else:
            names_by_id = {item["id"]: item["name"] for item in index["lists"]}
            neighbor_ids = {row["a"] for row in network["list_pairs"]} | {row["b"] for row in network["list_pairs"]}
            options = [""] + sorted((rid for rid in neighbor_ids if rid in names_by_id),
                                    key=lambda rid: names_by_id[rid].casefold())
            st.session_state.network_select = state["network_list"]
            st.selectbox("Choose a list to explore its network neighborhood", options,
                        format_func=lambda rid: "— choose a list —" if rid == "" else names_by_id[rid],
                        key="network_select", on_change=change, args=("network_list", "network_select"))
            st.caption(f"{len(neighbor_ids):,} of {index['counts'].get('eligible', 0):,} eligible lists have at least one "
                      f"qualifying neighbor (sharing ≥ {MIN_SHARED_PROJECTS} projects with another list) at the published threshold. "
                      f"Snapshot {network['generated_at'][:10]}.")
            if not state["network_list"]:
                st.info("Choose a list above to see other lists that cite many of the same projects.")
            else:
                graph = neighbor_graph(network["list_pairs"], state["network_list"], limit=NEIGHBOR_LIMIT)
                selected_name = names_by_id.get(state["network_list"], state["network_list"])
                if len(graph["nodes"]) <= 1:
                    st.info(f"{selected_name} has no other eligible list sharing at least {MIN_SHARED_PROJECTS} "
                           "projects at the published threshold.")
                else:
                    labels = {node_id: names_by_id.get(node_id, node_id) for node_id in graph["nodes"]}
                    positions = layout_positions(graph["nodes"], graph["edges"], state["network_list"])
                    svg = render_svg(graph, positions, labels)
                    # st.html() sanitizes with DOMPurify's html-only profile, which strips <svg>
                    # entirely -- embed it as a base64 data-URI <img> instead (an allowed tag, and
                    # the same technique identity_footer() already uses for the brand/AgentFlow
                    # logos above), rather than switching to an iframe-based component.
                    encoded_svg = base64.b64encode(svg.encode("utf-8")).decode("ascii")
                    st.html(f'<img src="data:image/svg+xml;base64,{encoded_svg}" width="{CANVAS_WIDTH}" '
                           f'height="{CANVAS_HEIGHT}" style="width:100%;max-width:{CANVAS_WIDTH}px;height:auto;'
                           f'display:block;margin:0 auto" alt="Network neighborhood of {html.escape(selected_name)}">')
                    st.caption(f"Showing up to {NEIGHBOR_LIMIT} nearest neighbors of {selected_name} by shared-project similarity, "
                              "plus any qualifying links between those neighbors. Dashed amber edges mark pairs flagged "
                              f"near-duplicate (jaccard ≥ {NEAR_DUP_JACCARD}, copy-lineage fraction ≥ {NEAR_DUP_COPY_FRACTION}) — "
                              "likely same-owner, forked, or templated sibling lists, not two independently curated collections.")
                    neighbor_rows = neighbors_of(network["list_pairs"], state["network_list"], limit=NEIGHBOR_LIMIT)
                    table_rows = [{"List": labels[row["neighbor"]], "Shared projects": row["shared"],
                                  "Jaccard similarity": row["jaccard"], "Copy-lineage fraction": row["copy_fraction"],
                                  "Near-duplicate": "Yes" if row["near_duplicate"] else "No"} for row in neighbor_rows]
                    with st.expander("Accessible neighbor data"):
                        st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
                    open_target = st.selectbox("Open a neighboring list", [row["neighbor"] for row in neighbor_rows],
                                               format_func=lambda rid: labels.get(rid, rid), key="network_open")
                    st.button("Explore neighboring list →", on_click=go, args=("List", open_target))
            with st.expander(f"Hub projects (top {len(network['hub_projects'])}, copy-lineage discounted)"):
                hub_rows = [{"Project": row["title"], "Cited by (raw)": row["list_count"],
                            "Cited by (independent)": row["independent_list_count"],
                            "Copy-lineage discount": row["hub_discount"], "URL": row["url"]}
                           for row in network["hub_projects"][:25]]
                st.dataframe(pd.DataFrame(hub_rows), hide_index=True, width="stretch",
                            column_config={"URL": st.column_config.LinkColumn(display_text="Open ↗")})
                st.caption("Ranked by independent_list_count — the copy-lineage-discounted citation count (issue #65's "
                          "validated heuristic), never a quality or trust score. Copy-lineage discount is the raw "
                          "citation count minus that discounted count, an observed fact about how much of the raw "
                          "count came from same-owner/forked sibling lists, not a hidden adjustment.")
            with st.expander("How this network view is derived"):
                st.write(network["content_policy"])
                st.caption("See issue #50 (D1) for the full methodology and the real-catalogue measurement that set these thresholds.")
    elif state["view"] == "List":
        item = next(x for x in index["lists"] if x["id"] == state["list"])
        st.button("← Back to results", on_click=go, args=("Discover",))
        st.caption(" / ".join(item["topics"]))
        st.title(item["name"])
        st.html('<p class="intro">' + html.escape(item["scope"]) + '</p>')
        st.link_button("Open original list ↗", item["url"], type="primary")
        st.link_button("Meet the upstream contributors ↗", item["url"] + "/graphs/contributors")
        st.button("See this list's network neighborhood →", on_click=go_network, args=(item["id"],))
        with st.container(key="list_metrics"):
            metrics = st.columns(4)
        for column, label, key in zip(metrics, ("Stars", "Forks", "Indexed entries", "Contributors seen"), ("stars", "forks", "entry_count", "contributors_count")):
            column.metric(label, number(item.get(key)))
        changed = item.get("content_updated_at")
        freshness_index = item["freshness"].get("index")
        st.caption(
            f"Last content change: {changed[:10] if changed else 'Unknown'} · "
            f"Freshness: {item['freshness']['range']}"
            f"{' · Index ' + str(freshness_index) + '/100' if freshness_index is not None else ''} · "
            f"Observed {item['observed_at'][:10]} · Status: {item['state']}"
        )
        if item["state"] != "eligible": st.info(item["reason"])
        if item.get("detail"):
            try:
                detail = detail_file(str(directory), item)
            except (OSError, ValueError, KeyError):
                st.error("This list's indexed content could not be verified. The original list remains available above.")
            else:
                st.subheader("Inside the list")
                st.caption(detail["coverage"])
                sections = {s["id"]: s for s in detail["sections"]}
                options = ["all", *[s["id"] for s in detail["sections"] if s["entries"]]]
                if state["content_category"] not in options: state["content_category"] = "all"
                category_key, content_key = "category_"+item["id"], "content_"+item["id"]
                st.session_state[category_key] = state["content_category"]
                st.session_state[content_key] = state["content_q"]
                category = st.selectbox("Original category", options, format_func=lambda value: "All categories" if value == "all" else " › ".join(sections[value]["path"]), key=category_key, on_change=change, args=("content_category", category_key))
                query = st.text_input("Search within this list", placeholder="Find an entry or listed property…", max_chars=200, key=content_key, on_change=change, args=("content_q", content_key))
                entries = content_filter(detail, query, category)
                st.caption(f"{len(entries):,} matching entries · {detail['unique_links']:,} unique indexed links")
                if category != "all": st.link_button("View this category at source ↗", sections[category]["source_url"])
                if entries:
                    rows = [{"Entry": e["title"], "Category": sections.get(e["category"], {}).get("title", "General"),
                             "Open": e["url"], "Source": e["source_url"], **e.get("properties", {})} for e in entries]
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=460,
                        column_config={"Open": st.column_config.LinkColumn("Open", display_text="Visit ↗"),
                                       "Source": st.column_config.LinkColumn("Source", display_text="At source ↗")})
                    profile_options = {e["title"]: project_id(e["url"]) for e in entries}
                    profile_pick = st.selectbox("View a project's vitality profile", list(profile_options),
                                                key="profile_pick_" + item["id"])
                    st.button("View project profile ↗", key="profile_go_" + item["id"],
                             on_click=go_project, args=(profile_options[profile_pick],))
                    st.caption("Liveness, real usage and alternatives — computed offline, factual only.")
                else: st.info("No entries match. Try another category or search.")
                st.subheader("Curated by people")
                st.write(detail["attribution"])
                observation = detail.get("contributor_observation")
                if observation:
                    st.caption(observation["description"])
                    if detail.get("contributors"):
                        columns = st.columns(min(5, len(detail["contributors"])))
                        for column, contributor in zip(columns, detail["contributors"][:5]):
                            column.link_button(f"@{contributor['login']} · {contributor['contributions']}", contributor["url"], width="stretch")
                    if detail.get("contributing_url"):
                        st.link_button("How to contribute ↗", detail["contributing_url"])
                else:
                    st.caption("Contributor counts are shown only when observed; unknown does not mean zero.")
                with st.expander("Source, taxonomy & permissions"):
                    st.write("Original category names are preserved. Topic labels are derived separately from public repository metadata.")
                    st.text("Listed properties: " + (", ".join(detail["properties"]) or "No supported structured properties observed"))
                    st.write(item["content_policy"])
                    for source_link in detail.get("source_data_links", []):
                        st.link_button("Open labelled source data ↗", source_link)
                    st.caption(f"Source license: {item.get('license') or 'Unknown'} · Commit {detail['revision']}")
        else: st.info("Content indexing is pending or this README format is unsupported. Explore the original list above.")
    elif state["view"] == "Project":
        st.button("← Back to results", on_click=go, args=("Discover",))
        profile = load_project_profile(directory, state["project"])
        if not profile:
            st.error("This project's profile is not available. It may not yet be published, or the link is invalid.")
        else:
            st.caption("Project profile · deduplicated across every citing list (#69)")
            st.title(profile["title"])
            st.link_button("Open project ↗", profile["url"], type="primary")

            status = liveness_status(profile["liveness"])
            color = LIVENESS_COLORS[status["bucket"]]
            if status["days_since_commit"] is not None:
                detail_text = f"Last observed push {status['days_since_commit']:,} day(s) ago"
            elif status["bucket"] == "archived":
                detail_text = "Archived by its owner on GitHub"
            else:
                detail_text = "Liveness has not been computed for this project yet"
            st.html(
                '<div style="border:3px solid ' + color + ';border-radius:14px;padding:1.2rem 1.5rem;margin:1rem 0 1.3rem">'
                '<div style="font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:' + color + ';font-weight:800">Liveness</div>'
                '<div style="font-size:2rem;font-weight:800;color:#173c35;margin:.15rem 0;line-height:1.15">' + html.escape(status["label"]) + '</div>'
                '<div style="color:#53635e;font-size:.95rem">' + html.escape(detail_text) + '</div></div>'
            )
            if profile["liveness"]:
                releases = profile["liveness"].get("releases", {})
                cadence = releases.get("median_interval_days")
                st.caption(
                    f"Default branch: {profile['liveness'].get('default_branch') or 'Unknown'} · "
                    f"Releases observed: {releases.get('observed_count', 0)}"
                    + (f" · Latest {releases['latest_at'][:10]}" if releases.get("latest_at") else "")
                    + (f" · Median interval {cadence:.0f}d" if cadence is not None else "")
                    + f" · Observed {profile['liveness']['observed_at'][:10]}"
                )
            else:
                st.caption("Liveness is computed offline for a growing batch of projects; this one is not covered yet.")

            st.subheader("Real usage")
            usage = usage_total(profile["usage"])
            if not usage["observed"]:
                st.caption("No verified package registry usage observed for this project yet.")
            else:
                columns = st.columns(len(usage["sources"]))
                for column, source in zip(columns, usage["sources"]):
                    column.metric(source["registry"].upper(), number(source["count"]), help=source["matched_via"])
                st.caption("Downloads/pulls are observed registry facts — never blended with stars or cross-list citation count.")

            st.subheader("See alternatives")
            alternatives = profile.get("alternatives")
            headings = (alternatives or {}).get("headings") or []
            if not headings:
                st.caption("No same-heading alternatives observed for this project yet.")
            else:
                for h_index, heading in enumerate(headings):
                    with st.expander(f"{heading['list_name']} › {heading['category']} ({heading['total_alternatives']} alternative(s))"):
                        for a_index, alternative in enumerate(heading["alternatives"]):
                            st.button(alternative["title"] + " →", key=f"alt_{state['project']}_{h_index}_{a_index}",
                                     on_click=go_project, args=(alternative["id"],))
                        if heading["truncated"]:
                            st.caption(f"Showing {len(heading['alternatives'])} of {heading['total_alternatives']}; capped for display.")

            st.caption(
                f"Cited by {profile['list_count']:,} distinct list(s), {profile['occurrence_count']:,} occurrence(s). "
                "Citation count is a factual tally, not a validated trust signal — see Delivery story."
            )
    else:
        st.html('<div class="eyebrow">Community knowledge, beautifully connected</div><h1 class="hero">A world of knowledge.<br><em>Curated by people.</em></h1><p class="intro">Discover the Awesome lists worth exploring—from self-hosting to science. Find a topic, meet its curators, and dive into their collections.</p>')
        with st.container(key="discovery_metrics"):
            metrics = st.columns(3)
        metrics[0].metric("Curated lists", number(index["counts"].get("eligible", 0)))
        metrics[1].metric("Candidates discovered", number(len(index["lists"])))
        metrics[2].metric("Minimum stars", "100")
        st.session_state.le_q = state["q"]
        st.text_input("Search lists", placeholder="Try self-hosting, Python, design, or science…", max_chars=200, key="le_q", on_change=change, args=("q", "le_q"))
        filters = st.columns([2, 1, 1])
        choose("topic", "Topic", ["All topics", *sorted({t for item in index['lists'] for t in item['topics']})], filters[0])
        choose("sort", "Sort by", SORTS, filters[1])
        choose("layout", "Display", ("Cards", "Table"), filters[2])
        with st.expander("More filters"):
            more = st.columns(3)
            st.session_state.le_min_stars = state["min_stars"]
            more[0].number_input("Minimum stars", min_value=100, max_value=1_000_000_000, step=100, key="le_min_stars", on_change=change, args=("min_stars", "le_min_stars"))
            choose("state", "Curation status", STATES, more[1])
            choose("freshness", "Content freshness", FRESHNESS, more[2])
            choose("archived", "Maintenance", ("Include archived", "Active only"))
            choose("forks", "Repository relationship", ("Include forks", "Originals only"))
            st.caption("These results require a known observed star count meeting the minimum, including in candidate views.")
        st.button("Reset discovery", on_click=reset)
        results = filtered(index, state)
        page, pages, start, end = page_slice(len(results), state["page"]); state["page"] = page
        st.subheader(f"{len(results):,} lists to explore")
        st.caption(f"Page {page} of {pages} · {start+1 if results else 0}–{end} of {len(results):,} matches")
        shown = results[start:end]
        if not results: st.info("No lists match these filters. Try a broader topic, fewer words, or reset discovery.")
        elif state["layout"] == "Table":
            st.dataframe(pd.DataFrame([{"List": x["name"], "Stars": x["stars"], "Entries": x["entry_count"], "Freshness": x["freshness"]["range"], "GitHub": x["url"]} for x in shown]), hide_index=True, width="stretch", column_config={"GitHub": st.column_config.LinkColumn(display_text="Open ↗")})
            choice = st.selectbox("Explore a listed collection", [x["id"] for x in shown], format_func=lambda rid: next(x["name"] for x in shown if x["id"] == rid))
            st.button("Explore selected list", on_click=go, args=("List", choice))
        else:
            for offset in range(0, len(shown), 3):
                columns = st.columns(3)
                for column, item in zip(columns, shown[offset:offset+3]):
                    with column.container(border=True):
                        esc = html.escape
                        scope = item['scope'][:155] + ("…" if len(item['scope']) > 155 else "")
                        st.html(f'<div class="list-card"><div class="topic">{esc(item["topics"][0])}</div><h3>{esc(item["name"])}</h3><p>{esc(scope)}</p><div class="numbers">★ {number(item["stars"])} &nbsp; · &nbsp; {number(item["entry_count"])} entries</div><div class="fresh">{number(item["category_count"])} categories · Freshness: {esc(item["freshness"]["range"])}</div></div>')
                        st.button("Explore list →", key="open_"+item["id"], on_click=go, args=("List", item["id"]), width="stretch")
                        st.link_button("GitHub ↗", item["url"], width="stretch")
        previous, following = st.columns(2)
        def turn_page(amount):
            state["page"] += amount
            st.session_state.pop("list_shared", None)
        previous.button("← Previous", disabled=page <= 1, on_click=turn_page, args=(-1,))
        following.button("Next →", disabled=page >= pages, on_click=turn_page, args=(1,))

    st.divider()
    if st.button("Share this view"):
        st.session_state.list_shared = share_url(state)
    if st.session_state.get("list_shared"):
        st.warning("Shared URLs include your search text. Do not share private information.")
        if preview: st.caption("This is a public-app URL; the unaccepted local preview is not yet available there.")
        st.code(st.session_state.list_shared, language=None)
    with st.expander("About this catalogue & coverage"):
        st.write(index["coverage"]["scope"])
        st.write("Discovery, curation eligibility and content indexing are separate. Pending is not excluded; unknown is not zero. Stars indicate popularity, not quality.")
        st.json({"states": index["counts"], "enrichment_pending": index["coverage"]["enrichment_pending"], "queued_partitions": index["coverage"]["queued_partitions"]}, expanded=False)
        st.caption("All crawling and processing happens locally. This website reads a versioned snapshot; it never runs repository code.")
    st.html(identity_footer())
    version = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
    st.caption(f"{'Local preview of next version · base ' if preview else ''}v{version} · {index['counts'].get('eligible', 0):,} curated lists · Snapshot {index['generated_at'][:10]} · Data {index['digest'][:12]}")
