// Project-owned CI entrypoint. Managed validators are invoked from the pinned source.
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
const root=process.cwd();
const pin=JSON.parse(readFileSync('agentflow-source.json','utf8'));
const runtime=resolve(pin.runtimePath);
const head=execFileSync('git',['-c',`safe.directory=${runtime.replaceAll('\\','/')}`,'-C',runtime,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
if(head!==pin.revision)throw Error('Agentflow runtime does not match source pin');
// Compare raw Git blob bytes, not text-filtered status: upstream contains CRLF JSON.
const tree=execFileSync('git',['-c',`safe.directory=${runtime.replaceAll('\\','/')}`,'-C',runtime,'ls-tree','-rz','HEAD'],{encoding:'utf8'});
for(const entry of tree.split('\0').filter(Boolean)){
 const [metadata,path]=entry.split('\t');const [mode,type,oid]=metadata.split(' ');
 if(type!=='blob'||!['100644','100755'].includes(mode))throw Error('Unexpected runtime tree entry');
 const bytes=readFileSync(resolve(runtime,path));
 const actual=createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
 if(actual!==oid)throw Error('Pinned runtime bytes changed: '+path);
}
const cli=(...args)=>execFileSync(process.execPath,[resolve(runtime,'bin/cli.mjs'),...args,'--target',root],{stdio:'inherit'});
cli('sdlc','validate');cli('sdlc','validate-authority');
for(const script of ['validate-spec.mjs','validate-branch-strategy.mjs','validate-role-routing.mjs'])execFileSync(process.execPath,[resolve(runtime,'scripts',script),'--target',root],{stdio:'inherit'});
const plan=JSON.parse(execFileSync(process.execPath,[resolve(runtime,'bin/cli.mjs'),'adopt','plan','--profile',pin.profile,'--storage','project','--target',root,'--json'],{encoding:'utf8'}));
if(plan.blocked||plan.actions.some(a=>!['unchanged','seed-skip'].includes(a.action)))throw Error('Managed adoption is not current');
console.log(`Pinned current Agentflow verified: ${head}; ${plan.actions.filter(a=>a.ownership==='managed').length} managed files.`);
