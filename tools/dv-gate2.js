export const meta = {
  name: 'dv-content-gate-round-2',
  description: 'Close the findings an independent recheck left open, then recheck again with a calibrated blocking/non-blocking verdict',
  phases: [
    { title: 'Fix2', detail: 'close every remaining finding, or say why not' },
    { title: 'Recheck2', detail: 'fresh reviewer; ready:true iff nothing BLOCKING remains' },
  ],
}

const REPO = 'E:\\code\\VLSI\\semiskill'

const ARGS = typeof args === 'string' ? JSON.parse(args) : (args || {})
const CELLS = ARGS.cells || []
const BATCH = ARGS.batch != null ? ARGS.batch : '?'
if (!CELLS.length) {
  throw new Error('no cells passed to round 2 — refusing to report an empty batch as a success')
}

// The standing content rules. Round 2 assumes the author knows them; what it adds is the
// blocking/non-blocking distinction that round 1 lacked.
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

const FIX_SCHEMA = {
  type: 'object',
  required: ['slug', 'lint_line', 'clean', 'fixed', 'not_fixed'],
  properties: {
    slug: { type: 'string' }, lint_line: { type: 'string' }, clean: { type: 'boolean' },
    fixed: { type: 'array', items: { type: 'string' } },
    not_fixed: { type: 'array', items: { type: 'string' },
                 description: 'each with the REASON it was not fixed — disagreement is allowed, silence is not' },
  },
}

const RECHECK_SCHEMA = {
  type: 'object',
  required: ['slug', 'ready', 'why', 'blocking', 'non_blocking'],
  properties: {
    slug: { type: 'string' },
    ready: { type: 'boolean' },
    why: { type: 'string' },
    blocking: {
      type: 'array',
      description: 'findings that would make an engineer take a WRONG action, or that make a step impossible to carry out. ready must be false if this is non-empty.',
      items: { type: 'string' },
    },
    non_blocking: {
      type: 'array',
      description: 'real but non-misleading: narrower-than-ideal phrasing, a nit, a style point, an improvement. These do NOT block publication.',
      items: { type: 'string' },
    },
    remaining: { type: 'array', items: { type: 'string' } },
    new_problems: { type: 'array', items: { type: 'string' } },
  },
}

phase('Fix2')
log(`Round 2, batch ${BATCH}: ${CELLS.length} skills that failed their first independent recheck — ` +
    `each fixer reads its own REVIEW.json for the open findings`)

const results = await pipeline(
  CELLS,

  (c) => agent(`${RULES}

# YOUR TASK — close the findings an independent recheck left open on ${c.slug}

The skill is at ${REPO}\\skills\\${c.slug}\\SKILL.md. It was written, reviewed once, fixed once, and
then a FRESH reviewer who had not seen the fixer's reasoning rejected it.

**First, read the gate record: ${REPO}\\skills\\${c.slug}\\REVIEW.json.** Its \`recheck\` object holds
the findings that reviewer left open (under \`remaining\`, \`blocking\`, \`remaining_nits\` and/or
\`new_problems\` — read all of them), and \`review\` and \`fix\` record what the earlier round already
found and changed, so you do not undo a deliberate decision. THEN read SKILL.md in full, then close
the findings.

How to work:
- Anything the reviewer marked BLOCKER, or that makes a step impossible to carry out inside the
  skill's own retrieval budget, or that is technically WRONG about the DV domain, is not optional.
- Fix each so the claim becomes CORRECT, not so it becomes unfalsifiable. Widening a sentence until
  it can no longer be checked is the failure mode the next reviewer is specifically told to look for.
- Items the reviewer labelled "Nit" are still worth closing when the fix is a phrase. Where a nit
  would cost structure you need, say so in not_fixed with the reason.
- If you believe a finding is simply WRONG, say so in not_fixed with your reasoning and evidence.
  A reviewer being mistaken is a real outcome; pretending to fix it is not.
- If the budget genuinely cannot cover the procedure, CHANGE THE BUDGET and say you did — the budget
  is a claim about the skill, not a constraint handed down from outside.

Keep metadata role/level at exactly ${c.role}/${c.level}. Bump semiskill-version to 1.2.0.

## Verify before you finish — MANDATORY, from ${REPO}

    python -m semiskill.cli lint skills/${c.slug}

Must print \`[approve 1.000]\` and \`clean\` with ZERO findings. Then confirm the pack still has no
consistency ERROR naming your slug:

    python -c "from semiskill.authoring.consistency import check_pack; [print(f.rule,f.level,f.slug,f.message[:120]) for f in check_pack('skills') if '${c.slug}' in f.slug]"

Edit ONLY ${REPO}\\skills\\${c.slug}\\. Never touch sibling skills, _shared/, or the linter — other
agents own those and are editing concurrently.`,
    { label: `fix2:${c.slug}`, phase: 'Fix2', schema: FIX_SCHEMA }),

  (fix, c) => agent(`${RULES}

# YOUR TASK — independent recheck, round 2

You are a FRESH reviewer. You did not write this skill, you did not fix it, and you have deliberately
not seen the fixer's reasoning. Earlier rounds of this project were rechecked by the lineage that
produced the fix, and every one of those shipped a new bug.

Read ${REPO}\\skills\\${c.slug}\\SKILL.md as it stands now, plus \`_shared/team-profile.md\`,
\`_shared/failure-signature-schema.md\` and \`_shared/handoff-vocabulary.md\`.

## The judgement you are making

This skill is for a real DV engineer at a real company. The question is NOT "is this perfect" — it is
**"would this help a competent engineer do this task, and could any part of it lead them astray?"**

Sort everything you find into exactly two buckets, and be honest about which is which:

**BLOCKING** — it would make an engineer take a WRONG action, or a step cannot be carried out at all:
  - technically wrong or misleading about the DV domain
  - a step that cannot run inside the skill's own stated retrieval budget, or a Grep/Read the budget
    never accounts for
  - a specific flag, message string, default or convention the author could not have known, asserted
    as fact rather than declared as a [[FILL:]] slot
  - a declared slot no step spends, or a handoff value no step assigns
  - a claim about a sibling skill, a shared file, or the pack that is not true
  - metadata role/level not exactly ${c.role}/${c.level}

**NON-BLOCKING** — real, but it would not mislead anyone: a narrower-than-ideal phrasing, a
stylistic point, a "could also mention", a date collision, an improvement you would make yourself.

Do not inflate a nit into a blocker to look rigorous, and do not demote a real defect to look
generous. A pack that never ships helps nobody; a pack that ships a wrong instruction is worse than
no pack.

Also run, from ${REPO}:
    python -m semiskill.cli lint skills/${c.slug}
and confirm it prints 1.000 and clean.

**Set ready:true if and only if the BLOCKING list is empty.** Do NOT edit any file.`,
    { label: `recheck2:${c.slug}`, phase: 'Recheck2', schema: RECHECK_SCHEMA })
    .then(rc => ({ slug: c.slug, role: c.role, level: c.level, fix: fix, recheck: rc })),
)

const ok = results.filter(Boolean)
const ready = ok.filter(r => r.recheck && r.recheck.ready)
log(`Round 2, batch ${BATCH}: ${ready.length}/${ok.length} now recheck-ready`)

return {
  batch: BATCH,
  round: 2,
  attempted: CELLS.length,
  completed: ok.length,
  ready: ready.map(r => r.slug),
  not_ready: ok.filter(r => !(r.recheck && r.recheck.ready))
              .map(r => ({ slug: r.slug, blocking: (r.recheck && r.recheck.blocking) || [] })),
}
