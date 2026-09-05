"""Evidence-backed AgentFlow delivery story for the public Streamlit app.

Renders from the live session-record ledger (`data/sessions/*.json`, aggregated into
`data/sessions-index.json` by `tools/derive_sessions.py`) instead of hand-authored per-build prose.
Every session record is contributed by whichever harness merged the PR it documents -- see
`schemas/session-record.schema.json` and the architecture note in the repository's delivery-story
plan. `data/delivery-story.json` is retained only for editorial framing that has no natural home in
a session record: hero copy, narrative spine/boundary prose, and the watermarked screenshot gallery.
"""
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
.session-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1rem 0 1.5rem}
.session-card{border:1px solid #dce8e4;border-radius:14px;padding:1rem;background:#fbfdfc}
.session-card b{display:block;color:#087f73;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35rem}
.session-card strong{color:#173c35;line-height:1.35}
.session-card small{display:block;color:#62716c;margin-top:.5rem;line-height:1.4}
.badge{display:inline-block;border-radius:999px;padding:.08rem .55rem;font-size:.68rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;margin-right:.3rem}
.badge-platform{background:#e7f3f1;color:#087f73}
.badge-profile{background:#f2f0fb;color:#4c3fb0}
.badge-high-assurance{background:#fdecec;color:#b3261e}
.decision-box{border:1px solid #dce8e4;border-radius:14px;padding:1rem 1.1rem;background:#fbfdfc;height:100%}
.decision-box b{display:block;color:#087f73;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem}
.decision-box p{color:#43554f;line-height:1.55;margin:.15rem 0 .8rem}
.finding-box{border:1px solid #f0e2b8;background:#fffaf0;border-radius:12px;padding:.8rem 1rem;margin:.4rem 0;color:#5c4a1d;line-height:1.55}
.boundary{font-size:.86rem;color:#53635e;background:#f7faf9;border:1px solid #dce8e4;border-radius:12px;padding:1rem 1.1rem;line-height:1.65}
.watermark-note{font-size:.75rem;color:#62716c;margin:.2rem 0 1rem}
@media(max-width:800px){.session-grid{grid-template-columns:1fr}.workflow{grid-template-columns:1fr}.workflow span:not(:last-child):after{content:' ↓';}.story-lede{font-size:1rem}}
</style>"""


def load_story(path: Path) -> dict:
    story = json.loads(path.read_text(encoding="utf-8"))
    if story.get("schemaVersion") != 2 or not story.get("hero"):
        raise ValueError("Unsupported delivery story manifest")
    return story


def load_sessions_index(path: Path) -> dict:
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("formatVersion") != 1 or "timeline" not in index:
        raise ValueError("Unsupported sessions-index manifest")
    return index


def load_session_record(session_id: str) -> dict:
    path = APP_ROOT / "data" / "sessions" / f"{session_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


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


def _badges(row: dict) -> str:
    parts = [f'<span class="badge badge-platform">{html.escape(row["platform"])}</span>',
             f'<span class="badge badge-profile">{html.escape(row["workflowProfile"])}</span>']
    if row.get("humanReviewRequired"):
        parts.append('<span class="badge badge-high-assurance">Human review required</span>')
    return ''.join(parts)


def _story_metrics(sessions_index: dict, insight: dict) -> None:
    counts = sessions_index["counts"]
    with st.container(key="delivery_metrics"):
        cols = st.columns(4)
    cols[0].metric("Session records", counts["sessions"])
    cols[1].metric("PR sessions", counts["pr"])
    cols[2].metric("Rollup waves", counts["rollup"])
    high_assurance = sum(1 for row in sessions_index["timeline"] if row["humanReviewRequired"])
    cols[3].metric("High-assurance gates", high_assurance)
    st.caption(
        f'Session ledger generated {sessions_index["generatedAt"][:10]} · '
        f'Product snapshot observed {insight["observed_at"]}. Repository totals are a point-in-time snapshot, not a live GitHub API feed.'
    )


def _session_cards(rows: list[dict]) -> None:
    cards = []
    for row in rows:
        link = (
            f'<a href="{row["prUrl"]}" target="_blank" rel="noopener noreferrer">PR #{row["prNumber"]} ↗</a>'
            if row.get("prUrl") else f'{len(row.get("children") or [])} child session(s)'
        )
        cards.append(
            '<div class="session-card">'
            f'<b>{html.escape(row.get("wave") or row["kind"].upper())} · {row["mergedAt"][:10]}</b>'
            f'<strong>{html.escape(row["title"])}</strong>'
            f'<small>{_badges(row)}<br>{link}</small>'
            '</div>'
        )
    st.html('<div class="session-grid">' + ''.join(cards) + '</div>')


def _timeline(sessions_index: dict) -> None:
    waves = [w for w in dict.fromkeys(row.get("wave") for row in sessions_index["timeline"]) if w]
    scope = st.selectbox("Filter the timeline by wave", ["All waves", *waves], key="delivery_wave")
    rows = sessions_index["timeline"]
    if scope != "All waves":
        rows = [row for row in rows if row.get("wave") == scope]
    _session_cards(rows)
    st.caption(f'{len(rows)} session record(s) shown, ordered by merge date. Every record is generated from its own PR\'s `## Agent review` manifest.')


def _deep_dive(sessions_index: dict) -> None:
    labels = {f'{row["title"]} · {row["mergedAt"][:10]}': row["id"] for row in reversed(sessions_index["timeline"])}
    selected_label = st.selectbox("Open a session's full evidence", list(labels), key="delivery_deep_dive")
    record = load_session_record(labels[selected_label])

    meta_cols = st.columns(4)
    meta_cols[0].metric("Harness", record["harness"]["platform"])
    meta_cols[1].metric("Workflow profile", record["sdlc"]["workflowProfile"])
    meta_cols[2].metric("Review", record["sdlc"]["review"])
    tests_passed = record.get("verification", {}).get("testsPassed")
    meta_cols[3].metric("Tests passed", tests_passed if tests_passed is not None else "unknown")

    if record["sdlc"].get("phasesRun"):
        spans = ''.join(f'<span>{html.escape(phase)}</span>' for phase in record["sdlc"]["phasesRun"])
        st.html(f'<div class="workflow">{spans}</div>')

    if record.get("decisions"):
        st.caption("Governed decisions recorded on this session")
        for decision in record["decisions"]:
            cols = st.columns(3)
            cols[0].html(f'<div class="decision-box"><b>Observation</b><p>{html.escape(decision["observation"])}</p></div>')
            cols[1].html(f'<div class="decision-box"><b>AgentFlow rule</b><p>{html.escape(decision["rule"])}</p></div>')
            cols[2].html(f'<div class="decision-box"><b>Result</b><p>{html.escape(decision["result"])}</p></div>')

    if record.get("findings"):
        st.caption("Findings only surfaced by running the real thing")
        for finding in record["findings"]:
            st.html(f'<div class="finding-box"><strong>{html.escape(finding["summary"])}</strong><br>{html.escape(finding["howFound"])}</div>')

    issues = record.get("repository", {}).get("issues", [])
    if issues:
        issue_frame = pd.DataFrame(issues)
        st.dataframe(issue_frame, hide_index=True, width="stretch", column_config={
            "number": "Issue", "relation": "Relation", "url": st.column_config.LinkColumn("Link", display_text="Open ↗"),
        })

    if record.get("children"):
        st.caption(f'Child sessions: {", ".join(record["children"])}')

    if record.get("evidence"):
        st.caption("Evidence")
        for ref in record["evidence"]:
            st.link_button(f'{ref["kind"]} ↗', ref["uri"])

    follow_ups = record.get("followUps") or []
    if follow_ups:
        st.caption("Follow-up issues: " + ", ".join(f"#{n}" for n in follow_ups))


def _harness_comparison(sessions_index: dict) -> None:
    frame = pd.DataFrame(sessions_index["harnessComparison"])
    if frame.empty:
        st.info("No session records yet.")
        return
    long_frame = frame.melt(id_vars=["platform"], value_vars=["highAssuranceRate", "findingsRate"],
                             var_name="metric", value_name="rate")
    chart = (
        alt.Chart(long_frame)
        .mark_bar()
        .encode(
            x=alt.X("platform:N", title="Harness platform"),
            y=alt.Y("rate:Q", title="Rate", axis=alt.Axis(format="%")),
            color=alt.Color("metric:N", title="Metric"),
            xOffset="metric:N",
            tooltip=["platform:N", "metric:N", alt.Tooltip("rate:Q", format=".1%")],
        )
        .properties(height=340, title="High-assurance rate and findings rate per harness")
    )
    st.altair_chart(chart, width="stretch")
    sessions_chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(x=alt.X("platform:N", title="Harness platform"), y=alt.Y("sessions:Q", title="Sessions"),
                tooltip=["platform:N", "sessions:Q"])
        .properties(height=260, title="Sessions per harness")
    )
    st.altair_chart(sessions_chart, width="stretch")
    with st.expander("Accessible harness-comparison data"):
        st.dataframe(frame, hide_index=True, width="stretch")
    st.caption("Computed by tools/derive_sessions.py from every session record's harness.platform, sdlc.workflowProfile, and findings[]. A small sample size can produce noisy rates.")


def _sdlc_conformance(sessions_index: dict) -> None:
    frame = pd.DataFrame(sessions_index["sdlcConformance"])
    review_frame = pd.DataFrame(sessions_index["reviewDistribution"])
    cols = st.columns(2)
    with cols[0]:
        st.bar_chart(frame, x="workflowProfile", y="sessions", height=320)
        with st.expander("Accessible workflow-profile data"):
            st.dataframe(frame, hide_index=True, width="stretch")
    with cols[1]:
        st.bar_chart(review_frame, x="review", y="sessions", height=320)
        with st.expander("Accessible review-type data"):
            st.dataframe(review_frame, hide_index=True, width="stretch")
    st.caption("Workflow-profile and review-type distribution across every session record -- the SDLC-conformance view.")


def _tests_over_time(sessions_index: dict) -> None:
    frame = pd.DataFrame(sessions_index["testsOverTime"])
    if frame.empty:
        st.info("No session yet records a testsPassed count.")
        return
    chart = (
        alt.Chart(frame)
        .mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3)
        .encode(
            x=alt.X("mergedAt:N", title="Merge date", sort=frame["mergedAt"].tolist()),
            y=alt.Y("testsPassed:Q", title="Passing tests", scale=alt.Scale(zero=False)),
            tooltip=["id:N", "title:N", "mergedAt:N", "testsPassed:Q"],
        )
        .properties(height=340, title="Verification suite size at each session that recorded a count")
    )
    st.altair_chart(chart, width="stretch")
    with st.expander("Accessible test-count data"):
        st.dataframe(frame, hide_index=True, width="stretch")
    st.caption("Only sessions whose PR manifest recorded a testsPassed count are plotted; unknown is never shown as zero.")


def render_delivery(root: Path, index: dict) -> None:
    # Preview fixtures replace the data root; editorial evidence and branded media
    # remain package-owned so preview and production render the same story.
    story = load_story(APP_ROOT / "data" / "delivery-story.json")
    sessions_index = load_sessions_index(APP_ROOT / "data" / "sessions-index.json")
    insight = dashboard(index, eligible_lists(index))
    st.html(STORY_CSS)
    hero = story["hero"]
    st.html(f'<div class="story-kicker">{html.escape(hero["kicker"])}</div>')
    st.title(hero["title"])
    st.html(
        f'<p class="story-lede">{html.escape(hero["lede"])}</p>'
        f'<div class="story-claim">{html.escape(hero["claim"])}</div>'
    )
    _story_metrics(sessions_index, insight)

    _section(
        "The product is the evidence. The delivery process is the story.",
        "AwesomeAwesomeness is a real Streamlit application for discovering and comparing curated Awesome lists. This page is not a hand-written retrospective: every card below is generated from a session record (schemas/session-record.schema.json) derived from the merged PR's own `## Agent review` manifest. New work contributes to this story automatically, from any harness."
    )
    st.html(
        '<div class="workflow"><span>Product manager</span><span>Analyst</span><span>Architect</span><span>Planner</span><span>Developer</span><span>Tester</span><span>Reviewer</span><span>Writer</span><span>PR readiness</span></div>'
    )
    st.caption("Canonical AgentFlow phase sequence. Each session record's own phasesRun (deep-dive below) shows what actually ran for that session.")

    _section("The deterministic spine", story["narrative"]["spine"])

    st.subheader("Delivery timeline")
    _timeline(sessions_index)

    product_cols = st.columns(4)
    product_cols[0].metric("Eligible lists", f'{index["counts"]["eligible"]:,}')
    product_cols[1].metric("Candidates", f'{len(index["lists"]):,}')
    product_cols[2].metric("Indexed entries", f'{insight["total_entries"]:,}')
    product_cols[3].metric("Fresh ≤30 days", f'{insight["fresh_30"]:,}')
    pending = index["counts"].get("pending", 0)
    excluded = index["counts"].get("excluded", 0)
    st.caption(f'Current versioned app data · {pending:,} pending · {excluded:,} excluded · minimum {index["min_stars"]} stars · digest {index["digest"][:12]}…')

    st.subheader("Session deep-dive")
    _deep_dive(sessions_index)

    st.subheader("Harness comparison")
    _harness_comparison(sessions_index)

    st.subheader("SDLC conformance")
    _sdlc_conformance(sessions_index)

    st.subheader("Verification grew with the delivery")
    _tests_over_time(sessions_index)

    st.subheader("The delivery, visibly")
    logo_path = APP_ROOT / "awesome" / "assets" / "move-the-needle-icon.png"
    screenshots = story.get("screenshots", [])
    if screenshots:
        image_tabs = st.tabs([shot["caption"].split(" · ", 1)[0] for shot in screenshots])
        for image_tab, shot in zip(image_tabs, screenshots):
            with image_tab:
                image_tab.image(watermarked_image(APP_ROOT / shot["path"], logo_path), caption=shot["caption"], width="stretch")
                note = story.get("waveNotes", {}).get(shot.get("wave"))
                if note:
                    st.caption(note)
    for wave, note in story.get("waveNotes", {}).items():
        if not any(shot.get("wave") == wave for shot in screenshots):
            st.caption(f'{wave}: {note}')
    st.html('<div class="watermark-note">Every screenshot displayed in this story is rendered with the Move the Needle logo and the visible movetheneedle.info watermark.</div>')

    _section("Evidence has boundaries", story["narrative"]["boundaries"])
    st.html('<div class="boundary"><b>Direct evidence</b> is linked to its durable artifact via each session record\'s <code>evidence[]</code>. <b>Derived metrics</b> come from <code>data/sessions-index.json</code>. <b>Product metrics</b> are calculated from the current app snapshot. Unknown is never converted to zero, and a historical checkpoint is never presented as current state.</div>')

    _section("Inspect the delivery, not just the result", story["narrative"]["closing"])
    st.html('<div class="story-claim">Different agents. Deterministic workflow. Consistent delivery.</div>')
