# Exploratory QA record

Actual browser interactions; not substituted by AppTest. Historical v0.1/v0.2
screenshots are labelled in the story. Final stable public smoke is recorded
separately in the final issue/release receipt.

| Journey | Observed result |
| --- | --- |
| Search/empty/reset | Terminal 105 matches; nonsense 0 with useful reset; reset restores 3,037. |
| Combined share | q=a, Node.js source, Command-line apps, Z–A, page 2 generated a URL; separate public browser tab restored 47 results, positions 25–47, page 2 of 2. |
| Generated-share automation | New AppTest instance initialized from the actual generated URL reproduces all state fields. |
| Expanded narrow filters | At 320px, document width and scroll width both 320; native source/topic/sort controls stack and remain labelled. |
| Keyboard | Tab from source reaches Topic, then Sort. Tab from Share reaches first resource link; visible ochre focus ring inspected. Next Tab reaches About-source. |
| Provenance activation | Enter on About Node.js opens Sources in a new tab, Node.js expanded, 66,685 observed stars, 591 entries, CC0 text and pinned b8e1c0c… revision. |
| Pagination | Last page has Next disabled; Enter on Previous returns page 1 of 2, positions 1–24. |
| Source mobile | Actual 390px source view inspected with long source name, pinned revision and licence context. |
| Occurrence accuracy | Council found Cargo/Crates mismatch for crates.io under Registries. Regression failed on Cargo, then passed on Crates with its selected-source description/search. |

Coverage is representative, not an exhaustive assistive-technology certification
or audit of every external link. No credentials, private data or account screens
are used in published screenshots.

## Verification discrepancy and correction

The long-running local server initially returned zero results for the new
`official public registry` + Rust/Registries search despite passing fresh-process
tests. A tester summary prematurely called the browser check passed. Review
explicitly withdrew that claim and returned to implementation. After stopping and
restarting the local server, with no further application-code change, the exact
controls returned one Crates result and its correct description. This is
consistent with stale local module state, not evidence that a version footer alone
proves the loaded code. Final hosted checks must exercise the behavior too.
