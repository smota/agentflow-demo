"""Evidence-backed AgentFlow delivery story for the public Streamlit app."""
from __future__ import annotations

from io import BytesIO
import html
import json
from pathlib import Path

import altair as alt
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

from awesome.insights import dashboard, eligible_lists


APP_ROOT = Path(__file__).resolve().parents[1]


STORY_CSS = """<style>
.story-kicker{margin-top:1rem;color:#087f73;font-size:.72rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase}
.story-lede{max-width:850px;color:#4d5f59;font-size:1.08rem;line-height:1.7;margin:.6rem 0 1.4rem}
.story-claim{border-left:4px solid #087f73;background:#eff8f5;padding:1rem 1.15rem;margin:1.2rem 0 1.5rem;border-radius:0 12px 12px 0;color:#173c35;font-family:Georgia,serif;font-size:1.3rem}
.story-section{margin-top:2.6rem;padding-top:.25rem}
.story-section h2{font-family:Georgia,serif;color:#173c35;font-size:clamp(1.7rem,3vw,2.35rem);font-weight:400;letter-spacing:-.035em;margin-bottom:.4rem}
.story-section p{color:#4d5f59;line-height:1.72;max-width:900px}
.workflow{display:grid;grid-template-columns:repeat(9,minmax(92px,1fr));gap:.35rem;margin:1rem 0 1.4rem;overflow-x:auto;padding-bottom:.5rem}
.workflow span{background:#f7faf9;border:1px solid #dce8e4;border-radius:10px;padding:.7rem .5rem;text-align:center;color:#173c35;font-size:.75rem;min-width:92px}
.workflow span:not(:last-child):after{content:'→';color:#8da39c;margin-left:.45rem}
.episode-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1rem 0 1.5rem}
.episode{border:1px solid #dce8e4;border-radius:14px;padding:1rem;background:#fbfdfc}
.episode b{display:block;color:#087f73;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35rem}
.episode strong{color:#173c35;line-height:1.35}
.episode small{display:block;color:#62716c;margin-top:.5rem;line-height:1.4}
.command-spine{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#102d29;color:#d9f3ec;border-radius:14px;padding:1rem 1.2rem;line-height:1.9;overflow-x:auto;margin:1rem 0}
.command-spine em{color:#7ed3c2;font-style:normal}
.decision-box{border:1px solid #dce8e4;border-radius:14px;padding:1rem 1.1rem;background:#fbfdfc;height:100%}
.decision-box b{display:block;color:#087f73;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem}
.decision-box p{color:#43554f;line-height:1.55;margin:.15rem 0 .8rem}
.boundary{font-size:.86rem;color:#53635e;background:#f7faf9;border:1px solid #dce8e4;border-radius:12px;padding:1rem 1.1rem;line-height:1.65}
.watermark-note{font-size:.75rem;color:#62716c;margin:.2rem 0 1rem}
@media(max-width:800px){.episode-grid{grid-template-columns:1fr}.workflow{grid-template-columns:1fr}.workflow span:not(:last-child):after{content:' ↓';}.story-lede{font-size:1rem}}
</style>"""


def load_story(path: Path) -> dict:
    story = json.loads(path.read_text(encoding="utf-8"))
    if story.get("schemaVersion") != 1 or not story.get("episodes"):
        raise ValueError("Unsupported delivery story manifest")
    return story


