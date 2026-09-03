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
- .tooling/agentflow-next holds the current pinned source from agentflow-source.json. The older .tooling/agentflow is historical only. .venv, .cache and data/raw are local-only.
- Set TEMP/TMP and package caches to project-local directories for tool commands that write them. Do not use global install or change global Git identity/trust.

## Installation

Use the exact revision in agentflow-source.json:60a0e800dc4d4ce9476c72231a0b853998131213. This is merged development, not a newer published release. The old v1 installation was explicitly retired and replaced by official fresh github-profile adoption; see wave2.md. Do not run retired init/sync commands.

Current adoption supports --storage project, with ignored receipts under .agentflow/transactions. Review adopt plan before applying the exact token. Never invent or modify lock hashes. JSON payload bytes are preserved with Git -text attributes because managed hashes are byte-based.

From the demo root in PowerShell, restore the ignored source only if absent:

```powershell
$demoRoot = (Get-Location).Path
New-Item -ItemType Directory -Force .cache/tmp, .cache/npm, .cache/pip, .tooling | Out-Null
$env:TEMP = Join-Path $demoRoot '.cache/tmp'
$env:TMP = $env:TEMP
$env:npm_config_cache = Join-Path $demoRoot '.cache/npm'
$env:PIP_CACHE_DIR = Join-Path $demoRoot '.cache/pip'
$env:PYTHONDONTWRITEBYTECODE = '1'
if (!(Test-Path .tooling/agentflow-next)) {
  git clone --config core.autocrlf=false --no-checkout https://github.com/smota/agentflow-sdlc.git .tooling/agentflow-next
  if ($LASTEXITCODE) { throw 'Framework clone failed' }
  git -C .tooling/agentflow-next checkout --detach 60a0e800dc4d4ce9476c72231a0b853998131213
  if ($LASTEXITCODE) { throw 'Framework checkout failed' }
  # Fresh tooling clone only: retain the raw pinned bytes, without text filters.
  node -e "const fs=require('fs'), cp=require('child_process'), path=require('path'); const base=path.resolve('.tooling/agentflow-next'); const git=(...a)=>cp.execFileSync('git',['-c','safe.directory='+base,'-C',base,...a]); for(const e of git('ls-tree','-rz','HEAD').toString().split('\0').filter(Boolean)){const [m,p]=e.split('\t'); const [mode,type,oid]=m.split(' '); const f=path.resolve(base,p); if(type!=='blob'||!['100644','100755'].includes(mode)||!f.startsWith(base+path.sep))throw Error('Unexpected source entry'); fs.writeFileSync(f,git('cat-file','blob',oid));}"
  if ($LASTEXITCODE) { throw 'Framework byte materialization failed' }
}
$frameworkSha = git -c safe.directory="$demoRoot/.tooling/agentflow-next" -C .tooling/agentflow-next rev-parse HEAD
if ($frameworkSha -ne '60a0e800dc4d4ce9476c72231a0b853998131213') { throw 'Unexpected framework revision' }
node scripts/check-framework.mjs
if ($LASTEXITCODE) { throw 'Framework validation failed' }
```

Normal Node environments run `npm run check:workflow`. This workstation intercepts `npm`, so use its installed runtime directly (no package installation):

```powershell
$demoNode = mise which node
& $demoNode (Join-Path (Split-Path $demoNode) 'node_modules/npm/bin/npm-cli.js') run check:workflow
```

Runtime discovery is workstation-specific; package.json and CI use the portable npm script. Caches remain ignored. No adoption is needed on a fresh clone: managed files and lock are already committed. For a future update, preserve authored changes and use official adopt plan/apply with project storage.

The raw-byte step is necessary for this pin: an isolated Windows checkout changed
91 files through line-ending filters despite `core.autocrlf=false`. A Git archive
fixture also failed the exact-byte check. `git cat-file blob` is the tested source
of authoritative bytes. Do not apply this overwrite step to an existing or authored
checkout: inspect differences, preserve originals, and restore only proven cache
materialization differences. A clean text-filtered Git status does not prove byte
identity. The framework checker verifies every blob against the pinned tree.

