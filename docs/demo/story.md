# Building AwesomeAwesomeness

This story records actual execution, including limitations and failed checks. It does not treat plans, simulations or local checks as public-release evidence.

## 1. Before the first feature

The starting repository was empty. Read-only readiness checks verified GitHub permissions and the authenticated Streamlit deployment form. An actual disposable pip installation of Streamlit 1.63.0, pytest 9.1.1 and markdown-it-py 4.2.0 succeeded; pip check and a Streamlit AppTest passed after correcting a Windows quoting error in the test harness. Test environments were removed.

Activation created [the delivery epic](https://github.com/smota/agentflow-demo/issues/1) and [foundation issue](https://github.com/smota/agentflow-demo/issues/2). An empty baseline commit established main and development without placing implementation on a protected branch.

## 2. A real capability boundary

The current Agentflow source differed from its latest published release. Current adoption requires a receipt outside the target, conflicting with the demo's folder-only constraint. The verified v1.0.0 release instead provides a supported init command. The demo uses that release, pinned to d61b3ca71189f872a6fd78373076f2aab787f2e0, and records the distinction rather than claiming unreleased capabilities.

Installation placed 335 framework files plus three seed files in the project. Application-specific configuration and recovery instructions are project-owned. The framework source repository was not modified.

## 3. Review returned work, not a rubber stamp

A same-platform, fresh-context advisory reviewer identified two foundation gaps:
missing exact recovery commands and upstream license attribution. The accountable
Codex reviewer returned phase 6 to implementation. Both were repaired before PR
readiness. The [signed handover](https://github.com/smota/agentflow-demo/issues/2#issuecomment-5515259055)
records the return; no real human approval is implied.

The workstation's npm wrapper printed guidance without running tests. Direct use
of the installed npm CLI then ran the actual workflow checks successfully. This
is a harness-aware fallback, not a bypass of a failed validator.

## 4. A real-data preview before polish

The [architecture council](architecture.md) used two fresh-context, read-only Codex
seats. Their objections became implementation requirements: actual license review,
safe token extraction, complete attribution and resource budgets. Static JSON won;
live hosted crawling was rejected because it violated the local-only contract.

The generic capability resolver initially refused a council because delegation was
not declared. This actual desktop harness had already demonstrated a helper, so
the project registered that capability and reran resolution successfully. This is
an environment-specific declaration, not a universal claim about Codex.

Two GitHub searches discovered 39 candidates. Three independently qualified CC0
lists produced 3,037 unique resources from 3,058 source occurrences. The
[source review](source-review.md) pins revisions, licenses and the accepted digest.
Thirty-one tests pass, including offline AppTest, unsafe URLs, parser fixtures,
threshold boundaries and rejection of a stale publication digest. The browser
separately verified 105 terminal-search results and the empty state.

![First local preview, v0.1.0](images/v0.1-local.png)

This screenshot is actual local execution, not a mockup or proof of public hosting.
The first UI intentionally leaves density, filters and shareable journeys for #5.

## Evidence still to come

Early public deployment, UX council/refinement, broader exploratory testing,
interruption recovery, release council and final publication remain pending.
