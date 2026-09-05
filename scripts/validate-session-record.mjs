#!/usr/bin/env node
// Validates data/sessions/*.json session records (schemas/session-record.schema.json) the same
// way scripts/validate-pr-manifest.mjs validates a PR manifest: a flat PASS/FAIL check list, hand
// -rolled rather than run through a JSON Schema engine, matching every other schemas/*.schema.json
// consumer in this repo (see lib/evidence-contracts.mjs).
//
// Three things are checked, per docs/agent-workflow.md's session-record architecture:
//   (a) schema conformance against schemas/session-record.schema.json's shape
//   (b) harness.platform is a registered slug (manifests/runtime-platforms.json), and
//       harness.executor/transport/delegationBoundary are known docs/execution-targets.md values
//   (c) when --pr-number/--pr-body are given, a record whose repository.prNumber matches the given
//       PR number cannot claim repository.issues its own PR body does not declare -- a session
//       record can't invent evidence its PR never carried.
import { existsSync, readFileSync, globSync } from 'node:fs'
import {
  extractSection,
  fieldValue,
} from '../lib/markdown-sections.mjs'
import { ALL_EXECUTION_TARGETS, TRANSPORTS, DELEGATION_BOUNDARIES } from '../lib/execution-targets.mjs'
import { loadProjectConfig } from '../lib/role-routing.mjs'
import { runtimePlatformSlugs } from '../lib/runtime-platforms.mjs'

function getArg(name) {
  const index = process.argv.indexOf(name)
  if (index === -1) return ''
  return process.argv[index + 1] ?? ''
}

const explicitPath = getArg('--path')
const globPattern = getArg('--glob')
const prNumberArg = getArg('--pr-number')
const prBodyPath = getArg('--pr-body')

let targets
if (explicitPath) {
  targets = [explicitPath]
} else if (globPattern) {
  targets = globSync(globPattern)
} else {
  targets = existsSync('data/sessions') ? globSync('data/sessions/*.json') : []
}

if (targets.length === 0) {
  process.stdout.write('[validate-session-record] no session records to validate (nothing matched)\n')
  process.exit(0)
}

const projectConfig = loadProjectConfig()
let registeredPlatforms = []
let platformRegistryError = null
try {
  registeredPlatforms = runtimePlatformSlugs(projectConfig)
} catch (error) {
  platformRegistryError = error.message
}

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function isInteger(value) {
  return typeof value === 'number' && Number.isInteger(value)
}

/** Hand-rolled shape check mirroring schemas/session-record.schema.json's required fields. */
function validateShape(record) {
  const errors = []
  const req = (cond, message) => {
    if (!cond) errors.push(message)
  }

  req(record.schemaVersion === 1, 'schemaVersion must be 1')
  req(isNonEmptyString(record.id), 'id is required')
  req(['pr', 'rollup', 'release'].includes(record.kind), 'kind must be pr, rollup, or release')
  req(isNonEmptyString(record.title), 'title is required')
  req(isNonEmptyString(record.summary), 'summary is required')
  req(isNonEmptyString(record.mergedAt) && !Number.isNaN(Date.parse(record.mergedAt)), 'mergedAt must be a valid date-time')

  const harness = record.harness ?? {}
  req(isNonEmptyString(harness.platform), 'harness.platform is required')
  req(isNonEmptyString(harness.executor), 'harness.executor is required')
  req(isNonEmptyString(harness.transport), 'harness.transport is required')
  req(isNonEmptyString(harness.delegationBoundary), 'harness.delegationBoundary is required')

  const sdlc = record.sdlc ?? {}
  req(['single-agent', 'multi-agent'].includes(sdlc.mode), 'sdlc.mode must be single-agent or multi-agent')
  req(
    ['bounded', 'standard', 'high-assurance', 'exploratory'].includes(sdlc.workflowProfile),
    'sdlc.workflowProfile must be bounded, standard, high-assurance, or exploratory',
  )
  req(Array.isArray(sdlc.phasesRun), 'sdlc.phasesRun must be an array')
  req(['self-review', 'independent', 'human'].includes(sdlc.review), 'sdlc.review must be self-review, independent, or human')
  req(typeof sdlc.humanReviewRequired === 'boolean', 'sdlc.humanReviewRequired must be a boolean')
  req(isNonEmptyString(sdlc.mergeOwner), 'sdlc.mergeOwner is required')

  const repository = record.repository ?? {}
  req(Array.isArray(repository.issues), 'repository.issues must be an array')
  if (record.kind === 'pr') {
    req(isInteger(repository.prNumber), 'repository.prNumber must be an integer (required for kind: pr)')
    req(isNonEmptyString(repository.prUrl), 'repository.prUrl is required (required for kind: pr)')
    req(isNonEmptyString(repository.targetBranch), 'repository.targetBranch is required (required for kind: pr)')
  }
  if (['rollup', 'release'].includes(record.kind)) {
    req(Array.isArray(record.children) && record.children.length > 0, 'children must be a non-empty array (required for kind: rollup/release)')
  }
  for (const issue of repository.issues ?? []) {
    if (!isInteger(issue.number) || !isNonEmptyString(issue.url) || !['implements', 'closes', 'refs'].includes(issue.relation)) {
      errors.push(`repository.issues has a malformed entry: ${JSON.stringify(issue)}`)
    }
  }

  const verification = record.verification ?? {}
  for (const validator of verification.validators ?? []) {
    if (!isNonEmptyString(validator.name) || !['passed', 'failed', 'not-run-with-reason'].includes(validator.result)) {
      errors.push(`verification.validators has a malformed entry: ${JSON.stringify(validator)}`)
    }
  }

  for (const decision of record.decisions ?? []) {
    for (const field of ['label', 'observation', 'rule', 'result']) {
      if (!isNonEmptyString(decision[field])) {
        errors.push(`decisions entry missing "${field}": ${JSON.stringify(decision)}`)
      }
    }
  }

  for (const finding of record.findings ?? []) {
    for (const field of ['summary', 'howFound']) {
      if (!isNonEmptyString(finding[field])) {
        errors.push(`findings entry missing "${field}": ${JSON.stringify(finding)}`)
      }
    }
  }

  for (const followUp of record.followUps ?? []) {
    if (!isInteger(followUp)) errors.push(`followUps entry must be an issue number: ${JSON.stringify(followUp)}`)
  }

  for (const child of record.children ?? []) {
    if (!isNonEmptyString(child)) errors.push(`children entry must be a session-record id: ${JSON.stringify(child)}`)
  }

  for (const ref of record.evidence ?? []) {
    for (const field of ['kind', 'system', 'uri', 'authority', 'relationship']) {
      if (!isNonEmptyString(ref[field])) errors.push(`evidence entry missing "${field}": ${JSON.stringify(ref)}`)
    }
    if (ref.authority && !['authoritative', 'working-copy', 'mirror'].includes(ref.authority)) {
      errors.push(`evidence entry has invalid authority: ${ref.authority}`)
    }
  }

  return errors
}

