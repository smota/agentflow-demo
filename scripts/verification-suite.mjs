// Produces invocation-bound evidence only after executing the real checks.
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
const report=process.env.AGENTFLOW_REPORT_PATH,invocationId=process.env.AGENTFLOW_INVOCATION_ID;
if(!report||!invocationId)throw Error('Use the Agentflow process collector');
const python=existsSync('.venv/Scripts/python.exe')?resolve('.venv/Scripts/python.exe'):'python';
const junit=resolve(dirname(report),'pytest.xml');
const assertions=[];
const check=(id,fn)=>{try{fn();assertions.push({id,outcome:'pass'});}catch(error){assertions.push({id,outcome:'fail'});console.error(id+': '+error.message);}};
check('pytest-suite',()=>{
 execFileSync(python,['-m','pytest','-q','--basetemp=.cache/pytest','--junitxml='+junit],{stdio:'pipe',timeout:120000});
 const xml=readFileSync(junit,'utf8');
 if(!/<testsuite\s/.test(xml)||!/<testcase\s/.test(xml)||/<(?:failure|error)(?:\s|>)/.test(xml))throw Error('Missing or failing JUnit assertions');
 const count=(xml.match(/<testcase\s/g)||[]).length;if(count<72)throw Error('Baseline test coverage unexpectedly reduced');
 console.log('Real pytest cases: '+count);
});
check('catalogue',()=>{
 execFileSync(python,['-m','tools.crawl','validate'],{stdio:'pipe',timeout:30000});
 if(existsSync('data/list-index.json'))execFileSync(python,['-m','tools.lists','validate'],{stdio:'pipe',timeout:180000});
});
check('framework',()=>execFileSync(process.execPath,['scripts/check-framework.mjs'],{stdio:'pipe',timeout:30000}));
writeFileSync(report,JSON.stringify({invocationId,assertions}));
if(assertions.some(x=>x.outcome!=='pass'))process.exitCode=1;
