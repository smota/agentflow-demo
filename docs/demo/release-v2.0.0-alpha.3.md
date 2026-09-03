# List insights and comparisons

AwesomeAwesomeness 2.0.0-alpha.3 makes the complete 100-star list catalogue easier
to understand and compare without adding hosted crawling or AI processing.

- Adds a first-class Insights workspace with population-labelled KPIs, topic and
  freshness distributions, and a stars-versus-indexed-content relationship view.
- Links search, topic and freshness filters to normalized shareable URL state and
  provides a predictable dashboard reset.
- Compares two to four eligible Awesome lists across observed stars, forks, entries,
  original categories, bounded public contributor counts and freshness.
- Provides accessible table equivalents for charts and exact comparison values.
- Reports indexed-content known/unknown coverage, preserves unknown scatter values,
  and presents freshness ranges in semantic age order.
- Keeps aggregate work index-only and list details lazy for Streamlit Community Cloud.

The accepted data remains the alpha.2 snapshot: 6,377 eligible public lists from 8,373
discovered candidates, 1,282,722 indexed entries, and digest
`0c9ffd50682687d0071b5e81c58b7dc18ea2b8b2d3a0482cd13daba00d0deeba`.
This release does not infer trends from that single observation.

Measured locally against the full index, validated loading took 1.778 seconds,
dashboard aggregation took 0.026 seconds, and Python peak allocation was 251.3 MiB.
The complete suite passed 156 tests before candidate freezing. Hosted desktop and 390px
acceptance remain release-time gates; an early blank startup capture is explicitly not
counted as mobile evidence.

This remains a prerelease. Final fresh-context recovery, story closeout and stable
promotion are tracked in issue #24. Agent-simulated design, data-honesty and performance
council advice is advisory—not human approval.
