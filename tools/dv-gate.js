export const meta = {
  name: 'dv-content-gate',
  description: 'Put already-authored DV skills through the gate: adversarial review, fix, independent recheck',
  phases: [
    { title: 'Review', detail: 'adversarial review per skill' },
    { title: 'Fix', detail: 'close the findings and the machine-checked consistency findings' },
    { title: 'Recheck', detail: 'a fresh reviewer per skill; ready:true is the publish gate' },
  ],
}

const REPO = 'E:\\code\\VLSI\\semiskill'

// args may arrive as an object or a JSON string. An empty batch reported as success is the worst
// available failure for a batch driver, so parse both forms and throw loudly.
const ARGS = typeof args === 'string' ? JSON.parse(args) : (args || {})
const CELLS = ARGS.cells || []
const BATCH = ARGS.batch != null ? ARGS.batch : '?'
if (!CELLS.length) {
  throw new Error('no cells passed to the gate — refusing to report an empty batch as a success')
}

const RULES = `
# READ THE CONTRACT FIRST — it is a file, not a summary

Before you do anything else, read **E:/code/VLSI/semiskill/docs/AUTHORING_CONTRACT.md**
in full. It is the single source of truth for what a skill in this pack must be: the standing rules,
the handoff vocabulary, the required frontmatter and body structure, and the review calibration.
It used to be pasted into three workflow scripts; three copies of a contract is three contracts.

Also read, as the contract tells you to:
  E:/code/VLSI/semiskill/skills/_shared/team-profile.md
  E:/code/VLSI/semiskill/skills/_shared/failure-signature-schema.md
  E:/code/VLSI/semiskill/skills/_shared/handoff-vocabulary.md
  E:/code/VLSI/semiskill/skills/dv-sim-log-first-error/SKILL.md   (golden: voice, density)
  E:/code/VLSI/semiskill/skills/dv-ral-bringup/SKILL.md          (golden: decision tree)

# The mechanical constraints, inlined because a lint failure wastes a whole agent run

The skill is scanned by a security pipeline and must score exactly 1.000. Any ONE of these blocks it:
 - ANY url (\`http\` followed by \`://\`). Cite documents by name and clause.
 - curl, wget, urllib, requests.get, socket., fetch(, "nc -".
 - Any of {eval, exec, function} immediately followed by "(" — CASE INSENSITIVE. Write "function H(s)".
 - "run the following command/script/shell/bash"; "you are now a/an/the ..." — instant hard fails.
 - "ignore ... previous/prior/above instructions"; "disregard the above/previous/system".
 - The letters "exfiltrat" in any word — write "unauthorised data egress".
 - "execute arbitrary code/commands"; a dotted quad (10.2.1.4); an NNN-NN-NNNN number;
   four groups of four digits; a 200+ character unbroken alphanumeric run.
 - {token, secret, password, api_key, passwd, pwd} followed by ":" or "=" then 16+ chars, even as a
   fake placeholder — use \`token: <your-token>\`. No [[FILL:]] slot named after a credential.
 - "<<<" or ">>>" anywhere.
 - Unquoted YAML values containing ": " or starting with @ \` % * & ! | > [ or {.

**lint 1.000 is a SECURITY score. It says nothing about whether the DV content is correct.**

`

const VERIFY = `
## Verify before you finish — MANDATORY, two commands, from ${REPO}

    python -m semiskill.cli lint skills/<your-slug>
    python -m semiskill.cli lint skills/

The first must print \`[approve 1.000]\` and \`clean\` with ZERO findings of any level. The second is
the pack-level check across every skill — it must not report ANY consistency **error**, and must not
report a C001/C005 **warn** naming YOUR slug. Iterate until both hold. The linter prints the exact
line and a fix for every finding.

Edit ONLY your own skill directory. Never modify the linter, the scanners, sibling skills or
_shared/ — other agents own those and are editing them concurrently.
`

const REVIEW_SCHEMA = {
  type: 'object',
  required: ['slug', 'verb_honesty', 'hallucination_risks', 'technical_errors', 'budget_violations', 'must_fix'],
  properties: {
    slug: { type: 'string' },
    verb_honesty: { type: 'array', items: { type: 'string' } },
    hallucination_risks: { type: 'array', items: { type: 'string' } },
    technical_errors: { type: 'array', items: { type: 'string' } },
    budget_violations: { type: 'array', items: { type: 'string' } },
    unused_slots: { type: 'array', items: { type: 'string' } },
    must_fix: { type: 'array', items: { type: 'string' } },
    open_twice: { type: 'string' },
  },
}

const FIX_SCHEMA = {
  type: 'object',
  required: ['slug', 'lint_line', 'clean', 'fixed', 'not_fixed'],
  properties: {
    slug: { type: 'string' }, lint_line: { type: 'string' }, clean: { type: 'boolean' },
    consistency_line: { type: 'string' },
    fixed: { type: 'array', items: { type: 'string' } },
    not_fixed: { type: 'array', items: { type: 'string' } },
  },
}

const RECHECK_SCHEMA = {
  type: 'object',
  required: ['slug', 'ready', 'why', 'remaining'],
  properties: {
    slug: { type: 'string' }, ready: { type: 'boolean' }, why: { type: 'string' },
    remaining: { type: 'array', items: { type: 'string' } },
    new_problems: { type: 'array', items: { type: 'string' } },
  },
}

