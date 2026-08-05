export const meta = {
  name: 'dv-authoring-wave',
  description: 'Author one role-wave of DV skills through the full gate: author, lint, adversarial review, fix, independent recheck',
  phases: [
    { title: 'Author', detail: 'one agent per cell, iterating against the linter until 1.000' },
    { title: 'Review', detail: 'adversarial review per skill' },
    { title: 'Fix', detail: 'close the findings' },
    { title: 'Recheck', detail: 'a fresh reviewer per skill; ready:true is the publish gate' },
  ],
}

const REPO = 'E:\\code\\VLSI\\semiskill'

// args can arrive as an object or as a JSON string depending on how it was passed. Silently
// producing an empty wave is the worst failure here — it looks like success — so parse both and
// throw loudly if there is nothing to do.
const ARGS = typeof args === 'string' ? JSON.parse(args) : (args || {})
const CELLS = ARGS.cells || []
const WAVE = ARGS.wave != null ? ARGS.wave : '?'
if (!CELLS.length) {
  throw new Error('no cells passed to the wave — refusing to report an empty wave as a success')
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
the pack-level check across every skill — it must not report a C003 or C004 **error**. Iterate until
both hold. The linter prints the exact line and a fix for every finding.

Edit ONLY your own skill directory. Never modify the linter, the scanners, sibling skills or _shared/.
`

const AUTHOR_SCHEMA = {
  type: 'object',
  required: ['slug', 'lint_line', 'clean', 'slots', 'uncertainties'],
  properties: {
    slug: { type: 'string' }, lint_line: { type: 'string' }, clean: { type: 'boolean' },
    slots: { type: 'integer' }, lines: { type: 'integer' },
    uncertainties: { type: 'array', items: { type: 'string' },
                     description: 'technical points you were not certain of — be honest, a flagged uncertainty is far more useful than a confident invention' },
  },
}

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

phase('Author')
log(`Wave ${WAVE}: ${CELLS.length} skills through author -> review -> fix -> independent recheck`)

const results = await pipeline(
  CELLS,

  // 1. author
  c => agent(`${RULES}

# YOUR SKILL — write it

directory and name: ${c.slug}
semiskill-role:     ${c.role}
semiskill-level:    ${c.level}
semiskill-title:    ${c.title}

What it must teach:
${c.one_line}

${c.notes ? `Additional context from the catalog design:\n${c.notes}\n` : ''}
Write ${REPO}\\skills\\${c.slug}\\SKILL.md.
${VERIFY}

Return the slug, the final lint line, the slot count, the line count, and — honestly — any technical
point you were not certain about. A flagged uncertainty is far more useful to the reviewer than a
confident invention.`,
    { label: `author:${c.slug}`, phase: 'Author', schema: AUTHOR_SCHEMA }),

  // 2. adversarial review
  (authored, c) => agent(`${RULES}

# YOUR TASK — adversarially review one skill

Read ${REPO}\\skills\\${c.slug}\\SKILL.md in full, plus the two _shared/ files and the golden
reference, and attack it. Default to finding problems: a clean review of a first draft is almost
certainly a failed review.

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
 6. **Would a busy DV engineer open it twice?** Answer honestly.

Do NOT edit any file. Report only.`,
    { label: `review:${c.slug}`, phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'feature-dev:code-reviewer' })
    .then(review => ({ authored, review })),

  // 3. fix
  (prev, c) => agent(`${RULES}

# YOUR TASK — close the review findings on ${c.slug}

The skill is at ${REPO}\\skills\\${c.slug}\\SKILL.md. Here is the review:

${JSON.stringify(prev.review, null, 1).slice(0, 30000)}

Everything under must_fix, technical_errors, verb_honesty and budget_violations is not optional. Fix
each so the claim becomes CORRECT, not so it becomes unfalsifiable — the next reviewer checks for
exactly that. Anything you deliberately do not fix, say why.

Keep metadata role/level at ${c.role}/${c.level}. Bump semiskill-version to 1.1.0.
${VERIFY}`,
    { label: `fix:${c.slug}`, phase: 'Fix', schema: FIX_SCHEMA })
    .then(fix => ({ ...prev, fix })),

  // 4. independent recheck — the publish gate
  (prev, c) => agent(`${RULES}

# YOUR TASK — independent recheck

You are a FRESH reviewer. You did not write this skill, you did not fix it, and you have not seen the
fixer's reasoning — deliberately. Earlier rounds of this project were rechecked by the lineage that
produced the fix and each shipped a new bug.

Read ${REPO}\\skills\\${c.slug}\\SKILL.md as it stands now, plus the two _shared/ files.

Answer strictly:
 1. Is the skill technically correct about the DV domain? Quote anything still wrong.
 2. Does every step fit the skill's own retrieval budget, with the budget accounting for every Grep?
 3. Is anything asserted the author could not know and that is not a [[FILL:]] slot?
 4. Is every declared slot actually spent by a step?
 5. Does the handoff block (if any) agree with the sibling skills that share its field names?
 6. Are metadata role/level exactly ${c.role}/${c.level}?
 7. **Would you hand this to a working DV engineer today?** "Nearly" is a no.

Set ready:true only if you would. Do NOT edit any file.`,
    { label: `recheck:${c.slug}`, phase: 'Recheck', schema: RECHECK_SCHEMA })
    .then(rc => ({ slug: c.slug, role: c.role, level: c.level, ...prev, recheck: rc })),
)

const ok = results.filter(Boolean)
const ready = ok.filter(r => r.recheck && r.recheck.ready)
log(`Wave ${WAVE}: ${ready.length}/${ok.length} recheck-ready`)

return {
  wave: WAVE,
  results: ok,
  ready: ready.map(r => r.slug),
  not_ready: ok.filter(r => !(r.recheck && r.recheck.ready))
              .map(r => ({ slug: r.slug, remaining: (r.recheck && r.recheck.remaining) || [] })),
}
