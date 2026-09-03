import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const contract = JSON.parse(readFileSync(new URL('../docs/demo/evidence/recovery-contract.json', import.meta.url), 'utf8'))

test('recovery contract fences writers and stale plans', () => {
  assert.equal(contract.schemaVersion, 1)
  assert.equal(contract.runId, 'awesomeawesomeness-2-final')
  assert.equal(contract.goal, 'issue:24')
  assert.equal(contract.source.kind, 'github')
  assert.equal(contract.source.coordinationBranch, 'agentflow-state')
  assert.equal(contract.recovery.initialGeneration, 0)
  assert.equal(contract.recovery.replacementGeneration, 1)
  assert.equal(contract.recovery.requiresCheckpoint, true)
  assert.equal(contract.recovery.requiresPause, true)
  assert.equal(contract.recovery.rejectsObsoleteWriter, true)
  assert.equal(contract.recovery.rejectsStalePlan, true)
})

test('publication and fresh-context boundaries are explicit', () => {
  assert.equal(contract.publication.issue, 24)
  assert.equal(contract.publication.attempts, 2)
  assert.equal(contract.publication.maximumCreatedComments, 1)
  assert.equal(contract.publication.requiresReconciliation, true)
  assert.equal(contract.freshContext.conversationHistoryAllowed, false)
  assert.equal(contract.freshContext.localScratchRequired, false)
  assert.deepEqual(contract.freshContext.requiredFields, ['issue','branch','candidate','gate','findings','nextSafeAction'])
})

test('release evidence keeps independent observations', () => {
  assert.deepEqual(contract.releaseObservations, ['commit','checks','tag','githubRelease','deployment'])
})