The pinned contained rollback CLI has a known receipt-field defect (issue18). The tested project adapter invokes the unmodified official API with the original signed receipt:
`node scripts/adoption-rollback.mjs --target <absolute-demo-or-contained-fixture> --receipt <absolute-receipt> --confirm <receipt-token>`.
It checks reserved contained paths and delegates digest/target/drift checks upstream. Retained receipts are not permission to overwrite later work. The exercised rollback was an isolated adoption fixture, not a production application rollback.

For Python 3.11, after the project-local cache variables above are set:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m streamlit run app.py --server.address=127.0.0.1
```

Use requirements.txt instead for the hosted/runtime-only dependency set. Do not
install globally. This workstation used its existing Python 3.11 runtime and
project-local uv cache to create/sync the same locked environment.

After changing imported Python modules, restart the local Streamlit process before
final browser acceptance. Hot reload and an updated version footer alone do not
prove every imported helper is fresh; verify the changed behavior explicitly.

## Checkpoint policy

Record current issue/role, branch/commit, last accepted action, input/output digests, relevant test evidence, open rework, remote object IDs and next safe action after every role and before/after external mutations. Commit coherent issue-scoped increments. The checkpoint is a recovery aid, not authority or evidence that tests passed.

For list-profile enrichment, keep `--batch-size` within 1–16 and `--workers`
within 1–4; the tested long-run setting is 8 and 4. Each completed batch is
applied deterministically to a small digest-bound `profile-checkpoint.json`
sidecar. A successful merge saves the main checkpoint and removes the sidecar.
Do not edit or transplant a sidecar across engine/run identities. Before removing
an orphaned writer lock, resolve its exact path and prove its recorded PID is gone.

## Retry policy

Use bounded network timeouts and at most three retries with backoff for transient failures. Honor rate-limit reset times. Never blindly retry a write whose outcome is unknown: inspect its remote identifier first. Repeated identical failures trigger diagnosis/replanning, not infinite retries. Continue independent authorized work when possible. Never weaken a gate to show progress.

## Release policy

Feature work targets development; release promotion targets main. Main/development are not implementation workspaces. Check PR body, CI, merge commit, issue closure, tag, GitHub release and running Streamlit version separately. Keep last-good code/data available. Do not claim production acceptance from local green tests alone.

### Guarded rollback procedure (documented, not executed)

Open an incident issue and record the bad promotion commit and desired known-good
tag. Preserve any dirty work before branching. Inspect first:

```powershell
git status --short
git fetch origin --tags
git show --no-patch --format=fuller <known-good-tag>
git rev-list -n 1 <known-good-tag>
gh release view <known-good-tag> --json tagName,targetCommitish,isDraft,isPrerelease
git diff --stat <known-good-tag> origin/main
```

Verify the release/tag target and desired package/dependency/catalogue contents.
Do not reset or force-push protected branches. With a clean worktree, create an
incident-scoped work branch from origin/main and revert the exact bad promotion
merge after inspecting its parents:

```powershell
git switch -c work/rollback-<incident> origin/main
git show --no-patch --format=%P <bad-promotion-merge>
git revert -m 1 <bad-promotion-merge>
```

The `-m 1` example is only for a verified main promotion merge whose first parent
is the prior main. For another history shape, plan the exact revert; do not copy
this command blindly. Inspect the resulting app, locks and data against the
known-good tree, assign a new patch version, run all checks and open a full
incident PR into development. Promote through a reviewed main PR with required
checks, publish a new release, then verify hosted search/version/digest independently.
Never move existing tags, publish a partial catalogue or infer recovery from CI
alone. Record both the incident and hosted recovery receipts.

## Recovery exercise

At a completed phase, freeze a checkpoint and evidence digest. A read-only fresh-context helper reconstructs the next action using these documents and GitHub without receiving the prior conversation. Compare its reconstruction with the recorded contract. A separate deterministic test rejects changed candidate digests and resumes an interrupted crawler without duplicate records. Identify replay/simulation versus actual interruption explicitly in the story.

### GitHub-backed Agentflow run

The final 2.0 exercise uses run ID `awesomeawesomeness-2-final`, goal `issue:24`,
repository `smota/agentflow-demo` and coordination branch `agentflow-state`. First run
the source preflight and inspect its current default-branch SHA, rules, permissions and
workflow branch filters. Never reuse the historical setup digest from the story:

```powershell
node .tooling/agentflow-next/bin/cli.mjs run source-plan awesomeawesomeness-2-final --target . --json
node .tooling/agentflow-next/bin/cli.mjs run status awesomeawesomeness-2-final --target . --json
node .tooling/agentflow-next/bin/cli.mjs run context awesomeawesomeness-2-final --target . --json
```

Start a new run only after reviewing and authorizing the exact source-plan digest.
Record the actual parent writer PID. Every mutation supplies the current owner and
generation plus `--execute --boundary external-action`. Checkpoint and pause record
Agentflow state; they do not claim to stop an arbitrary crawler or model provider.

For replacement, first preview `run resume` with a real live replacement PID. Save the
returned plan unchanged, review `priorWriter`, workspace identity, operations and digest,
then apply that exact plan with `--confirm` and the old generation. An uncertain response
must be resolved with `run status`/`run context` and a state-branch read-back before any
retry. Continue with the returned generation. Never delete a lock merely because it is old.

Publication follows the same intent-first rule: preview `run publish --issue 24`, save
the exact plan, then apply it with its digest. Reapplying the same plan must reconcile the
existing marker-backed comment. A newly previewed plan after the run revision changes is
not the same operation and must not be used as a duplicate-write test.

To reconstruct without transcript or scratch, fetch the coordination ref read-only and
give an ephemeral successor only repository policy plus Git refs:

```powershell
git fetch origin agentflow-state:refs/remotes/origin/agentflow-state
git show origin/agentflow-state:runs/awesomeawesomeness-2-final.json
npm run check:recovery
```

Refresh the ref before making a later decision. The committed recovery evidence is a
sanitized point-in-time test record; current GitHub state remains authoritative.

### Local crawler commands

Use the project environment. `build` only stages a candidate; it never publishes.
Choose a new lowercase run ID for a new discovery observation. Reusing a run ID
resumes its pinned inputs, not current GitHub state.

```powershell
.venv/Scripts/python.exe -m tools.crawl build --run-id refresh-20260902
.venv/Scripts/python.exe -m tools.crawl validate
# Review staged source licenses/content and copy its full digest before publishing:
.venv/Scripts/python.exe -m tools.crawl publish --expected-digest <reviewed-digest>
```

The recovery exercise requires the local raw caches from the original crawl;
they are intentionally not committed. A fresh clone can run all fixture tests,
or perform a new local build with its own GitHub CLI authorization. Do not claim
that cached replay works without those inputs.

```powershell
# Expected injected exit after one durable source checkpoint:
.venv/Scripts/python.exe -m tools.crawl build --run-id recovery-example --replay-published --interrupt-after 1
# Resume and then repeat to verify idempotence:
.venv/Scripts/python.exe -m tools.crawl build --run-id recovery-example --replay-published
.venv/Scripts/python.exe -m tools.crawl build --run-id recovery-example --replay-published
```

Expected output for this snapshot: 3,037 resources and digest
`6765f04bb900eaf6d868e070613d7800faf2d0bec5d5d0577a65d23dc894d5f3`.
Published file SHA-256 is
`25804156edbe403dfb684556e84445c345d1b8530cb119dc613b021fc748c90b` in
the original Windows checkout; checkout line-ending conversion can change the
file-byte hash without changing the canonical catalogue digest.

If engine/checkpoint/raw-input identity changes, do not edit hashes to force
acceptance: investigate, preserve evidence and use a new run ID after review.
If `.agent-runs/crawler.lock` exists, inspect its recorded PID with `Get-Process`
and confirm no crawler is active. Never delete an active/unknown lock. For a
confirmed dead owner, move the exact lock file to a uniquely named incident file
within `.agent-runs/`, then retry. No automatic stale-age unlock is implemented.
