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
# What a skill in this pack is

A single Markdown procedure a DV engineer's agent loads and follows. The reader is a working
verification engineer at an EDA-and-IP company. The agent that will execute it has ONLY Read, Grep
and Glob over text files already on disk.

# Standing rules — all of these are checked, most of them mechanically

1. **Verb honesty.** The agent cannot run VCS, Verdi, URG, a formal engine, an emulator, or submit to
   a compute farm. Every step is an analysis or authoring verb (read, locate, classify, rank, draft,
   cross-check) OR an explicit handoff: "ask the engineer to run X and give you the path to the
   output". Never write a bare Run/Execute/Merge/Compute as something the agent performs. This is the
   single most common way a skill like this becomes shelfware.
2. **No proprietary lookup.** You do not know their tool flags, message strings, house conventions,
   VIP knob names, or licensed spec text — and you must not pretend to. Every such fact is a
   \`[[FILL: ...]]\` slot. A skill whose value depends on a fact you invented is worse than no skill.
3. **Retrieval budget that the procedure obeys.** DV artifacts are enormous — 100MB+ logs, filelists
   with thousands of entries. State an explicit bounded budget (Grep first to locate, then bounded
   windowed Reads, with a stopping rule), then make sure NO step exceeds it and the budget accounts
   for every Grep the steps actually spend. A step that cannot be carried out inside the skill's own
   caps is broken.
4. **Markers must be slots.** If a step Greps for a "fatal marker" or "pass marker", the slot table
   must declare it. Never Grep for something the engineer was never asked to define.
5. **Every slot must be spent.** A slot the procedure never consumes sends the reader to interrupt a
   colleague for nothing. Drop it or use it. (Machine-checked: rule C001.)
6. **Logs are files on disk.** Grep and Read cannot search text pasted into a chat. If the
   description advertises the pasted-in case, step 1 must resolve it to a path first, or say plainly
   what cannot be done and mark the result provisional.
7. **State your own coverage.** If the procedure stops early under its budget, the output says how
   much it actually covered. An unstated shortcut is far worse than a stated one.
8. **Pack-wide facts live in \`_shared/team-profile.md\`** — log locations, fatal/pass/infra markers,
   run identity, known-issue list, area-to-owner map, sign-off, simulator, filelist convention.
   Reference them; do not re-ask them. If the skill needs something NARROWER than the profile
   records, say exactly how it is narrower. Never claim two differently-named facts are "the same
   fact" unless they genuinely are — that error propagated wrong marker strings across two skills.
9. **Signatures** come from \`_shared/failure-signature-schema.md\`. Use its field names and rules as
   written rather than re-deriving them.
10. **Handoff-block fields** follow \`_shared/handoff-vocabulary.md\` — the pack-wide field registry.
    Read it before touching a fenced report block. Registered fields carry a canonical enum; an
    unregistered field name must not collide with another skill's meaning for the same word.
11. Every skill ends with **"Human verification — what a wrong answer looks like"**.

# Mechanical constraints — any violation silently prevents publication

The skill is scanned by a security pipeline and must score exactly 1.000. These block it:
 - ANY url (\`http\` followed by \`://\`). Cite documents by name and clause instead.
 - The words curl, wget, urllib, requests.get, socket., fetch(, or "nc -".
 - Any word from {eval, exec, function} immediately followed by "(" — CASE INSENSITIVE. So
   "transfer function (H(s))" is fatal; write "transfer function H(s)".
 - "run the following command/script/shell/bash" — instant hard fail. Use the handoff phrasing.
 - "you are now a/an/the ..." — instant hard fail. Write "as the block owner, you ...".
 - "ignore ... previous/prior/above instructions", "disregard the above/previous/system".
 - The letters "exfiltrat" in any word. Write "unauthorised data egress".
 - "execute arbitrary code/commands".
 - A dotted quad like 10.2.1.4 (reads as a private IP). Write "v10.2 patch 1.4".
 - A NNN-NN-NNNN number (reads as a US SSN). Re-punctuate part numbers and clause numbers.
 - Four groups of four digits; a 200+ character unbroken alphanumeric run.
 - {token, secret, password, api_key, passwd, pwd} followed by ":" or "=" then 16+ characters, even
   as a fake placeholder. Use angle brackets: \`token: <your-token>\`.
 - "<<<" or ">>>" anywhere. A [[FILL:]] slot named after a credential.
 - Unquoted YAML values containing ": " or starting with @ \` % * & ! | > [ or {.

# Required frontmatter (ADR-008) — exactly these keys, nothing else at top level

\`\`\`
---
name: <the kebab folder name, identical to the directory>
description: <what it does>. Use when <concrete triggers in the engineer's own words>.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: <human title>
  semiskill-function: design-verification
  semiskill-role: <given below>
  semiskill-level: <given below>
  semiskill-owner: dv-guild
  semiskill-version: <bump>
  semiskill-review-by: <a date 6-14 months out; STAGGER it, do not reuse a sibling's>
  semiskill-tags: <comma separated>
---
\`\`\`

# Required body structure

1. \`# <Title>\` then two or three sentences framing what actually goes wrong.
2. \`## When to use something else\` — route to the sibling skills honestly.
3. \`## Fill this in for our team\` — a table of 5-10 \`[[FILL: ...]]\` slots with a "Who knows" column.
4. \`## Retrieval budget — read this before opening anything\` — numbered, with a stopping rule.
5. \`## Procedure\` — numbered \`### \` steps naming the tool in bold at each step.
6. \`## Gotchas\` — 6-10 bullets of hard-won specifics. **This is the most valuable section**; it is
   what actually transfers experience between people. Be concrete and technically correct.
7. \`## Human verification — what a wrong answer looks like\`
8. \`## Done when\` — one line.

Length 180-260 lines. Substantial, not padded.

# Golden references

${REPO}\\skills\\dv-sim-log-first-error\\SKILL.md  (voice, structure, density)
${REPO}\\skills\\dv-ral-bringup\\SKILL.md          (a decision-tree skill, reviewer-approved)
${REPO}\\skills\\_shared\\team-profile.md
${REPO}\\skills\\_shared\\failure-signature-schema.md
${REPO}\\skills\\_shared\\handoff-vocabulary.md
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
