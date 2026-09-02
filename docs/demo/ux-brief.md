# UX council common brief — issue #5

The v0.1.0 preview is genuinely live at https://awesomeawesomeness.streamlit.app/.
Review actual screenshots images/v0.1-local.png (desktop) and v0.1-mobile.png
(390x844 public app), plus app.py and SPEC.md. Do not control the browser or write.

Two fresh-context same-platform Codex seats simulate chief designer and UX/QA
specialist perspectives. Parent architect synthesizes and remains sole writer.
No real human approval or cross-platform independence is claimed.

Question: what bounded changes make finding and sharing useful resources pleasant
and usable on desktop/mobile while preserving native accessible controls?

Parent-observed baseline issues: mobile header/brand collision; large hero and
stacked statistics push search below the first screen; desktop cards below fold;
column-major DOM order differs from visible row-major ordering. Missing topic
filter, sort options, clear/reset and shareable query state are planned scope.

Proposed direction: compact editorial hero, three small statistic chips, 2–3-column
row-ordered card grid with single-column mobile fallback, named view navigation,
search then source/topic/sort controls, bounded page controls and explicit copyable
URL. Source view keeps pinned revision/license context. Public story links real
evidence. Avoid inaccessible fake controls, remote images or Markdown execution.

Return prioritized blockers, recommended design/interaction decisions, tests and
tradeoffs. Review only these supplied public/synthetic artifacts and current code.
