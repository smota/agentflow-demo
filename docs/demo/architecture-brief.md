# Architecture council common brief — issue #4

Decision: simplest credible free-hosted discovery app, with all crawler and application
AI processing local. Compare static JSON, SQLite and hosted live crawling. Source
repositories must be public, genuinely Awesome resource lists and observed at >=50k
stars through GitHub search; linked resources themselves need not qualify.

Preview proposal: local Python + markdown-it parser, bounded GitHub CLI API calls,
versioned JSON artifact, Streamlit search and source attribution. No paid API, runtime
token, user accounts or model inference. Initial licensed subset is acceptable when
candidate exclusions and coverage limits are explicit. Never execute remote content.

Two read-only fresh-context Codex seats: data/risk critic and implementation/testability
critic. Parent architect synthesizes. Same-platform advice is not human approval or
cross-platform role alternation. Helpers may inspect public source/license evidence and
read local policy; no writes, installs or remote mutations. Give bounded blockers,
options/tradeoffs, recommendations and test requirements, not code implementation.

Harness evidence: generic v1.0.0 defaults say Codex delegation is unavailable. This
desktop session successfully ran the read-only foundation helper. Project config now
declares native delegated-subagents for this actual harness; portability requires
rechecking that capability in another executor. No gate is satisfied merely by config.
