export const meta = {
  name: 'dataset-investigator',
  description: 'Investigate one CSV/Parquet dataset: deterministic tools, model-proposed hypotheses, validated findings, and a reproducible analysis package (QuantSmith spec 0099)',
  whenToUse: 'On demand, to investigate a tabular dataset end to end. args: {dataset (required), out?, target?, timestamp?, pii?: [columns], seed?, as_of?: "YYYY-MM-DD", rounds?: 0-3, created_at?, command?}',
  phases: [
    { title: 'Profile', detail: 'load, fingerprint, column roles, deterministic plan' },
    { title: 'Plan', detail: 'planner chooses analyses from the catalog' },
    { title: 'Analyze', detail: 'registered tools run; candidate findings; templated hypotheses' },
    { title: 'Investigate', detail: 'investigator proposes hypotheses; registered tools test them' },
    { title: 'Validate', detail: 'validator checks; downgrade-only model review' },
    { title: 'Report', detail: 'grounded narrative, report, analysis package' },
  ],
}

// Spec 0099 (REQ-016, REQ-017). Two kinds of agent:
// - reasoning agents (planner, investigator, validator, writer) see only the context JSON the
//   investigator command prints (profile, roles, aggregate evidence; never rows) and answer in a schema;
// - one executor agent per step runs exactly one investigator command (`quantsmith-dataset-investigator`) this script
//   builds. The command is the enforcement boundary: it runs only registered tools with valid
//   parameters, and re-validates everything the reasoning agents return.
// Scripts cannot read files or clocks, so timestamps come in through args.

const A = args || {}
if (!A.dataset) throw new Error('args.dataset is required (path to a CSV, TSV, or Parquet file)')
const OUT = A.out || 'investigation_run'
const ROUNDS = Math.max(0, Math.min(3, A.rounds === undefined ? 2 : A.rounds))
// The repository's own toolchain by default; override with args.command (e.g. an activated venv's binary).
const CLI = A.command || 'uv run --frozen --extra investigator quantsmith-dataset-investigator'
const EOF = 'QS_EOF_0099'
const ANALYSES = ['profile', 'data_quality', 'target_balance', 'numeric_distributions', 'categorical_distributions',
  'correlations', 'target_relationships', 'missingness_relationships', 'segments', 'temporal_trends',
  'temporal_drift', 'period_patterns', 'entity_concentration', 'anomaly_detection']

