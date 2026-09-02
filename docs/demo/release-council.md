# Release council — decisions and dispositions

Three fresh-context read-only Codex advisors simulated QA, operations and evidence
reviewers. The parent architect validated findings against actual code/data and
remains the sole writer and accountable standard-profile self-reviewer. No real
human approval or cross-platform role alternation is claimed.

| Seat | Objection | Required disposition |
| --- | --- | --- |
| Evidence | Filtered occurrence supplies topic/source but canonical title/description can disagree (crates.io: Cargo versus Crates) | Project a coherent matching occurrence for display, search and sort; add regression without changing catalogue bytes. |
| Operations | Documented pip install does not configure its cache inside project | Explicit project-local PIP_CACHE_DIR and dev install commands. |
| Operations | Rollback plan lacks guarded commands | Document exact known-good verification, feature-branch restoration, tests, protected promotion and hosted check; do not claim rollback was executed. |
| QA | Share URL text is tested, not the complete reopened journey | Automated generated-link round trip plus actual browser combined filters/page, provenance link and source details. |
| QA | Existing keyboard/mobile evidence is partial | Exercise expanded filters, card/provenance focus, bottom pagination and Sources at narrow widths. |
| All | Final documentation/public identity still pending | Update README/notices/app story and evidence matrix; verify candidate/stable tags and actual hosted version separately. |

The evidence advisor's GitHub reads were network-blocked; parent separately
verified v0.3.0 main/tag/release and public footer. That parent verification is not
misattributed to the advisor. Existing screenshots/test counts are historical;
final checks must be rerun. No new product or infrastructure scope was requested.

## Candidate disposition

All bounded objections were addressed before RC readiness: the real-corpus
metadata regression went red then green; generated-link reopening is automated
and separately browser-tested; expanded 320px filters, visible card focus,
keyboard provenance activation and pagination were exercised. Installation now
sets PIP_CACHE_DIR locally; rollback is guarded and labelled unexecuted. The
72-test suite and evidence index cover the final scope. No finding was silently
deferred; stable hosted acceptance remains a publication gate, not a code finding.
