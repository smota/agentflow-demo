// Project-owned formatter/publisher. It records supplied evidence; it never decides a gate.
import { readFileSync, writeFileSync, mkdirSync, existsSync, renameSync } from 'node:fs'
import { resolve, dirname, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
process.chdir(root)
const roles = ['product-manager-jtbd', 'analyst', 'architect', 'developer-planning', 'developer', 'tester', 'review', 'tech-writer', 'pr-readiness']
const repo = 'smota/agentflow-demo'
const safe = (path) => {
  const target = resolve(root, path)
  if (!target.startsWith(root + sep)) throw new Error('Artifact must stay inside the demo repository')
  return target
}
const save = (path, text) => { const p = safe(path); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p + '.tmp', text); renameSync(p + '.tmp', p) }
const hash = (text) => createHash('sha256').update(text).digest('hex')
const git = (...args) => execFileSync('git', ['-c', `safe.directory=${root.replaceAll('\\', '/')}`, ...args], { encoding: 'utf8' }).trim()
const api = (path, body) => JSON.parse(execFileSync('gh', ['api', path, ...(body ? ['--method', 'POST', '--input', '-'] : [])], { encoding: 'utf8', input: body ? JSON.stringify(body) : undefined }))
const [command, input] = process.argv.slice(2)

if (command === 'record') {
  const entry = JSON.parse(readFileSync(safe(input), 'utf8'))
  if (!Number.isInteger(entry.issue) || entry.issue < 1 || !roles[entry.phase]) throw new Error('Invalid issue or phase')
  if (!entry.summary || !entry.next || !entry.inputs?.length) throw new Error('Evidence needs summary, next contract and inputs')
  const dir = `.agent-runs/issues/${entry.issue}`
  const ledgerPath = `${dir}/ledger.json`
  const ledger = existsSync(safe(ledgerPath)) ? JSON.parse(readFileSync(safe(ledgerPath), 'utf8')) : []
  if (ledger.length && !entry.inputs.includes(ledger.at(-1).path)) throw new Error('Read and reference the previous role pass before recording the next')
  const phase = entry.phase
  const epic = entry.epic ?? (entry.issue >= 16 ? 16 : 1)
  const authorizationDate = entry.issue >= 16 ? '2026-09-03' : '2026-09-02'
  const role = roles[phase]
  const stamp = new Date().toISOString()
  const branch = git('branch', '--show-current')
  const profile = entry.profile ?? 'standard'
  const status = entry.status ?? 'pass'
  if (!['pass', 'returned', 'blocked', 'skipped'].includes(status)) throw new Error('Invalid status')
  const nextPhase = status === 'returned' ? (phase === 4 ? 3 : 4) : Math.min(phase + 1, 8)
  if (ledger.length) {
    const prior = ledger.at(-1)
    const expected = prior.status === 'returned' ? (prior.phase === 4 ? 3 : 4) : prior.phase + 1
    if (phase !== expected) throw new Error(`Invalid phase transition: expected ${expected}, got ${phase}`)
  }
  const transition = {version:1, subject:`issue:${entry.issue}`, fromRole:role, toRole:roles[nextPhase], decision:status, nextContract:entry.next, timestamp:stamp, profile, actionBoundary:{version:1, profile, requested:'external-action', effective:'external-action', enforcementRefs:['docs/demo/goal.md']},inputRefs:[],outputRefs:[],validationRefs:[],openQuestions:[],extensionPlays:[],provenance:{platform:'codex',executor:'codex-cli',transport:'local-cli',delegationBoundary:'current-session'}}
  const markdown = `## Role Pass\n\n**Issue:** #${entry.issue}\n**Branch:** ${branch}\n**Phase:** ${phase}\n**Role:** ${role}\n**Status:** ${status}\n**Workflow profile:** ${profile}\n**Action boundary:** external-action\n**Planned owner:** not-applicable:single-agent\n**Executed by:** codex\n**Launcher:** codex\n**Executor:** codex-cli\n**Transport:** local-cli\n**Delegation boundary:** current-session\n**Context boundary:** current-session\n**Independence boundary:** ${role === 'review' ? 'self-review' : 'not-applicable'}\n**Model / runtime:** Codex desktop; model not recorded\n\n### Inputs read\n\n${entry.inputs.map(x => '- ' + x).join('\n')}\n\n### Decisions / findings\n\n${entry.summary}\n\n### Validation evidence\n\n${entry.validation ?? 'No gate result asserted by this phase.'}\n\n### Open questions\n\n${entry.questions ?? 'None.'}\n\n### Next-phase contract\n\n${entry.next}\n\n### Transition envelope\n\n\`\`\`json\n${JSON.stringify(transition,null,2)}\n\`\`\`\n\nSigned-off-by: codex (${role})\nTimestamp: ${stamp}\n`
  const path = `${dir}/passes/${String(phase).padStart(2,'0')}-${role}-${ledger.length + 1}.md`
  save(path, markdown)
  execFileSync(process.execPath, ['scripts/validate-sdlc-role-pass.mjs', '--path', path], {stdio:'inherit'})
  ledger.push({phase, role, status, summary:entry.summary, next:entry.next, timestamp:stamp, path, digest:hash(markdown), commit:git('rev-parse','HEAD')})
  save(ledgerPath, JSON.stringify(ledger,null,2)+'\n')
  save(`${dir}/handover.md`, `<!-- agent-handover -->\n## Role handover ledger — issue #${entry.issue}\n\nOne accountable Codex executor; same-platform helpers are advisory, not cross-platform role alternation. Approval: user activated the scoped demo goal on ${authorizationDate}.\n\n` + ledger.map(x => `### ${x.phase} — ${x.role} (${x.status})\n\n${x.summary}\n\nNext contract: ${x.next}\n\nRole-pass SHA-256: ${x.digest}\n\nSigned-off-by: codex (${x.role}), ${x.timestamp}\n`).join('\n'))
  save('.agent-runs/checkpoint.json', JSON.stringify({schemaVersion:1, repository:repo, epic, issue:entry.issue, branch, commit:git('rev-parse','HEAD'), phase, lastRolePass:path, lastRolePassDigest:hash(markdown), nextSafeAction:entry.next, openRework:entry.openRework ?? [], updatedAt:stamp},null,2)+'\n')
  console.log(path)
} else if (command === 'publish') {
  const issue = Number(input)
  if (!Number.isInteger(issue) || issue < 1) throw new Error('Invalid issue')
  const body = readFileSync(safe(`.agent-runs/issues/${issue}/handover.md`),'utf8')
  const comments = JSON.parse(execFileSync('gh', ['api', `repos/${repo}/issues/${issue}/comments`, '--paginate', '--slurp'], {encoding:'utf8'})).flat()
  const existing = comments.filter(x => x.body.startsWith('<!-- agent-handover -->'))
  if (existing.length > 1) throw new Error('Multiple ledgers; reconcile manually')
  let result
  if (existing.length) {
    result = JSON.parse(execFileSync('gh',['api',`repos/${repo}/issues/comments/${existing[0].id}`,'--method','PATCH','--input','-'],{encoding:'utf8',input:JSON.stringify({body})}))
  } else result = api(`repos/${repo}/issues/${issue}/comments`,{body})
  save(`.agent-runs/issues/${issue}/remote.json`, JSON.stringify({handoverUrl:result.html_url,commentId:result.id},null,2)+'\n')
  console.log(result.html_url)
  const ledger = JSON.parse(readFileSync(safe(`.agent-runs/issues/${issue}/ledger.json`), 'utf8'))
  const latest = ledger.at(-1)
  const statusBody = `<!-- ativaly-workflow-status -->\n## Workflow Status\n\n**Issue:** #${issue}\n**Profile:** standard\n**Mode:** single-agent\n**Implemented by:** codex\n**Executor:** codex-cli\n**Transport:** local-cli\n**Delegation boundary:** current-session\n**Action boundary:** external-action\n**Review:** ${latest.phase >= 6 ? 'self-review' : 'pending'}\n**State:** ${latest.status === 'returned' ? 'implementing' : latest.phase === 8 ? 'ready' : 'verifying'}\n**Current phase:** ${latest.phase}\n\n### Latest Role Pass\n\n${latest.summary}\n\n### Next Action\n\n${latest.next}\n\n### Evidence\n\n[Signed phase handovers](${result.html_url})\n\nEvidence digest: ${latest.digest}\n\nLocal scratch is not committed. Simulated stakeholder review is not human approval.\n\nSigned-off-by: codex (orchestrator)\nTimestamp: ${latest.timestamp}\n`
  const statuses = comments.filter(x => x.body.startsWith('<!-- ativaly-workflow-status -->'))
  if (statuses.length > 1) throw new Error('Multiple workflow statuses; reconcile manually')
  const statusResult = statuses.length
    ? JSON.parse(execFileSync('gh',['api',`repos/${repo}/issues/comments/${statuses[0].id}`,'--method','PATCH','--input','-'],{encoding:'utf8',input:JSON.stringify({body:statusBody})}))
    : api(`repos/${repo}/issues/${issue}/comments`,{body:statusBody})
  save(`.agent-runs/issues/${issue}/remote.json`, JSON.stringify({handoverUrl:result.html_url,commentId:result.id,statusUrl:statusResult.html_url,statusId:statusResult.id},null,2)+'\n')
  console.log(statusResult.html_url)
} else throw new Error('Usage: node scripts/demo-evidence.mjs record <input.json> | publish <issue>')
