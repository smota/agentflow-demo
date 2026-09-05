#!/usr/bin/env node
// Derives data/sessions/pr-<n>.json (schemas/session-record.schema.json) from a PR's own
// manifest body -- the `## Implemented issues`, `## Related issues`, `## Agent review`,
// `## Role attribution matrix`, `## CI-equivalent validation`, and `## Follow-up issues`
// sections AGENTS.md already requires every PR to carry. Reuses lib/markdown-sections.mjs and
// lib/role-attribution.mjs rather than re-deriving parsing logic (see scripts/validate-pr-manifest.mjs
// for the same reuse pattern).
//
// Usage:
//   node scripts/derive-session-record.mjs <pr-number> [--body-file <path>] [--title <t>]
//     [--merged-at <iso>] [--merge-commit <sha>] [--target-branch development]
//     [--pr-url <url>] [--out <path>] [--dry-run]
//   node scripts/derive-session-record.mjs --rollup --id build-4 --title <t> --summary <s>
//     --children pr-63,pr-66,... [--wave "Build 4"] [--merged-at <iso>] [--out <path>] [--dry-run]
//     [--platform claude] [--executor claude-cli] [--transport local-cli]
//     [--delegation-boundary current-session] [--workflow-profile standard] [--mode multi-agent]
//     [--merge-owner "human/operator"] [--issues 47,48,49]
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { spawnSync } from 'node:child_process'
import { extractSection, fieldValue, parseMarkdownTable } from '../lib/markdown-sections.mjs'
import { rowsFromTable } from '../lib/role-attribution.mjs'

function getArg(name, fallback = '') {
  const index = process.argv.indexOf(name)
  if (index === -1) return fallback
  return process.argv[index + 1] ?? fallback
}

function hasFlag(name) {
  return process.argv.includes(name)
}

function listArg(name) {
  const value = getArg(name)
  return value ? value.split(',').map((x) => x.trim()).filter(Boolean) : []
}

function fail(message) {
  process.stderr.write(`[derive-session-record] ${message}\n`)
  process.exit(1)
}

function ghPrView(prNumber) {
  const result = spawnSync(
    'gh',
    ['pr', 'view', String(prNumber), '--json', 'number,title,url,body,mergeCommit,mergedAt,baseRefName'],
    { encoding: 'utf8' },
  )
  if (result.status !== 0) {
    return null
  }
  try {
    const parsed = JSON.parse(result.stdout)
    // `gh pr view --json mergeCommit` returns `{ oid: "<sha>" }`, not a bare string -- flatten it
    // here so every other consumer of `meta.mergeCommit` can keep treating it as a plain SHA string
    // (schemas/session-record.schema.json's repository.mergeCommit is a string).
    if (parsed && parsed.mergeCommit && typeof parsed.mergeCommit === 'object') {
      parsed.mergeCommit = parsed.mergeCommit.oid ?? null
    }
    return parsed
  } catch {
    return null
  }
}

function parseIssueLines(section, relation, pattern) {
  if (!section) return []
  const results = []
  for (const match of section.matchAll(pattern)) {
    results.push({ number: Number(match[1]), relation })
  }
  return results
}

