// Project integration of the installed, unmodified Agentflow collector and role contracts.
import {readFileSync,writeFileSync,mkdirSync,existsSync,readdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {collectProcessObservation,inspectProcessRuntime} from '../lib/verification/process-collector.mjs';
import {verifyObservation} from '../lib/core/verification-observation.mjs';
import {recordDigest} from '../lib/core/record-digest.mjs';
import {fingerprintCandidate} from '../lib/verification/workspace.mjs';
import {createRoleHandoff} from '../lib/role-catalog.mjs';
import {createAcceptanceContract,createDeliveryReceipt,createAcceptanceDecision,verifyRoleAdvance} from '../lib/core/role-collaboration.mjs';
const [command,issue,reason]=process.argv.slice(2);
if(!/^\d+$/.test(issue??''))throw Error('Numeric issue required');
const root=process.cwd(),dir=resolve('.agent-runs/issues',issue,'typed');
const read=n=>JSON.parse(readFileSync(resolve(dir,n+'.json'),'utf8'));
const save=(n,data)=>{mkdirSync(dir,{recursive:true});writeFileSync(resolve(dir,n+'.json'),JSON.stringify(data,null,2)+'\n');};
const tree=p=>readdirSync(p,{withFileTypes:true}).flatMap(e=>e.name==='__pycache__'?[]:e.isDirectory()?tree(p+'/'+e.name):[p+'/'+e.name]);
if(command==='freeze'){
 if(existsSync(resolve(dir,'contract.json'))){if(!reason)throw Error('Prior contract exists; provide an explicit supersession reason');save('superseded-'+Date.now(),{reason,prior:Object.fromEntries(['contract','handoff','definition','candidate','observation','delivery','decision','advance'].filter(n=>existsSync(resolve(dir,n+'.json'))).map(n=>[n,read(n)]))});}
 const inputs=['app.py','requirements.txt','requirements-dev.txt','agentflow-source.json','agent-framework-lock.json','package.json','sdlc.config.json','agent-workflow.config.json','SPEC.md','data/catalogue.json',...tree('awesome'),...tree('tests'),...tree('tools'),...tree('scripts'),...tree('lib'),...tree('.github/workflows')].filter(x=>/\.(py|json|mjs|txt|md|yml|yaml)$/.test(x));inputs.push('.gitattributes');
 if(existsSync('data/list-index.json')){inputs.push('data/list-index.json');inputs.push(...tree('data/lists'));}
 const definition={id:'suite',criterionId:'suite',executable:process.execPath,args:['scripts/verification-suite.mjs'],inputs:[...new Set(inputs)].sort(),assertions:['pytest-suite','catalogue','framework'],timeoutMs:180000,format:'structured',env:{PYTHONDONTWRITEBYTECODE:'1',PYTHONUTF8:'1',GIT_CONFIG_COUNT:'1',GIT_CONFIG_KEY_0:'safe.directory',GIT_CONFIG_VALUE_0:root.replaceAll('\\','/')}};
 const candidate=fingerprintCandidate(root,definition);
 const contract=createAcceptanceContract({id:'tests-'+issue,subject:'issue:'+issue,ownerRole:'agentflow:developer',deliveryRole:'agentflow:tester',collaborationClass:'bilateral',candidateDigest:candidate.digest,criteria:[{id:'suite',description:'Run all current pytest cases, catalogue validation and pinned framework checks without changing declared inputs',verification:'deterministic',required:true}],councilPolicy:{required:false,seats:[],decisionOwner:'agentflow:developer'}});
 const handoff=createRoleHandoff({id:'test-handoff-'+issue,subject:contract.subject,state:'issued',fromRole:contract.ownerRole,toRole:contract.deliveryRole,acceptanceContract:contract});
 save('definition',definition);save('candidate',candidate);save('contract',contract);save('handoff',handoff);console.log(JSON.stringify({contract:contract.digest,candidate:candidate.digest,next:'verify'}));
}else if(command==='verify'){
 const definition=read('definition'),contract=read('contract');
 if(fingerprintCandidate(root,definition).digest!==contract.candidateDigest)throw Error('Candidate changed since handoff');
 const result=collectProcessObservation({root,definition,boundary:'mutate-worktree'});
 save('observation',result.observation);save('collector-reference',{path:result.observationPath});
 console.log(JSON.stringify(result.observation));if(result.observation.outcome!=='pass')process.exitCode=1;
}else if(command==='accept'){
 const definition=read('definition'),contract=read('contract'),handoff=read('handoff'),observation=read('observation');
 const persisted=JSON.parse(readFileSync(read('collector-reference').path,'utf8'));
 if(persisted.digest!==observation.digest||persisted.outcome!=='pass'||fingerprintCandidate(root,definition).digest!==contract.candidateDigest||observation.candidateDigest!==contract.candidateDigest)throw Error('Absent, failed or stale collector evidence');
 if(inspectProcessRuntime(root,definition).identity.digest!==observation.executionContextDigest)throw Error('Execution runtime changed');
 const resolution=verifyObservation({observation:persisted,candidateDigest:contract.candidateDigest,definitionDigest:recordDigest(definition),requiredAssertions:definition.assertions,sourceVerified:true,maxAgeMs:3600000});
 if(resolution.status!=='pass')throw Error(JSON.stringify(resolution));save('resolution',resolution);
 const evidence={kind:'validation',system:'local',uri:'.agent-runs/issues/'+issue+'/typed/observation.json',authority:'working-copy',relationship:'verifies',digest:observation.digest};
 const delivery=createDeliveryReceipt({id:'test-delivery-'+issue,handoffDigest:handoff.digest,contractDigest:contract.digest,producerRole:contract.deliveryRole,candidateDigest:contract.candidateDigest,criteriaResults:[{criterionId:'suite',status:'pass',evidenceRefs:[evidence]}],evidenceRefs:[evidence],provenance:{platform:'codex',executor:'codex-cli'}});
 const decision=createAcceptanceDecision({id:'test-acceptance-'+issue,handoff,contract,delivery,decidedByRole:contract.ownerRole,state:'accepted',semanticFindings:[],provenance:{platform:'codex'}});
 const verification=verifyRoleAdvance({handoff,contract,delivery,decision,openReworkRequests:[]});
 if(!verification.ok)throw Error(JSON.stringify(verification));save('delivery',delivery);save('decision',decision);save('advance',verification);console.log(JSON.stringify({state:decision.state,decision:decision.digest,verification}));
}else throw Error('Use freeze, verify or accept with issue number');
