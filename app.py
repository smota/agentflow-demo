"""AwesomeAwesomeness: a read-only, versioned public resource library."""
import html
import json
from pathlib import Path

import streamlit as st
from awesome.catalogue import load_catalogue
from awesome.navigation import (DEFAULTS, SORTS, VIEWS, discover,
                                matching_occurrences, normalize, page_slice, share_url)

ROOT = Path(__file__).resolve().parent
VERSION = json.loads((ROOT / "package.json").read_text())["version"]
st.set_page_config(page_title="AwesomeAwesomeness · A library of good finds", page_icon="✳", layout="wide")


@st.cache_data
def catalogue(content_stamp: int) -> dict:
    return load_catalogue(ROOT / "data/catalogue.json")


st.html("""<style>
.block-container {max-width:1180px;padding-top:3.5rem;padding-bottom:2rem}
.brand {font-weight:800;letter-spacing:-.04em;font-size:1.2rem;margin-bottom:.7rem;overflow-wrap:anywhere}
.brand span {color:#087f73;margin-right:.45rem}
.eyebrow {font-size:.75rem;font-weight:800;letter-spacing:.12em;color:#087f73;text-transform:uppercase}
.hero {font-family:Georgia,serif;font-weight:400;font-size:clamp(2rem,4vw,3.2rem);line-height:1.1;letter-spacing:-.045em;margin:.4rem 0 .6rem}
.hero em {color:#087f73;font-style:italic}
.intro {color:#53635e;font-size:.95rem;line-height:1.5;margin:0 0 .5rem}
.stats {display:flex;flex-wrap:wrap;gap:.4rem 1.3rem;color:#53635e;font-size:.82rem;padding:.4rem 0}
.stats strong {color:#173c35}
.resource-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}
.resource-card {border:1px solid #d8dfd5;border-radius:14px;background:#fffef9;padding:1.15rem;overflow-wrap:anywhere}
.resource-card .topic {font-size:.8rem;color:#53635e;margin-bottom:.6rem}
.resource-card h3 {font-size:1.1rem;letter-spacing:-.02em;margin:0 0 .6rem}
.resource-card h3 a {color:#173c35;text-decoration:none}
.resource-card a:hover {text-decoration:underline}
.resource-card p {font-size:.88rem;color:#53635e;line-height:1.55;margin:0 0 .8rem}
.resource-card .source {font-size:.8rem;color:#087f73}
.resource-card a:focus-visible {outline:3px solid #bd7210;outline-offset:4px}
@media(max-width:1000px){.resource-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.block-container{padding:3.8rem 1rem 2rem}.resource-grid{grid-template-columns:1fr}.brand{font-size:1.08rem}.eyebrow{font-size:.68rem}.hero{font-size:2.2rem}}
</style>""")
st.html('<div class="brand"><span>✳</span>AwesomeAwesomeness</div><div class="eyebrow">Community-curated. Wonderfully discoverable.</div><h1 class="hero">Less searching. More <em>good finds.</em></h1><p class="intro">Useful projects from selected community-curated lists. Find your next good thing.</p>')
try:
    data = catalogue((ROOT / "data/catalogue.json").stat().st_mtime_ns)
except (OSError, ValueError, KeyError):
    st.error("The catalogue is temporarily unavailable. Please try again later.")
    st.stop()

source_options = ["All sources", *[s["id"] for s in data["sources"]]]
topic_options = ["All topics", *sorted({o["category"] for r in data["resources"] for o in r["occurrences"]})]
if "discovery" not in st.session_state:
    # Reject repeated URL fields instead of silently choosing an ambiguous value.
    params = {k: st.query_params.get_all(k)[0] for k in st.query_params
              if len(st.query_params.get_all(k)) == 1}
    st.session_state.discovery = normalize(params, source_options, topic_options)
state = st.session_state.discovery


def changed(field: str, widget: str) -> None:
    state[field] = st.session_state[widget]
    if field != "view":
        state["page"] = 1
    st.session_state.pop("shared_url", None)
    st.query_params.clear()


def reset() -> None:
    st.session_state.discovery = dict(DEFAULTS)
    st.session_state.pop("shared_url", None)
    st.query_params.clear()


st.html(f'<div class="stats"><span><strong>{len(data["resources"]):,}</strong> resources</span><span><strong>{len(data["sources"])}</strong> source lists</span><span>Snapshot {html.escape(data["generated_at"][:10])}</span></div>')
st.session_state.view = state["view"]
st.radio("Explore", VIEWS, horizontal=True, key="view", on_change=changed, args=("view", "view"))