function deriveRepositoryIssues(body, repoSlug) {
  const implemented = extractSection(body, 'Implemented issues')
  const related = extractSection(body, 'Related issues')
  // Priority order implements > closes > refs: a real PR body can legitimately list the same
  // issue under both "Implemented issues" (Closes #N, e.g. a trunk-targeting PR) and "Related
  // issues" (Refs #N) for cross-reference clarity -- collapse to the strongest relation instead of
  // recording the same issue number twice with two different relations (seen against real PR #87's
  // own body, which lists #50 both ways).
  const issues = [
    ...parseIssueLines(implemented, 'implements', /^-\s+Implements #(\d+)/gm),
    ...parseIssueLines(implemented, 'closes', /^-\s+Closes #(\d+)/gm),
    ...parseIssueLines(related, 'refs', /^-\s+Refs #(\d+)/gm),
  ]
  const byNumber = new Map()
  for (const issue of issues) {
    if (!byNumber.has(issue.number)) byNumber.set(issue.number, issue)
  }
  return [...byNumber.values()].map((issue) => ({
    ...issue,
    url: `https://github.com/${repoSlug}/issues/${issue.number}`,
  }))
}

function deriveFollowUps(body) {
  const section = extractSection(body, 'Follow-up issues')
  if (!section || /^\s*none\s*$/im.test(section)) return []
  return [...section.matchAll(/#(\d+)/g)].map((match) => Number(match[1]))
}

function deriveValidators(body) {
  const ci = extractSection(body, 'CI-equivalent validation')
  if (!ci) return []
  const status = fieldValue(ci, 'Status') ?? 'not-run-with-reason'
  const result = status === 'passed' ? 'passed' : status === 'not-run-with-reason' ? 'not-run-with-reason' : 'failed'
  // "Commands:" is a single field value (see agents/templates/pr-manifest.md); real PR bodies
  // list multiple commands comma- or newline-separated, each optionally backtick-quoted.
  const commandsLine = fieldValue(ci, 'Commands')
  const extraLines = ci
    .split('\n')
    .filter((line) => /^\s*-\s+`[^`]+`/.test(line) && !/^\s*-\s+Commands:/.test(line))
    .map((line) => line.replace(/^\s*-\s+/, ''))
  const rawNames = [
    ...(commandsLine ? commandsLine.split(/,|\n/) : []),
    ...extraLines,
  ]
  const names = [...new Set(rawNames
    .map((x) => x.trim().replace(/^`|`$/g, ''))
    .filter(Boolean))]
  return names.map((name) => ({ name, result }))
}

function deriveTestsPassed(body) {
  const workflowEvidence = extractSection(body, 'Workflow evidence')
  const ci = extractSection(body, 'CI-equivalent validation')
  for (const section of [ci, workflowEvidence]) {
    if (!section) continue
    const match = section.match(/(\d+)\s+(?:passing\s+)?tests?\s+pass(?:ed|ing)?/i) || section.match(/pytest[^\n]*?(\d+)\s+passed/i)
    if (match) return Number(match[1])
  }
  return undefined
}

function derivePhasesRun(body) {
  const attributionSection = extractSection(body, 'Role attribution matrix')
  const rows = rowsFromTable(parseMarkdownTable(attributionSection))
  if (rows.length > 0) {
    return [...new Set(rows.map((row) => row.role).filter(Boolean))]
  }
  // Single-agent PRs don't carry a role attribution matrix (it is only required for multi-agent
  // claims -- see docs/agent-workflow.md §4a). A single executor running every phase is the
  // documented default shape, so record the full canonical phase sequence rather than guessing
  // a partial list from prose.
  return [
    'product-manager',
    'analyst',
    'architect',
    'implementation-planner',
    'developer',
    'tester',
    'reviewer',
    'technical-writer',
    'pr-readiness',
  ]
}

function deriveSdlcReview(agentReview) {
  const review = fieldValue(agentReview, 'Review')
  if (review === 'self-review') return 'self-review'
  if (review === 'human-review-requested' || review === 'human-reviewed') return 'human'
  return 'independent'
}

function deriveEvidence(body, prUrl, repoSlug) {
  const evidence = []
  if (prUrl) {
    evidence.push({
      kind: 'pull-request',
      system: 'github',
      uri: prUrl,
      authority: 'authoritative',
      relationship: 'delivers',
    })
  }
  const evidenceField = extractSection(body, 'Workflow evidence')
  const contracts = fieldValue(evidenceField, 'Evidence contracts')
  if (contracts && contracts !== 'none') {
    for (const url of contracts.matchAll(/https?:\/\/\S+/g)) {
      evidence.push({
        kind: 'evidence-contract',
        system: repoSlug ? 'github' : 'local',
        uri: url[0].replace(/[),.]+$/, ''),
        authority: 'authoritative',
        relationship: 'documents',
      })
    }
  }
  return evidence
}

function buildPrRecord({ prNumber, body, meta, opts }) {
  const repoSlug = opts.repoSlug || 'smota/agentflow-demo'
  const prUrl = opts.prUrl || meta?.url || `https://github.com/${repoSlug}/pull/${prNumber}`
  const mergedAt = opts.mergedAt || meta?.mergedAt
  if (!mergedAt) {
    fail(`no mergedAt available for PR #${prNumber}; pass --merged-at or ensure \`gh pr view\` returns it`)
  }
  const agentReview = extractSection(body, 'Agent review')
  const workflowEvidence = extractSection(body, 'Workflow evidence')
  const title = opts.title || meta?.title || `PR #${prNumber}`
  const roleSummary = fieldValue(workflowEvidence, 'Role-pass summary')
  const summary = opts.summary || roleSummary || title

  const record = {
    schemaVersion: 1,
    id: `pr-${prNumber}`,
    kind: 'pr',
    title,
    summary,
    mergedAt,
    harness: {
      platform: fieldValue(agentReview, 'Implemented by') || 'human',
      executor: fieldValue(agentReview, 'Executor') || 'human',
      transport: fieldValue(agentReview, 'Transport') || 'manual',
      delegationBoundary: fieldValue(agentReview, 'Delegation boundary') || 'human-handoff',
    },
    sdlc: {
      mode: fieldValue(agentReview, 'Mode') || 'single-agent',
      workflowProfile: fieldValue(agentReview, 'Workflow profile') || 'standard',
      phasesRun: derivePhasesRun(body),
      review: deriveSdlcReview(agentReview),
      humanReviewRequired: fieldValue(agentReview, 'Workflow profile') === 'high-assurance',
      mergeOwner: fieldValue(agentReview, 'Merge owner') || 'human/operator',
    },
    repository: {
      prNumber,
      prUrl,
      mergeCommit: opts.mergeCommit || meta?.mergeCommit || undefined,
      targetBranch: opts.targetBranch || meta?.baseRefName || 'development',
      issues: deriveRepositoryIssues(body, repoSlug),
    },
    verification: {
      validators: deriveValidators(body),
    },
    decisions: [],
    findings: [],
    followUps: deriveFollowUps(body),
    evidence: deriveEvidence(body, prUrl, repoSlug),
  }

  const model = fieldValue(agentReview, 'Model / runtime')
  if (model && !model.startsWith('<')) record.harness.model = model

  const selfReviewDisclosure = fieldValue(agentReview, 'Self-review disclosure')
  if (selfReviewDisclosure && selfReviewDisclosure !== 'not-applicable') {
    record.sdlc.selfReviewDisclosure = selfReviewDisclosure
  }

  const testsPassed = deriveTestsPassed(body)
  if (testsPassed !== undefined) record.verification.testsPassed = testsPassed

  if (!record.repository.mergeCommit) delete record.repository.mergeCommit

  return record
}

function buildRollupRecord(opts) {
  const id = opts.id
  if (!id) fail('--id is required for --rollup')
  const children = listArg('--children')
  if (children.length === 0) fail('--children is required (comma-separated session-record ids) for --rollup')
  const mergedAt = opts.mergedAt
  if (!mergedAt) fail('--merged-at is required for --rollup')

  return {
    schemaVersion: 1,
    id,
    kind: 'rollup',
    title: opts.title || id,
    summary: opts.summary || opts.title || id,
    mergedAt,
    wave: opts.wave || undefined,
    harness: {
      platform: opts.platform || 'claude',
      executor: opts.executor || 'claude-cli',
      transport: opts.transport || 'local-cli',
      delegationBoundary: opts.delegationBoundary || 'current-session',
    },
    sdlc: {
      mode: opts.mode || 'multi-agent',
      workflowProfile: opts.workflowProfile || 'standard',
      phasesRun: [
        'product-manager',
        'analyst',
        'architect',
        'implementation-planner',
        'developer',
        'tester',
        'reviewer',
        'technical-writer',
        'pr-readiness',
      ],
      review: opts.review || 'independent',
      humanReviewRequired: (opts.workflowProfile || 'standard') === 'high-assurance',
      mergeOwner: opts.mergeOwner || 'human/operator',
    },
    repository: {
      issues: listArg('--issues').map((n) => ({
        number: Number(n),
        url: `https://github.com/${opts.repoSlug || 'smota/agentflow-demo'}/issues/${n}`,
        relation: 'refs',
      })),
    },
    verification: {},
    decisions: [],
    findings: [],
    followUps: [],
    children,
    evidence: [],
  }
}

function main() {
  const opts = {
    title: getArg('--title') || undefined,
    summary: getArg('--summary') || undefined,
    mergedAt: getArg('--merged-at') || undefined,
    mergeCommit: getArg('--merge-commit') || undefined,
    targetBranch: getArg('--target-branch') || undefined,
    prUrl: getArg('--pr-url') || undefined,
    repoSlug: getArg('--repo') || undefined,
    id: getArg('--id') || undefined,
    wave: getArg('--wave') || undefined,
    platform: getArg('--platform') || undefined,
    executor: getArg('--executor') || undefined,
    transport: getArg('--transport') || undefined,
    delegationBoundary: getArg('--delegation-boundary') || undefined,
    workflowProfile: getArg('--workflow-profile') || undefined,
    mode: getArg('--mode') || undefined,
    review: getArg('--review') || undefined,
    mergeOwner: getArg('--merge-owner') || undefined,
  }

  let record
  if (hasFlag('--rollup')) {
    record = buildRollupRecord(opts)
  } else {
    const prNumber = Number(process.argv[2])
    if (!Number.isInteger(prNumber) || prNumber <= 0) {
      fail('usage: derive-session-record.mjs <pr-number> [...] | --rollup --id <id> --children <ids>')
    }
    const bodyFile = getArg('--body-file')
    let body
    let meta = null
    if (bodyFile) {
      if (!existsSync(bodyFile)) fail(`--body-file does not exist: ${bodyFile}`)
      body = readFileSync(bodyFile, 'utf8')
    } else {
      meta = ghPrView(prNumber)
      if (!meta) {
        fail(
          `could not fetch PR #${prNumber} via \`gh pr view\` (no local auth/network, or PR does not exist). Pass --body-file <path> with a locally saved PR body instead.`,
        )
      }
      body = meta.body
    }
    record = buildPrRecord({ prNumber, body, meta, opts })
  }

  const out = getArg('--out') || `data/sessions/${record.id}.json`
  const json = `${JSON.stringify(record, null, 2)}\n`

  if (hasFlag('--dry-run')) {
    process.stdout.write(json)
    return
  }

  mkdirSync(dirname(out), { recursive: true })
  writeFileSync(out, json, 'utf8')
  process.stdout.write(`[derive-session-record] wrote ${out}\n`)
}

main()