const quote = s => "'" + String(s).replace(/'/g, "'\\''") + "'"

const RESULT = {
  type: 'object',
  properties: { exit_code: { type: 'integer' }, stdout: { type: 'string' }, stderr: { type: 'string' } },
  required: ['exit_code', 'stdout'],
}

async function run(command, stdin, label, phaseTitle) {
  let full = command
  if (stdin !== undefined) {
    const body = JSON.stringify(stdin)
    if (body.includes(EOF)) throw new Error(`${label}: input contains the heredoc delimiter`)
    full = `${command} <<'${EOF}'\n${body}\n${EOF}`
  }
  const r = await agent(
    'You are the executor step of the Dataset Investigator. From the repository root, run exactly the one shell ' +
    'command below with the Bash tool. Do not change it, run anything else, retry it, or open the data or any ' +
    'output file. Return its exit code, its complete stdout, and its stderr.\n\n' + full,
    { label, phase: phaseTitle, schema: RESULT, effort: 'low' })
  if (!r) throw new Error(`${label}: the executor returned nothing`)
  return r
}

function parsed(r, label) {
  if (r.exit_code !== 0) throw new Error(`${label} failed (exit ${r.exit_code}): ${(r.stderr || r.stdout || '').slice(0, 2000)}`)
  return JSON.parse(r.stdout)
}

const NUMBERS = 'State only numbers that appear in the evidence you were given. Put column names, group labels and ' +
  'dates in backticks. Describe associations, never causes.'

// --- Profile ------------------------------------------------------------------
phase('Profile')
let profile = `${CLI} profile ${quote(A.dataset)} --out ${quote(OUT)} --context planner`
if (A.target) profile += ` --target ${quote(A.target)}`
if (A.timestamp) profile += ` --timestamp ${quote(A.timestamp)}`
if (A.pii && A.pii.length) profile += ` --pii ${A.pii.map(quote).join(' ')}`
if (A.seed !== undefined) profile += ` --seed ${Number(A.seed)}`
if (A.as_of) profile += ` --as-of ${quote(A.as_of)}`
if (A.created_at) profile += ` --created-at ${quote(A.created_at)}`
const p0 = parsed(await run(profile, undefined, 'profile', 'Profile'), 'profile')
log(`Profiled ${p0.result.rows} rows × ${p0.result.columns} columns`)

// --- Plan ---------------------------------------------------------------------
phase('Plan')
const PLAN = {
  type: 'object',
  properties: {
    analyses: { type: 'array', items: { type: 'string', enum: ANALYSES } },
    rationale: { type: 'string' },
  },
  required: ['analyses', 'rationale'],
}
const plan = await agent(
  'You are the planner of a dataset investigation. Below is the dataset profile, the column roles, the analysis ' +
  'catalog, and the deterministic plan with its reasons. Choose which analyses to run and in what order, by name ' +
  'only; you cannot add tools or parameters. Keep the deterministic plan unless you have a reason in the profile ' +
  'to drop or reorder something, and say why.\n\n' + JSON.stringify(p0.context),
  { label: 'planner', phase: 'Plan', schema: PLAN })

// --- Analyze ------------------------------------------------------------------
phase('Analyze')
// The command rejects a repeated name; keep the planner's first mention of each.
const analyses = plan && plan.analyses && plan.analyses.length ? [...new Set(plan.analyses)] : null
const p1 = parsed(await run(`${CLI} run-plan ${quote(OUT)} --templates --context investigator` +
  (analyses ? ' --analyses -' : ''), analyses ? { analyses } : undefined, 'run-plan', 'Analyze'), 'run-plan')
log(`${p1.result.executions} tool executions, ${p1.result.candidate_findings} candidate findings`)
let ctx = p1.context

// --- Investigate --------------------------------------------------------------
phase('Investigate')
const CONDITION = {
  type: 'object',
  properties: { path: { type: 'string' }, op: { type: 'string', enum: ['>=', '>', '<=', '<', '==', '!='] }, value: { type: 'number' } },
  required: ['path', 'op', 'value'],
}
const PROPOSALS = {
  type: 'object',
  properties: {
    hypotheses: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          statement: { type: 'string' },
          from_findings: { type: 'array', items: { type: 'string' } },
          tool: { type: 'string' },
          params: { type: 'object' },
          prediction: { type: 'string' },
          decision_rule: {
            type: 'object',
            properties: { supported: { type: 'array', items: CONDITION }, rejected: { type: 'array', items: CONDITION } },
            required: ['supported', 'rejected'],
          },
        },
        required: ['statement', 'from_findings', 'tool', 'params', 'prediction', 'decision_rule'],
      },
    },
    done: { type: 'boolean' },
  },
  required: ['hypotheses', 'done'],
}
for (let round = 1; round <= ROUNDS; round++) {
  if (!ctx.budget || ctx.budget.tool_calls_left <= 0) { log('Tool-call budget spent; stopping the hypothesis loop'); break }
  const proposal = await agent(
    'You are the investigator of a dataset investigation. Below are the candidate findings with their evidence, ' +
    'the hypotheses already tested, the registered tools with their parameter schemas, the decision-rule ' +
    'language, and the remaining budget. Propose up to 4 new, testable hypotheses that could change how a finding ' +
    'should be read — especially ones that could REJECT a tempting reading (denominator effects, confounding by ' +
    'another column, concentration in a few entities). Each must use a registered tool with valid parameters and ' +
    'a decision rule on fields that tool returns. Do not repeat a tested hypothesis. Set done=true if nothing ' +
    'worth testing remains. ' + NUMBERS + '\n\n' + JSON.stringify(ctx),
    { label: `investigator:${round}`, phase: 'Investigate', schema: PROPOSALS })
  if (!proposal || !proposal.hypotheses.length) { log(`Round ${round}: no new hypotheses`); break }
  const r = parsed(await run(`${CLI} hypotheses ${quote(OUT)} --add - --context investigator`,
    { hypotheses: proposal.hypotheses }, `hypotheses:${round}`, 'Investigate'), `hypotheses:${round}`)
  const tested = r.result.tested || []
  log(`Round ${round}: ` + tested.map(h => `${h.hypothesis_id} ${h.status}`).join(', '))
  ctx = r.context
  if (proposal.done) break
}

