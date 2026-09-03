"""Read-only Streamlit list explorer. All ingestion stays in local tools."""
from __future__ import annotations
import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from awesome.lists import load_index, validate_detail
from awesome.explore import (DEFAULTS, SORTS, STATES, FRESHNESS, normalize,
                             filtered, page_slice, share_url, content_filter, number)


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
a:focus-visible,button:focus-visible{outline:3px solid #bd7210!important;outline-offset:3px}
@media(max-width:640px){.block-container{padding:3.5rem 1rem 2rem}.hero{font-size:2.6rem}.list-card{min-height:0}.list-card p{min-height:0}h1:not(.hero){font-size:1.9rem}
.st-key-list_metrics [data-testid="stColumn"],.st-key-discovery_metrics [data-testid="stColumn"]{min-width:calc(50% - 1rem)!important;flex:1 1 calc(50% - 1rem)!important}
[data-testid="stMetricValue"]{font-size:1.75rem}}
</style>"""


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

    def reset():
        st.session_state.list_explorer = dict(DEFAULTS)
        st.session_state.pop("list_shared", None)
        st.query_params.clear()

    def choose(field, label, options, target=st):
        key = "le_" + field
        st.session_state[key] = state[field]
        return target.selectbox(label, options, key=key, on_change=change, args=(field, key))

    navigation = st.columns([1, 1, 3])
    navigation[0].button("Explore lists", on_click=go, args=("Discover",), width="stretch")
    navigation[1].button("Delivery story", on_click=go, args=("Delivery story",), width="stretch")
    if state["view"] == "Delivery story":
        st.title("Built in the open.")
        st.write("Follow the decisions, reviews, tests and releases behind this application.")
        st.link_button("Read the demo story", "https://github.com/smota/agentflow-demo/blob/main/docs/demo/story.md")
        st.link_button("Follow the 2.0 delivery", "https://github.com/smota/agentflow-demo/issues/16")
        st.caption("Agent-simulated stakeholder reviews are advisory, not human approval. Local processing; read-only free hosting.")
    elif state["view"] == "List":
        item = next(x for x in index["lists"] if x["id"] == state["list"])
        st.button("← Back to results", on_click=go, args=("Discover",))
        st.caption(" / ".join(item["topics"]))
        st.title(item["name"])
        st.html('<p class="intro">' + html.escape(item["scope"]) + '</p>')
        st.link_button("Open original list ↗", item["url"], type="primary")
        st.link_button("Meet the upstream contributors ↗", item["url"] + "/graphs/contributors")
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
    version = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
    st.caption(f"{'Local preview of next version · base ' if preview else ''}v{version} · {index['counts'].get('eligible', 0):,} curated lists · Snapshot {index['generated_at'][:10]} · Data {index['digest'][:12]}")
