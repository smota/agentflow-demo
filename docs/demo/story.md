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

## Evidence still to come

Architecture/data council, local ingestion, early public preview, UX council and screenshots, exploratory testing, review/rework, recovery exercise, release council and final publication. These are pending, not completed claims.
