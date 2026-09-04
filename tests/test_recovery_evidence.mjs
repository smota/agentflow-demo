import test from 'node:test'
import { verifyRecoveryEvidence } from '../scripts/verify-recovery-evidence.mjs'

test('committed recovery and fresh-context evidence satisfies the contract', () => {
  verifyRecoveryEvidence()
})