if state["view"] == "Discover":
    st.session_state.query = state["q"]
    st.text_input("Search resources", placeholder="Try terminal, testing, web, or learning…", max_chars=200,
                  key="query", on_change=changed, args=("q", "query"),
                  help="Matches title, description, URL and topic. All words must match; punctuation is literal.")
    with st.expander("Filter & sort", expanded=any(state[k] != DEFAULTS[k] for k in ("source", "topic", "sort"))):
        controls = st.columns(3)
        for col, field, label, options in zip(controls, ("source", "topic", "sort"),
                                              ("Source list", "Topic", "Sort"),
                                              (source_options, topic_options, SORTS)):
            st.session_state[field] = state[field]
            col.selectbox(label, options, key=field, on_change=changed, args=(field, field))
    results = discover(data["resources"], state)
    page, pages, start, end = page_slice(len(results), state["page"])
    state["page"] = page
    st.caption(f"{len(results):,} resources · {state['sort']} · Showing {start + 1 if results else 0}–{end} · Page {page} of {pages}")
    with st.container(horizontal=True):
        st.button("Reset discovery", on_click=reset)
        if st.button("Share this search"):
            st.session_state.shared_url = share_url(normalize(state, source_options, topic_options))
    if "shared_url" in st.session_state:
        st.warning("Search text is included in the link. Do not include private information.")
        st.code(st.session_state.shared_url, language=None)
    if not results:
        st.info("No finds for these criteria. Try fewer words or Reset discovery to clear all filters.")
    else:
        st.caption("Resource links open third-party sites in a new tab. Inclusion is not a security endorsement.")
        cards = []
        for item in results[start:end]:
            occurrence = matching_occurrences(item, state["source"], state["topic"])[0]
            source = occurrence["source"]
            provenance_url = share_url({**DEFAULTS, "view": "Sources", "source": source})
            cards.append(f'<article class="resource-card"><div class="topic">{html.escape(occurrence["category"])}</div><h3><a href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(item["title"])} ↗</a></h3><p>{html.escape(item["description"][:220] or "Explore this community-curated resource.")}</p><a class="source" href="{html.escape(provenance_url, quote=True)}" target="_blank" rel="noopener noreferrer">About {html.escape(source)} ↗</a></article>')
        st.html('<section class="resource-grid" aria-label="Resources">' + "".join(cards) + '</section>')
        with st.container(horizontal=True):
            if st.button("← Previous", disabled=page == 1):
                state["page"] -= 1
                st.session_state.pop("shared_url", None)
                st.rerun()
            if st.button("Next →", disabled=page == pages):
                state["page"] += 1
                st.session_state.pop("shared_url", None)
                st.rerun()
        st.caption(f"Page {page} of {pages} · {len(results):,} resources. About-source links open provenance in a new tab.")
elif state["view"] == "Sources":
    st.subheader("Good lists, with their receipts.")
    st.write(data["coverage"])
    st.caption("At least 50,000 observed stars qualify source lists—not individual resources. Stars are not a safety or quality guarantee.")
    for source in data["sources"]:
        with st.expander(f"{source['id']} · {source['stars']:,} observed stars", expanded=state["source"] == source["id"]):
            st.write(source["reason"])
            st.caption(f"Observed {source['observed_at'][:10]} · {source['extracted_occurrences']:,} extracted entries · {source['license']}")
            st.link_button("Read the pinned source", f"https://github.com/{source['id']}/blob/{source['revision']}/{source['readme_path']}")
            st.code(source["revision"], language=None)
            st.text(source["license_text"])
    st.caption(f"{len(data['candidates'])} candidates discovered; {len(data['sources'])} selected after review. Other candidates are outside this preview, not judged low quality.")
else:
    st.subheader("A small app. An observable delivery process.")
    st.write("Built with Agentflow: explicit role passes, advisory councils, review returns, tests and versioned releases. Crawling happens locally; this app only reads the published snapshot. Stakeholder personas are agent-simulated, not human sign-off.")
    st.markdown("**The delivery path:** pinned framework installation → architecture council → early public preview → failed CI and repair → UX refinement → interrupted-rebuild and fresh-context recovery → release council and versioned acceptance. Exact checks and publication receipts are linked below.")
    st.link_button("Follow the illustrated delivery story ↗", "https://github.com/smota/agentflow-demo/blob/main/docs/demo/story.md")
    st.link_button("Explore the GitHub workstream ↗", "https://github.com/smota/agentflow-demo/issues/1")
    st.link_button("Versions and releases ↗", "https://github.com/smota/agentflow-demo/releases")
st.divider()
st.caption(f"AwesomeAwesomeness · v{VERSION} · Catalogue {data['digest'][:12]} · Built with Agentflow · No live crawling or AI inference")
