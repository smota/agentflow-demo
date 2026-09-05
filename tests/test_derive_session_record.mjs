import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

const ROOT = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')

const SAMPLE_BODY = `## Implemented issues

- Implements #47
- Implements #65

## Related issues

- Refs #67

## Workflow evidence

- Workflow-status comment: https://github.com/smota/agentflow-demo/issues/47#issuecomment-1
- Handover comments: exception:no role transition occurred
- Role-pass summary: Implemented cross-list project search with copy-lineage disclosure.
- Capability evidence: not-applicable:none
- Collaboration evidence: single-agent:no delegation needed
- Validation evidence: pytest -q reported 178 passed
- Evidence contracts: none
- Action boundary: not-applicable

## CI-equivalent validation

- Status: passed
- Commands: \`pytest -q\`, \`node scripts/validate-pr-manifest.mjs\`
- Notes: none

## Follow-up issues

- #67

## Agent review

- Implemented by: claude
- Launcher: claude
- Executor: claude-cli
- Transport: local-cli
- Delegation boundary: current-session
- Model / runtime: claude-sonnet-4-20250514
- Review: self-review
- Workflow profile: standard
- Merge owner: human/operator
- Fallback chain: none
- Regression test: not-applicable:new feature
- Mode: single-agent
- Self-review disclosure: not-applicable
`

function runNode(args) {
  return spawnSync('node', args, { cwd: ROOT, encoding: 'utf8' })
}

function writeSample(dir) {
  const bodyPath = join(dir, 'body.md')
  writeFileSync(bodyPath, SAMPLE_BODY, 'utf8')
  return bodyPath
}

test('derive-session-record produces a schema-conformant record from a real manifest shape', () => {
  const dir = mkdtempSync(join(tmpdir(), 'session-record-'))
  const bodyPath = writeSample(dir)

  const result = runNode([
    'scripts/derive-session-record.mjs', '69',
    '--body-file', bodyPath,
    '--merged-at', '2026-08-01T00:00:00Z',
    '--dry-run',
  ])
  assert.equal(result.status, 0, result.stderr)
  const record = JSON.parse(result.stdout)

  assert.equal(record.id, 'pr-69')
  assert.equal(record.kind, 'pr')
  assert.equal(record.schemaVersion, 1)
  assert.equal(record.harness.platform, 'claude')
  assert.equal(record.harness.executor, 'claude-cli')
  assert.equal(record.sdlc.mode, 'single-agent')
  assert.equal(record.sdlc.review, 'self-review')
  assert.equal(record.repository.prNumber, 69)
  assert.deepEqual(
    record.repository.issues.map((i) => [i.number, i.relation]).sort(),
    [[47, 'implements'], [65, 'implements'], [67, 'refs']],
  )
  assert.deepEqual(record.followUps, [67])
  assert.deepEqual(
    record.verification.validators.map((v) => v.name),
    ['pytest -q', 'node scripts/validate-pr-manifest.mjs'],
  )
  assert.equal(record.verification.testsPassed, 178)
})

test('derived record passes validate-session-record.mjs, including the pr-body cross-check', () => {
  const dir = mkdtempSync(join(tmpdir(), 'session-record-'))
  const bodyPath = writeSample(dir)
  const outPath = join(dir, 'pr-69.json')

  const derive = runNode([
    'scripts/derive-session-record.mjs', '69',
    '--body-file', bodyPath,
    '--merged-at', '2026-08-01T00:00:00Z',
    '--out', outPath,
  ])
  assert.equal(derive.status, 0, derive.stderr)
  assert.ok(existsSync(outPath))

  const validate = runNode([
    'scripts/validate-session-record.mjs',
    '--path', outPath,
    '--pr-number', '69',
    '--pr-body', bodyPath,
  ])
  assert.equal(validate.status, 0, validate.stdout + validate.stderr)
  assert.match(validate.stdout, /PASS {2}schema-conformance/)
  assert.match(validate.stdout, /PASS {2}harness-vocabulary/)
  assert.match(validate.stdout, /PASS {2}pr-body-cross-check/)
})

test('validate-session-record.mjs fails when a record claims an issue its own PR body does not declare', () => {
  const dir = mkdtempSync(join(tmpdir(), 'session-record-'))
  const bodyPath = writeSample(dir)
  const outPath = join(dir, 'pr-69.json')

  runNode(['scripts/derive-session-record.mjs', '69', '--body-file', bodyPath, '--merged-at', '2026-08-01T00:00:00Z', '--out', outPath])
  const record = JSON.parse(readFileSync(outPath, 'utf8'))
  record.repository.issues.push({ number: 999, url: 'https://github.com/smota/agentflow-demo/issues/999', relation: 'refs' })
  writeFileSync(outPath, JSON.stringify(record), 'utf8')

  const validate = runNode(['scripts/validate-session-record.mjs', '--path', outPath, '--pr-number', '69', '--pr-body', bodyPath])
  assert.equal(validate.status, 1)
  assert.match(validate.stdout, /FAIL {2}pr-body-cross-check/)
  assert.match(validate.stdout, /claims #999/)
})

test('validate-session-record.mjs fails schema conformance on a malformed record', () => {
  const dir = mkdtempSync(join(tmpdir(), 'session-record-'))
  const outPath = join(dir, 'broken.json')
  writeFileSync(outPath, JSON.stringify({ schemaVersion: 1, kind: 'pr' }), 'utf8')

  const validate = runNode(['scripts/validate-session-record.mjs', '--path', outPath])
  assert.equal(validate.status, 1)
  assert.match(validate.stdout, /FAIL {2}schema-conformance/)
})

test('derive-session-record --rollup builds a record pointing at its children', () => {
  const result = runNode([
    'scripts/derive-session-record.mjs', '--rollup',
    '--id', 'build-test', '--title', 'Build Test', '--summary', 'A test wave',
    '--children', 'pr-1,pr-2', '--merged-at', '2026-08-02T00:00:00Z',
    '--wave', 'Build Test', '--dry-run',
  ])
  assert.equal(result.status, 0, result.stderr)
  const record = JSON.parse(result.stdout)
  assert.equal(record.kind, 'rollup')
  assert.deepEqual(record.children, ['pr-1', 'pr-2'])
})

test('every migrated data/sessions/*.json record validates', () => {
  const result = runNode(['scripts/validate-session-record.mjs', '--glob', 'data/sessions/*.json'])
  assert.equal(result.status, 0, result.stdout + result.stderr)
})
