"""AwesomeAwesomeness: a read-only, versioned public resource library."""
import html
import json
import math
from pathlib import Path

import streamlit as st
from awesome.catalogue import load_catalogue, search

ROOT = Path(__file__).resolve().parent
VERSION = json.loads((ROOT / "package.json").read_text())["version"]
st.set_page_config(page_title="AwesomeAwesomeness · A library of good finds", page_icon="✳", layout="wide")


@st.cache_data
def catalogue(content_stamp: int) -> dict:
    return load_catalogue(ROOT / "data/catalogue.json")


st.html("""<style>
.block-container {max-width:1180px;padding-top:2.2rem;padding-bottom:3rem}
header[data-testid="stHeader"] {background:transparent}
.brand {font-weight:800;letter-spacing:-.04em;font-size:1.3rem;margin-bottom:2.7rem}
.brand span {color:#087f73;margin-right:.45rem}
.eyebrow {font-size:.72rem;font-weight:800;letter-spacing:.17em;color:#087f73;text-transform:uppercase}
.hero {font-family:Georgia,serif;font-weight:400;font-size:clamp(2.8rem,6vw,4.8rem);line-height:1.03;letter-spacing:-.055em;max-width:850px;margin:.6rem 0 1rem}
.hero em {color:#087f73;font-style:italic}
.intro {color:#53635e;font-size:1.05rem;max-width:660px;line-height:1.7;margin-bottom:1.7rem}
.card {min-height:180px;border:1px solid #d8dfd5;border-radius:16px;background:#fffef9;padding:1.25rem;margin:0 0 1rem}
.card .topic {font-size:.68rem;text-transform:uppercase;color:#62706a;letter-spacing:.1em;margin-bottom:.65rem}
.card h3 {font-size:1.13rem;letter-spacing:-.02em;margin:0 0 .65rem}
.card h3 a {color:#173c35;text-decoration:none}
.card h3 a:hover {text-decoration:underline}
.card p {font-size:.87rem;color:#53635e;line-height:1.55;margin:0 0 .7rem}
.card .source {font-size:.72rem;color:#087f73}
.card a:focus-visible {outline:3px solid #e6a755;outline-offset:4px}
@media(max-width:640px){.block-container{padding:1.1rem}.brand{margin-bottom:1.8rem}.card{min-height:0}}
</style>""")
st.html('<div class="brand"><span>✳</span>AwesomeAwesomeness</div>')
st.html('<div class="eyebrow">Community-curated. Wonderfully discoverable.</div><h1 class="hero">Less searching.<br>More <em>good finds.</em></h1><p class="intro">A quieter way to explore the internet’s best resource lists. Real projects, chosen by communities. One place to find your next useful thing.</p>')
try:
    data = catalogue((ROOT / "data/catalogue.json").stat().st_mtime_ns)
except (OSError, ValueError, KeyError):
    st.error("The catalogue is temporarily unavailable. Please try again later.")
    st.stop()

metrics = st.columns(3)
metrics[0].metric("Resources to explore", f"{len(data['resources']):,}")
metrics[1].metric("Curated source lists", len(data["sources"]))
metrics[2].metric("Source-list entry bar", "50k+ stars")
st.caption("Stars qualify the source lists—not each linked resource. Selected preview coverage, not an exhaustive index.")
discover, sources_tab, story_tab = st.tabs(["Discover", "The source lists", "Built in the open"])
with discover:
    query = st.text_input("Search resources", placeholder="Try terminal, testing, web, or learning…", max_chars=200, key="query")
    selected = st.selectbox("From a source list", ["All sources", *[s["id"] for s in data["sources"]]], key="source")
    results = search(data["resources"], query, selected)
    st.caption(f"{len(results):,} finds · Alphabetical · Snapshot {data['generated_at'][:10]}")
    if not results:
        st.info("No finds this time. Try a shorter search or choose All sources.")
    else:
        pages = max(1, math.ceil(len(results) / 24))
        page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key=f"page:{query}:{selected}")
        columns = st.columns(3)
        for position, item in enumerate(results[(page - 1) * 24:page * 24]):
            occurrence = item["occurrences"][0]
            attribution = ", ".join(sorted({o["source"] for o in item["occurrences"]}))
            with columns[position % 3]:
                st.html(f'<article class="card"><div class="topic">{html.escape(occurrence["category"])}</div><h3><a href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(item["title"])} ↗</a></h3><p>{html.escape(item["description"][:220] or "Explore this community-curated resource.")}</p><div class="source">Found in {html.escape(attribution)}</div></article>')
        st.caption(f"Page {page} of {pages}. External links open third-party sites; inclusion is not a security endorsement.")
with sources_tab:
    st.subheader("Good lists, with their receipts.")
    st.write(data["coverage"])
    for source in data["sources"]:
        with st.expander(f"{source['id']} · {source['stars']:,} observed stars"):
            st.write(source["reason"])
            st.caption(f"Observed {source['observed_at'][:10]} · {source['extracted_occurrences']:,} extracted entries · {source['license']}")
            st.link_button("Read the pinned source", f"https://github.com/{source['id']}/blob/{source['revision']}/{source['readme_path']}")
            st.code(source["revision"], language=None)
            st.text(source["license_text"])
    st.caption(f"{len(data['candidates'])} candidates discovered; {len(data['sources'])} selected after review. Other candidates are outside this preview, not judged low quality.")
with story_tab:
    st.subheader("A small app. An observable delivery process.")
    st.write("Built with Agentflow: explicit role passes, architecture advice, review returns, tests and versioned releases. Crawling happens locally; this app only reads the published snapshot.")
    st.link_button("Follow the delivery story ↗", "https://github.com/smota/agentflow-demo/blob/main/docs/demo/story.md")
    st.link_button("Explore the GitHub workstream ↗", "https://github.com/smota/agentflow-demo/issues/1")
st.divider()
st.caption(f"AwesomeAwesomeness · v{VERSION} · Catalogue {data['digest'][:12]} · Built with Agentflow · No live crawling or AI inference")
