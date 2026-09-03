import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const load = (relative) => JSON.parse(readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8'))

export function verifyRecoveryEvidence() {
  const contract = load('docs/demo/evidence/recovery-contract.json')
  const recovery = load('docs/demo/evidence/recovery-rc1.json')
  const fresh = load('docs/demo/evidence/fresh-context-rc1.json')

  assert.equal(recovery.schemaVersion, 1)
  assert.equal(recovery.run.id, contract.runId)
  assert.equal(recovery.run.goal, contract.goal)
  assert.equal(recovery.run.sourceBranch, contract.source.coordinationBranch)
  assert.equal(recovery.run.generation, contract.recovery.replacementGeneration)
  assert.equal(recovery.recovery.previousOwnerStopped, true)
  assert.equal(recovery.recovery.candidateInvalidatedOnTransfer, true)
  assert.equal(recovery.recovery.stalePlanExitCode, 4)
  assert.equal(recovery.recovery.obsoleteWriterExitCode, 4)
  assert.match(recovery.recovery.failedObservation, /^[a-f0-9]{64}$/)
  assert.match(recovery.recovery.passingObservation, /^[a-f0-9]{64}$/)
  assert.notEqual(recovery.recovery.failedObservation, recovery.recovery.passingObservation)
  assert.equal(recovery.publication.attempts, contract.publication.attempts)
  assert.equal(recovery.publication.createdComments, contract.publication.maximumCreatedComments)
  assert.equal(recovery.publication.state, 'confirmed')
  assert.equal(recovery.freshContext.result, 'pass')
  assert.equal(recovery.freshContext.conversationHistoryUsed, false)
  assert.equal(recovery.freshContext.localScratchUsed, false)

  assert.equal(fresh.issue, contract.publication.issue)
  assert.equal(fresh.branch, 'codex/recovery-stable-2')
  assert.match(fresh.candidate, /^[a-f0-9]{40}$/)
  assert.match(fresh.gate, /product-manager.*verify-and-advance/)
  assert.ok(fresh.findings.some((finding) => finding.includes('Generation-0 writer')))
  assert.ok(fresh.findings.some((finding) => finding.includes('subsequent immutable collector observation passed')))
  assert.ok(fresh.findings.some((finding) => finding.includes('confirmed state')))
  assert.ok(fresh.nextSafeAction.includes(fresh.candidate))
  assert.ok(contract.freshContext.requiredFields.every((field) => Object.hasOwn(fresh, field)))
  return {run: recovery.run.id, generation: recovery.run.generation, candidate: fresh.candidate}
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = verifyRecoveryEvidence()
  process.stdout.write(`Recovery evidence READY: ${JSON.stringify(result)}\n`)
}
