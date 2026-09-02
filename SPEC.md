# Issue #2: chore: establish Agentflow governance and durable project foundation

**Epic:** #1

## Background & Problem Statement

The empty demo repository needs mandatory policy, repeatable setup, GitHub governance and durable execution records before application implementation.

## Requirements

- Pin Agentflow v1.0.0 at d61b3ca71189f872a6fd78373076f2aab787f2e0 and initialize through its supported CLI.
- Keep every project-controlled local write inside the demo repository.
- Use work branches into development and release promotion to main.
- Establish specification, acceptance matrix, validation, recovery instructions and issue-linked delivery history.
- Preserve the distinction between the released framework and newer source-only contracts.

## Technical Design

Install the pinned source in ignored .tooling/agentflow and run its init on this empty target. Commit installed governance and lock metadata. Seed project-owned configuration for Python/Streamlit and a Node-based workflow validator. Store transient execution state under ignored .agent-runs, durable summaries in GitHub, and stable documentation under docs/demo. No credentials, global configuration changes or external rollback receipt.

## Acceptance criteria

- [ ] Required policies and validators installed and read.
- [ ] Approved goal, milestones and recovery instructions recorded.
- [ ] Foundation validators pass.
- [ ] GitHub phase handovers, issue-scoped commit and PR verified.

## Test plan

Run the pinned framework doctor, specification validation, project configuration validation and installed workflow checks. Independently review the adoption diff before merge.

## Workflow classification

- **Profile:** standard
- **Risk:** low
- **Effort:** medium
- **Change surfaces:** docs, infra

Empty-repository policy bootstrap. Single-agent multi-role with read-only advisory review as needed. No human security gate is represented as satisfied by simulation.

## Open questions

None.