// --- Validate -----------------------------------------------------------------
phase('Validate')
const v0 = parsed(await run(`${CLI} validate ${quote(OUT)} --context validator`, undefined, 'validate', 'Validate'), 'validate')
const REVIEW = {
  type: 'object',
  properties: {
    reviews: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          finding: { type: 'string' },
          status: { type: 'string', enum: ['WEAK_EVIDENCE', 'INCONCLUSIVE', 'REJECTED'] },
          confidence: { type: 'string', enum: ['low', 'medium'] },
          note: { type: 'string' },
        },
        required: ['finding', 'note'],
      },
    },
  },
  required: ['reviews'],
}
const review = await agent(
  'You are the validation reviewer of a dataset investigation. The deterministic validator has already checked ' +
  'every claim (numbers, causal wording, sample size, significance after multiple-testing adjustment, ' +
  'reproduction). Read each claim against its evidence and flag only real problems: wording that overstates the ' +
  'evidence, a comparison that is not like for like, a confidence that is too high. You may only downgrade. ' +
  'Return an empty list if every claim is fair.\n\n' + JSON.stringify(v0.context),
  { label: 'validator-review', phase: 'Validate', schema: REVIEW })
const reviews = review && review.reviews ? review.reviews : []
const v1 = parsed(await run(`${CLI} validate ${quote(OUT)} --context writer` + (reviews.length ? ' --review -' : ''),
  reviews.length ? { reviews } : undefined, 'validate:final', 'Validate'), 'validate:final')
log(`Key findings: ${(v1.result.key_findings || []).join(', ') || 'none'}`)

// --- Report -------------------------------------------------------------------
phase('Report')
const NARRATIVE = { type: 'object', properties: { narrative: { type: 'string' } }, required: ['narrative'] }
let feedback = ''
let accepted = null
let narrativeIncluded = false
for (let attempt = 1; attempt <= 2 && !accepted; attempt++) {
  const w = await agent(
    'You are the report writer of a dataset investigation. Write a short executive narrative (at most 250 words) ' +
    'of what the evidence establishes, what it does not, and what to investigate next, from the validated ' +
    'findings, hypotheses and questions below. ' + NUMBERS + feedback + '\n\n' + JSON.stringify(v1.context),
    { label: `writer:${attempt}`, phase: 'Report', schema: NARRATIVE })
  if (!w || !w.narrative) break
  const r = await run(`${CLI} report ${quote(OUT)} --export --narrative -`, w.narrative, `report:${attempt}`, 'Report')
  if (r.exit_code === 0) { accepted = JSON.parse(r.stdout); narrativeIncluded = true; break }
  if (r.exit_code !== 5) parsed(r, `report:${attempt}`)
  const why = JSON.parse(r.stdout)
  feedback = ` Your previous draft was rejected: unbacked values ${JSON.stringify(why.unbacked)}, causal wording ` +
    `${JSON.stringify(why.causal)}. Use only numbers and labels present in the evidence.`
}
if (!accepted) {
  log('Narrative not accepted; writing the template report without it')
  accepted = parsed(await run(`${CLI} report ${quote(OUT)} --export`, undefined, 'report:template', 'Report'), 'report:template')
}

return {
  run: OUT,
  report: accepted.report,
  package: accepted.package,
  key_findings: accepted.key_findings,
  hypotheses: accepted.hypotheses,
  questions: accepted.questions,
  narrative_included: narrativeIncluded,
  reproduce: `cd ${OUT}/analysis_package && dataset-investigator reproduce <FINDING_ID> --data ${A.dataset}`,
}