def watermarked_image(path: Path, logo_path: Path) -> bytes:
    """Return display bytes with an embedded Move the Needle logo and site text."""
    with Image.open(path) as source:
        image = source.convert("RGBA")
    with Image.open(logo_path) as source_logo:
        logo = source_logo.convert("RGBA")

    scale = max(1, image.width // 1100)
    pad = 12 * scale
    logo_size = 34 * scale
    logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
    text = "movetheneedle.info"
    font = ImageFont.load_default(size=14 * scale)
    probe = ImageDraw.Draw(image)
    box = probe.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    badge_width = pad * 3 + logo.width + text_width
    badge_height = max(logo.height, text_height) + pad * 2
    x = image.width - badge_width - pad
    y = image.height - badge_height - pad
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (x, y, x + badge_width, y + badge_height),
        radius=10 * scale,
        fill=(16, 45, 41, 232),
        outline=(126, 211, 194, 255),
        width=max(1, scale),
    )
    overlay.alpha_composite(logo, (x + pad, y + (badge_height - logo.height) // 2))
    draw.text(
        (x + pad * 2 + logo.width, y + (badge_height - text_height) // 2 - box[1]),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )
    result = Image.alpha_composite(image, overlay).convert("RGB")
    output = BytesIO()
    result.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def _section(title: str, body: str) -> None:
    st.html(f'<div class="story-section"><h2>{html.escape(title)}</h2><p>{body}</p></div>')


def _story_metrics(story: dict, insight: dict) -> None:
    with st.container(key="delivery_metrics"):
        cols = st.columns(4)
    cols[0].metric("Delivery episodes", len(story["episodes"]))
    cols[1].metric("Fresh-context recoveries", story["recovery"]["successfulFreshContext"])
    cols[2].metric("Public releases", story["repository"]["releases"])
    cols[3].metric("Final verification suite", f'{story["episodes"][-1]["tests"]} tests')
    st.caption(
        f'Versioned delivery evidence observed {story["observedAt"]} · '
        f'Product snapshot observed {insight["observed_at"]}. Repository totals are a point-in-time snapshot, not a live GitHub API feed.'
    )


def _episode_cards(story: dict) -> None:
    cards = []
    for episode in story["episodes"]:
        cards.append(
            '<div class="episode">'
            f'<b>{html.escape(episode["label"])}</b>'
            f'<strong>{html.escape(episode["short"])}</strong>'
            f'<small>{episode["tests"]} tests · {html.escape(episode["release"])} · '
            f'<a href="{episode["url"]}" target="_blank" rel="noopener noreferrer">Issue #{episode["issue"]} ↗</a></small>'
            '</div>'
        )
    st.html('<div class="episode-grid">' + ''.join(cards) + '</div>')


def _command_dashboard(story: dict) -> None:
    st.subheader("The deterministic command rail")
    st.write(
        "Agents interpret evidence and propose decisions. AgentFlow commands inspect authority, bind intent to a digest, "
        "apply the reviewed transition, or reconcile its result. Product checks remain a separate evidence-producing layer."
    )
    st.html(
        '<div class="command-spine"><em>source-plan</em> → status → context → checkpoint → pause<br>'
        '→ <em>resume preview</em> → resume confirm → read-back → verify<br>'
        '→ <em>publish preview</em> → publish confirm → reconcile</div>'
    )
    frame = pd.DataFrame(story["commands"])
    st.dataframe(frame, hide_index=True, width="stretch", column_config={
        "stage": "Function", "command": "Deterministic command", "decision": "What it establishes"
    })
    st.caption("Documented command types and exercised decisions. Totals are not inferred from prose or terminal scrollback.")


def _decision_replay(story: dict, episode: str) -> None:
    decisions = story["decisions"]
    if episode != "All builds":
        name = episode.split(" ·", 1)[0]
        scoped = [item for item in decisions if item["episode"] == name]
        if scoped:
            decisions = scoped
    labels = [item["label"] for item in decisions]
    selected = st.selectbox("Replay a governed decision", labels, key="delivery_decision")
    item = next(item for item in decisions if item["label"] == selected)
    cols = st.columns(3)
    cols[0].html(f'<div class="decision-box"><b>Observation · {html.escape(item["episode"])}</b><p>{html.escape(item["observation"])}</p></div>')
    cols[1].html(f'<div class="decision-box"><b>AgentFlow rule</b><p>{html.escape(item["rule"])}</p></div>')
    cols[2].html(f'<div class="decision-box"><b>Workflow result</b><p>{html.escape(item["result"])}</p></div>')


def _evidence_explorer(story: dict) -> None:
    st.subheader("Follow every claim to durable evidence")
    concepts = [item["concept"] for item in story["evidence"]]
    selected = st.selectbox("Evidence concept", concepts, key="delivery_evidence")
    item = next(item for item in story["evidence"] if item["concept"] == selected)
    st.link_button(f'{item["artifact"]} ↗', item["url"])
    st.caption("GitHub issues, PRs, commits, releases and checked manifests are public provenance. Local Codex session links are intentionally excluded.")


def render_delivery(root: Path, index: dict) -> None:
    # Preview fixtures replace the data root; editorial evidence and branded media
    # remain package-owned so preview and production render the same story.
    story = load_story(APP_ROOT / "data" / "delivery-story.json")
    insight = dashboard(index, eligible_lists(index))
    st.html(STORY_CSS)
    st.html('<div class="story-kicker">An inspectable AgentFlow delivery story</div>')
    st.title("Different agents. Deterministic workflow. Consistent delivery.")
    st.html(
        '<p class="story-lede">AI agents can generate code. Delivery requires something harder: preserving intent, evidence and decision quality as work moves across roles, sessions, candidates and release gates. AwesomeAwesomeness was built through three separate delivery episodes. Agents changed. Context windows ended. AgentFlow kept the delivery coherent.</p>'
        '<div class="story-claim">Agents reason. AgentFlow makes delivery repeatable.</div>'
    )
    _story_metrics(story, insight)
    episode = st.selectbox("Explore the delivery through", ["All builds", *[x["label"] for x in story["episodes"]]], key="delivery_episode")
    _episode_cards(story)

    _section(
        "The product is the evidence. The delivery process is the story.",
        "AwesomeAwesomeness is a real Streamlit application for discovering and comparing curated Awesome lists. But this is not primarily the story of a catalogue. It is the story of how AgentFlow governed an end-to-end SDLC from an empty repository to a public v2.0.1 release. The application gives us something concrete to test. AgentFlow gives the work continuity."
    )
    st.html(
        '<div class="workflow"><span>Product manager</span><span>Analyst</span><span>Architect</span><span>Planner</span><span>Developer</span><span>Tester</span><span>Reviewer</span><span>Writer</span><span>PR readiness</span></div>'
    )
    st.caption("Accountable functions in a predominantly single-agent, multi-role delivery—not a claim that every role was a different human or model.")

    _section(
        "The deterministic spine",
        "An agent can interpret incomplete information and propose a course of action. AgentFlow validates whether that proposal belongs to the current goal, role, candidate and gate. A passing test does not prove deployment. A tag does not prove public behavior. An agent’s confidence does not advance a gate. Every transition needs evidence appropriate to that decision."
    )
    _command_dashboard(story)

    _section(
        "Build 1 · Establish a governed path",
        "The first episode turned a broad product request into role-owned work, signed handovers, issue-scoped branches, protected pull requests and explicit release gates. When automated tests passed but the exact browser journey returned zero Crates results, Review returned the work to Implementation. The claim was withdrawn, the stale runtime was restarted and the journey was repeated. The significant event was not the defect: it was that contradictory evidence changed the workflow without erasing the earlier record. v1.0.0 closed at an exact commit with 72 tests and separately verified public behavior."
    )

    _section(
        "Build 2 · Scale without losing control",
        "The second episode expanded a small preview into a list-first discovery and analytics product. AgentFlow preserved decomposition across the v2 epic and its child issues while the product grew to thousands of lists and more than a million indexed entries. Implementation correctness, data integrity, performance, browser behavior, release identity, GitHub publication and hosted behavior remained separate evidence domains."
    )
    product_cols = st.columns(4)
    product_cols[0].metric("Eligible lists", f'{index["counts"]["eligible"]:,}')
    product_cols[1].metric("Candidates", f'{len(index["lists"]):,}')
    product_cols[2].metric("Indexed entries", f'{insight["total_entries"]:,}')
    product_cols[3].metric("Fresh ≤30 days", f'{insight["fresh_30"]:,}')
    pending = index["counts"].get("pending", 0)
    excluded = index["counts"].get("excluded", 0)
    st.caption(f'Current versioned app data · {pending:,} pending · {excluded:,} excluded · minimum {index["min_stars"]} stars · digest {index["digest"][:12]}…')

    st.subheader("Verification grew with the delivery")
    tests = pd.DataFrame(story["testCheckpoints"])
    if episode != "All builds":
        scoped = tests[tests["episode"] == episode.split(" ·", 1)[0]]
        if not scoped.empty:
            tests = scoped
    checkpoint_order = tests["checkpoint"].tolist()
    test_chart = (
        alt.Chart(tests)
        .mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3)
        .encode(
            x=alt.X("checkpoint:N", title="Delivery checkpoint", sort=checkpoint_order),
            y=alt.Y("tests:Q", title="Passing tests", scale=alt.Scale(zero=False)),
            color=alt.Color("episode:N", title="Episode"),
            tooltip=["episode:N", "checkpoint:N", "tests:Q"],
        )
        .properties(height=340, title="Verification suite at documented checkpoints")
    )
    st.altair_chart(test_chart, width="stretch")
    with st.expander("Accessible checkpoint data"):
        st.dataframe(tests, hide_index=True, width="stretch")
    st.caption("Suite size at documented checkpoints; this is not a proxy for productivity or cumulative effort.")

    _section(
        "The climax · A new agent continues correctly",
        "The strongest claim is not that the original agent remembered what it had done. It is that a new process could reconstruct what mattered without that memory. The first v2 fresh-context attempt recovered only part of the state and was rejected. After the durable coordination ref was fetched, a second ephemeral read-only process—without prior conversation, memory, network or local scratch—reconstructed the issue, exact candidate, current gate, evidence sequence, external projection and next safe action. Different process. Different context. Same delivery position."
    )
    consistency = pd.DataFrame(story["consistency"])
    st.dataframe(consistency, hide_index=True, width="stretch", column_config={
        "field": "Required field", "recorded": "Recorded state", "reconstructed": "Fresh agent recovered", "match": "Result"
    })
    recovery = story["recovery"]
    rec_cols = st.columns(4)
    rec_cols[0].metric("Successful reconstructions", recovery["successfulFreshContext"])
    rec_cols[1].metric("Partial attempts rejected", recovery["partialAttemptsRejected"])
    rec_cols[2].metric("Writer generation", f'{recovery["initialGeneration"]} → {recovery["replacementGeneration"]}')
    rec_cols[3].metric("Projection", f'{recovery["publicationAttempts"]} attempts → {recovery["createdComments"]} comment')

    _section(
        "Recovery is a protocol, not a timeout",
        "The original writer was paused before authority transferred from generation 0 to generation 1. An uncertain apply response was resolved by reading durable state, not by blindly retrying. Reusing the consumed recovery plan and acting as the obsolete writer were both rejected with conflict exit code 4. Applying the same GitHub projection twice reconciled to one comment. Valid once did not mean valid forever, and former authority could not silently continue."
    )
    st.html(
        '<div class="command-spine">Writer G0 ─ checkpoint & pause ─▶ durable state<br>'
        'durable state ─ digest-bound resume ─▶ Writer G1<br>'
        'Writer G0 ─ stale action ─▶ <em>REJECT · exit 4</em><br>'
        'publish attempt ×2 ─ reconcile ─▶ <em>one GitHub comment</em></div>'
    )

    _section(
        "Build 3 · Consistency in everyday change",
        "The third episode added persistent maintainer and AgentFlow identity links. A focused test exposed that temporary preview roots could not resolve package-owned assets. The implementation separated data location from bundled identity assets, then passed focused UI checks, desktop and measured 390-pixel inspection, the 158-test suite, workflow validation and catalogue integrity. The change moved through issue #39, integration PR #40, promotion PR #41 and v2.0.1. AgentFlow remained the operating model even when the change was small."
    )

    st.subheader("Decision replay")
    _decision_replay(story, episode)

    st.subheader("The delivery, visibly")
    image_specs = (
        ("docs/demo/images/v0.1-local.png", "Build 1 · the first local product checkpoint"),
        ("docs/demo/images/v2-insights-public-desktop.png", "Build 2 · the public Insights baseline"),
        ("docs/demo/images/v2-rc1-local-mobile.jpg", "Build 2 · measured 390px release-candidate acceptance"),
    )
    image_tabs = st.tabs(("Build 1", "Build 2 dashboard", "Build 2 mobile"))
    logo_path = APP_ROOT / "awesome" / "assets" / "move-the-needle-icon.png"
    for image_tab, (relative, caption) in zip(image_tabs, image_specs):
        image_tab.image(watermarked_image(APP_ROOT / relative, logo_path), caption=caption, width="stretch")
    st.html('<div class="watermark-note">Every screenshot displayed in this story is rendered with the Move the Needle logo and the visible movetheneedle.info watermark.</div>')

    _section(
        "Evidence has boundaries",
        "This delivery was predominantly single-agent and multi-role. Fresh-context advisors were same-platform Codex processes, not independent human reviewers. Process IDs demonstrate cooperative replacement, not hostile-host authentication. Local checks do not prove GitHub state; GitHub checks do not prove a release; a release does not prove the hosted application changed. AgentFlow did not write the application by itself. Agents and tools produced observations; AgentFlow governed how those observations became durable delivery decisions."
    )
    st.html('<div class="boundary"><b>Direct evidence</b> is linked to its durable artifact. <b>Derived metrics</b> come from this versioned manifest. <b>Product metrics</b> are calculated from the current app snapshot. Unknown is never converted to zero, and a historical checkpoint is never presented as current state.</div>')

    _section(
        "Inspect the delivery, not just the result",
        "AwesomeAwesomeness is the shipped case. AgentFlow is the reason its delivery can be reconstructed. Start with any decision, transition or metric and follow it back to the issue, manifest, pull request, release or public observation that supports it."
    )
    _evidence_explorer(story)
    st.html('<div class="story-claim">Different agents. Deterministic workflow. Consistent delivery.</div>')