phase('Review')
log(`Batch ${BATCH}: ${CELLS.length} authored skills through review -> fix -> independent recheck`)

const results = await pipeline(
  CELLS,

  // 1. adversarial review
  c => agent(`${RULES}

# YOUR TASK — adversarially review one already-written skill

Read ${REPO}\\skills\\${c.slug}\\SKILL.md in full, plus the _shared/ files and a golden reference,
and attack it. Default to finding problems: a clean review here is almost certainly a failed review.
This skill was written by an agent in a batch and has NOT been reviewed by anyone yet.

 1. **Verb honesty** — quote every step where the AGENT is made to run a tool, merge a database,
    compute a metric, open a waveform, or submit a job. It has only Read, Grep and Glob over files.
 2. **Hallucination risk** — every specific tool flag, message string, file name, default, or
    convention the author could not have known and that is not a [[FILL:]] slot. These are the lines
    that make a senior engineer close the file and never reopen it.
 3. **Technical errors** — anything wrong or misleading about the DV domain. Be specific and cite the
    line. This is the most valuable thing you can find.
 4. **Budget violations** — steps that cannot be carried out within the skill's own stated caps, and
    Greps the steps spend that the budget never accounts for.
 5. **Unused slots** — declared and never consumed.
 6. **Dead handoff values** — a value the report block offers that no step ever tells the reader to
    assign. Two engineers will fill those in differently.
 7. **Would a busy DV engineer open it twice?** Answer honestly.

${c.findings && c.findings.length ? `The machine checker already found these on this skill — treat
them as confirmed and include them in must_fix:\n${c.findings.map(f => ` - ${f}`).join('\n')}\n` : ''}
Do NOT edit any file. Report only.`,
    { label: `review:${c.slug}`, phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'feature-dev:code-reviewer' }),

  // 2. fix
  (review, c) => agent(`${RULES}

# YOUR TASK — close the review findings on ${c.slug}

The skill is at ${REPO}\\skills\\${c.slug}\\SKILL.md. Here is the review:

${JSON.stringify(review, null, 1).slice(0, 30000)}

Everything under must_fix, technical_errors, verb_honesty and budget_violations is not optional. Fix
each so the claim becomes CORRECT, not so it becomes unfalsifiable — the next reviewer checks for
exactly that. Anything you deliberately do not fix, say why.

${c.findings && c.findings.length ? `ALSO close these machine-checked consistency findings on this
skill:\n${c.findings.map(f => ` - ${f}`).join('\n')}

For a dead handoff value (C005) you must choose deliberately: either ADD the step branch that tells
the reader to assign it, or DROP the value from the block. Adding a branch is usually the better fix
when the value names a real outcome the procedure can reach; dropping is right when the value was
speculative. Do not simply mention the word somewhere to silence the checker — that is the
unfalsifiable fix, and the recheck looks for it.\n` : ''}
Keep metadata role/level at exactly ${c.role}/${c.level}. Bump semiskill-version to 1.1.0.
${VERIFY}

Report the pack-level consistency line for your slug in 'consistency_line'.`,
    { label: `fix:${c.slug}`, phase: 'Fix', schema: FIX_SCHEMA })
    .then(fix => ({ review, fix })),

  // 3. independent recheck — the publish gate
  (prev, c) => agent(`${RULES}

# YOUR TASK — independent recheck

You are a FRESH reviewer. You did not write this skill, you did not fix it, and you have not seen the
fixer's reasoning — deliberately. Earlier rounds of this project were rechecked by the lineage that
produced the fix, and each shipped a new bug.

Read ${REPO}\\skills\\${c.slug}\\SKILL.md as it stands now, plus the _shared/ files.

Answer strictly:
 1. Is the skill technically correct about the DV domain? Quote anything still wrong.
 2. Does every step fit the skill's own retrieval budget, with the budget accounting for every Grep?
 3. Is anything asserted the author could not know and that is not a [[FILL:]] slot?
 4. Is every declared slot actually spent by a step?
 5. Does every value the handoff block offers have a step that assigns it, and does the block agree
    with _shared/handoff-vocabulary.md?
 6. Are metadata role/level exactly ${c.role}/${c.level}?
 7. Run from ${REPO}: \`python -m semiskill.cli lint skills/${c.slug}\` — confirm 1.000 and clean.
 8. **Would you hand this to a working DV engineer today?** "Nearly" is a no.

Set ready:true only if you would. Do NOT edit any file.`,
    { label: `recheck:${c.slug}`, phase: 'Recheck', schema: RECHECK_SCHEMA })
    .then(rc => ({ slug: c.slug, role: c.role, level: c.level, ...prev, recheck: rc })),
)

const ok = results.filter(Boolean)
const ready = ok.filter(r => r.recheck && r.recheck.ready)
log(`Batch ${BATCH}: ${ready.length}/${ok.length} recheck-ready`)

return {
  batch: BATCH,
  attempted: CELLS.length,
  completed: ok.length,
  ready: ready.map(r => r.slug),
  not_ready: ok.filter(r => !(r.recheck && r.recheck.ready))
              .map(r => ({ slug: r.slug, remaining: (r.recheck && r.recheck.remaining) || [] })),
}
