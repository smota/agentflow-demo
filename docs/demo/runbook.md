# Delivery runbook

## Resume before doing work

1. Read root AGENTS.md, CODEX.md, docs/agent-workflow.md, docs/issue-standards.md and current SPEC.md.
2. Read docs/demo/goal.md and the ignored .agent-runs/checkpoint.json if present.
3. Inspect Git status, branch and HEAD; preserve unknown changes. Confirm remote issue/PR/release state before retrying any external operation.
4. Read the current issue's workflow-status and handover comments, which outrank the local checkpoint.
5. Verify any referenced process is actually alive before launching a replacement. Only one implementation writer.
6. Revalidate changed code/data and stale acceptance before continuing the recorded next action.

## Storage boundaries

- Stable plan, architecture, story and runbook are committed.
- GitHub is authoritative for issue/phase, PR, release and closeout status.
- .agent-runs stores local checkpoints, role-pass drafts, logs and unfinished artifacts; never commit it.
- .tooling/agentflow holds the pinned release source. .venv, .cache and data/raw are local-only.
- Set TEMP/TMP and package caches to project-local directories for tool commands that write them. Do not use global install or change global Git identity/trust.

## Installation

Pin Agentflow v1.0.0 / d61b3ca71189f872a6fd78373076f2aab787f2e0. Its supported init installs framework-owned files and seeds missing project policy. Init is only for the empty initial target; use doctor and reviewed sync for later changes. Do not rerun init over authored edits.

The newer source's adopt command requires an external rollback receipt; it is not used because it conflicts with the folder-only requirement. Do not silently replace the pinned version.

From the demo root in PowerShell, restore the ignored source only if absent:

```powershell
$demoRoot = (Get-Location).Path
New-Item -ItemType Directory -Force .cache/tmp, .cache/npm, .tooling | Out-Null
$env:TEMP = Join-Path $demoRoot '.cache/tmp'
$env:TMP = $env:TEMP
$env:npm_config_cache = Join-Path $demoRoot '.cache/npm'
if (!(Test-Path .tooling/agentflow)) {
  git clone --branch v1.0.0 --depth 1 https://github.com/smota/agentflow-sdlc.git .tooling/agentflow
  if ($LASTEXITCODE) { throw 'Framework clone failed' }
}
$frameworkSha = git -c safe.directory="$demoRoot/.tooling/agentflow" -C .tooling/agentflow rev-parse HEAD
if ($frameworkSha -ne 'd61b3ca71189f872a6fd78373076f2aab787f2e0') { throw 'Unexpected framework revision' }
node .tooling/agentflow/bin/cli.mjs doctor --target .
if ($LASTEXITCODE) { throw 'Framework doctor failed' }
```

Normal Node environments run `npm run check:workflow`. This workstation intercepts `npm`, so use its installed runtime directly (no package installation):

```powershell
$demoNode = mise which node
& $demoNode (Join-Path (Split-Path $demoNode) 'node_modules/npm/bin/npm-cli.js') run check:workflow
```

Runtime discovery is workstation-specific; package.json and CI use the portable npm script. Caches remain ignored. No `init` is needed on a fresh clone: managed files and lock are already committed.

## Checkpoint policy

Record current issue/role, branch/commit, last accepted action, input/output digests, relevant test evidence, open rework, remote object IDs and next safe action after every role and before/after external mutations. Commit coherent issue-scoped increments. The checkpoint is a recovery aid, not authority or evidence that tests passed.

## Retry policy

Use bounded network timeouts and at most three retries with backoff for transient failures. Honor rate-limit reset times. Never blindly retry a write whose outcome is unknown: inspect its remote identifier first. Repeated identical failures trigger diagnosis/replanning, not infinite retries. Continue independent authorized work when possible. Never weaken a gate to show progress.

## Release policy

Feature work targets development; release promotion targets main. Main/development are not implementation workspaces. Check PR body, CI, merge commit, issue closure, tag, GitHub release and running Streamlit version separately. Keep last-good code/data available. Do not claim production acceptance from local green tests alone.

## Recovery exercise

At a completed phase, freeze a checkpoint and evidence digest. A read-only fresh-context helper reconstructs the next action using these documents and GitHub without receiving the prior conversation. Compare its reconstruction with the recorded contract. A separate deterministic test rejects changed candidate digests and resumes an interrupted crawler without duplicate records. Identify replay/simulation versus actual interruption explicitly in the story.
