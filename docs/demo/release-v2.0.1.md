# v2.0.1 — Visible application identity

[Open the app](https://awesomeawesomeness.streamlit.app/) ·
[Move the Needle](https://movetheneedle.info/) ·
[AgentFlow](https://movetheneedle.info/agent-sdlc/)

AwesomeAwesomeness now identifies Move the Needle as its maintainer and AgentFlow
as the delivery system used to build it. Both identities appear in a compact,
responsive footer strip on every application view, using the supplied brand marks
and stable canonical links.

The identity strip does not add or replace an application navigation destination.
Its links open in a new tab, include visible relationship labels, and stack cleanly
at the tested 390-pixel mobile viewport.

## Validation

- 158 application tests passed;
- AgentFlow workflow validation passed;
- catalogue integrity remained unchanged at digest
  `6765f04bb900eaf6d868e070613d7800faf2d0bec5d5d0577a65d23dc894d5f3`;
- bundled logo assets matched the supplied source files byte for byte; and
- desktop and 390-pixel local browser acceptance passed before promotion.

The GitHub release target and cold hosted behavior are verified independently after
the protected `main` promotion; this pre-promotion note does not claim deployment.