function validateHarnessVocabulary(record) {
  const errors = []
  const harness = record.harness ?? {}
  if (platformRegistryError) {
    errors.push(platformRegistryError)
  } else if (harness.platform && !registeredPlatforms.includes(harness.platform)) {
    errors.push(
      `harness.platform "${harness.platform}" is not registered in manifests/runtime-platforms.json or platformRegistry.additionalPlatforms`,
    )
  }
  if (harness.executor && harness.executor !== 'human' && !ALL_EXECUTION_TARGETS.includes(harness.executor)) {
    errors.push(`harness.executor "${harness.executor}" is not a known execution target (see docs/execution-targets.md)`)
  }
  if (harness.transport && !TRANSPORTS.includes(harness.transport)) {
    errors.push(`harness.transport "${harness.transport}" is not a known transport (see docs/execution-targets.md)`)
  }
  if (harness.delegationBoundary && !DELEGATION_BOUNDARIES.includes(harness.delegationBoundary)) {
    errors.push(`harness.delegationBoundary "${harness.delegationBoundary}" is not a known delegation boundary (see docs/execution-targets.md)`)
  }
  return errors
}

function declaredIssueNumbers(prBody) {
  const implemented = extractSection(prBody, 'Implemented issues') ?? ''
  const related = extractSection(prBody, 'Related issues') ?? ''
  const numbers = new Set()
  for (const text of [implemented, related]) {
    for (const match of text.matchAll(/#(\d+)/g)) {
      numbers.add(Number(match[1]))
    }
  }
  return numbers
}

function validateAgainstPrBody(record) {
  if (!prNumberArg || !prBodyPath) {
    return { skipped: true, errors: [] }
  }
  const prNumber = Number(prNumberArg)
  if (record.repository?.prNumber !== prNumber) {
    return { skipped: true, errors: [] }
  }
  if (!existsSync(prBodyPath)) {
    return { skipped: false, errors: [`--pr-body path does not exist: ${prBodyPath}`] }
  }
  const prBody = readFileSync(prBodyPath, 'utf8')
  const declared = declaredIssueNumbers(prBody)
  const errors = []
  for (const issue of record.repository?.issues ?? []) {
    if (!declared.has(issue.number)) {
      errors.push(
        `repository.issues claims #${issue.number}, but PR #${prNumber}'s own body does not declare it under Implemented issues or Related issues`,
      )
    }
  }
  return { skipped: false, errors }
}

let overallFailed = false
for (const path of targets) {
  process.stdout.write(`[validate-session-record] ${path}\n\n`)
  let record
  try {
    record = JSON.parse(readFileSync(path, 'utf8'))
  } catch (error) {
    process.stdout.write(`  FAIL  parse  -  ${error.message}\n\nResult: FAILED\n\n`)
    overallFailed = true
    continue
  }

  const shapeErrors = validateShape(record)
  const harnessErrors = validateHarnessVocabulary(record)
  const prCheck = validateAgainstPrBody(record)

  const checks = [
    {
      name: 'schema-conformance',
      ok: shapeErrors.length === 0,
      detail: shapeErrors.length === 0 ? 'matches schemas/session-record.schema.json' : shapeErrors.join('; '),
    },
    {
      name: 'harness-vocabulary',
      ok: harnessErrors.length === 0,
      detail: harnessErrors.length === 0 ? `platform=${record.harness?.platform}` : harnessErrors.join('; '),
    },
    {
      name: 'pr-body-cross-check',
      ok: prCheck.errors.length === 0,
      detail: prCheck.skipped
        ? 'not-run-with-reason: no matching --pr-number/--pr-body for this record'
        : prCheck.errors.length === 0
          ? `repository.issues verified against PR #${prNumberArg}'s own body`
          : prCheck.errors.join('; '),
    },
  ]

  let failed = false
  for (const check of checks) {
    const status = check.ok ? 'PASS' : 'FAIL'
    process.stdout.write(`  ${status}  ${check.name}  -  ${check.detail}\n`)
    if (!check.ok) failed = true
  }
  process.stdout.write(`\nResult: ${failed ? 'FAILED' : 'READY'}\n\n`)
  if (failed) overallFailed = true
}

process.exit(overallFailed ? 1 : 0)
