// Project-owned adapter for the upstream contained-receipt CLI defect.
// Uses the unmodified framework API; it never synthesizes receipt fields or digests.
import {readFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {containedPath} from '../lib/verification/workspace.mjs';
import {rollbackAdoption} from '../.tooling/agentflow-next/lib/adoption/transaction.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const args=process.argv.slice(2);
const flag=n=>{const i=args.indexOf(n);if(i<0||!args[i+1])throw Error('Required '+n);return args[i+1];};
const target=resolve(flag('--target'));
if(target!==root)containedPath(root,target);
const receiptPath=containedPath(target,flag('--receipt'));
const receipt=JSON.parse(readFileSync(receiptPath,'utf8'));
if(!/^\.agentflow\/transactions\/[a-f0-9-]+\/receipt\.json$/.test(receipt.receiptPath??'')||resolve(target,receipt.receiptPath)!==receiptPath)throw Error('Reserved contained receipt path required');
console.log(JSON.stringify(rollbackAdoption(target,receipt,{confirm:flag('--confirm')})));
// Retain the original receipt for audit. A repeated rollback is rejected by upstream state checks.
