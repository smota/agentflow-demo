# UX council decision — issue #5

Two fresh-context read-only Codex advisors simulated chief designer and UX/QA
perspectives. Parent architect inspected their findings against the actual preview
screenshots and code. This is same-platform advisory collaboration, not human
approval or cross-platform role alternation.

| Finding | Decision and verification |
| --- | --- |
| Host controls overlap mobile brand | Reserve top clearance; inspect actual hosted mobile rendering. |
| Hero/statistics bury search | Compact serif hero and one wrapping statistics strip; search before optional advanced filters. |
| Column-major keyboard/mobile order | One semantic article grid in sorted DOM order; responsive CSS changes columns only. |
| First occurrence can contradict source filter | Match source and topic on the same occurrence; display that occurrence. |
| Missing sharing/reset contract | Allowlisted normalized URL state; explicit share action and privacy warning; reset clears state and URL. |
| Small provenance metadata | Larger wrapping metadata with source-view links; source stars never rank resources. |

Retain native labelled inputs, radio navigation and buttons. Sort Title A–Z or
Title Z–A deterministically before 24-record pagination. Preserve discovery state
when visiting Sources or Delivery story. Unknown URL fields are discarded;
invalid enums/page values fall back or clamp. Search is literal, at most 200
characters. Arbitrary free text cannot be proven non-sensitive: sharing is an
explicit opt-in with a warning, not a claim of secret detection.

Keep advanced source/topic/sort controls in a native expander, open automatically
when a non-default filter is restored. This prioritizes mobile search and results
without removing filtering. No remote fonts, images, inference or crawler imports.

Baseline: [mobile v0.1](images/v0.1-mobile.png). Implementation, tests and final
screenshots are required before accepting these recommendations as resolved.
