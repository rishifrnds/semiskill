# Handoff field vocabulary

A handoff field name is the **consumer's join key**. Blocks from different skills get pasted into one
table and compared by exact token, so a field name is a promise about the value space — not a label
for a column. Same name must mean same values; same values need not mean same name.

Read this before naming an enum-valued field. It is bounded on purpose: 7 registered enums, 5
spelling locks, 19 held nouns. Your obligation is one question, not a survey of 83 siblings: *is the
field I am about to write one of these?* If yes, copy the values verbatim. If no, the name is yours,
subject to the held-noun rule below.

**Measured on the pack as it stands** (re-measure before quoting these — a census that has drifted is
worse than none, because every other claim here checks out and a reader has no reason to doubt it):
675 distinct field names across 84 skills, of which **160 are enum-valued and 153 of those appear in
exactly one skill**. Local-by-default is the healthy state, not a gap. The seven enum names that do
appear in more than one skill are *exactly* the seven registered below — after the ADR-011 rename
wave there is no longer a single unregistered shared enum in the pack.

This file is also read by `semiskill/authoring/consistency.py`, which is **fail-closed** about it: a
missing file, an unparseable row, an unknown keyword, a value that is not a lowercase token, a
narrowing that is not a proper subset, or a holder slug with no `SKILL.md` all raise rather than
degrade. A silently-empty registry is the worst available failure mode — it would turn C006 into
sixteen errors on files that are already correct and C003 into zero on the one file that is wrong.

## When two skills may share a field name

All three must hold — the **one-column test**:

1. **Same question, same object** — not a similar-sounding question about a different object.
2. **Reconcilable values** — one canonical set in which no token means something different on either
   side, so an equality test between two pasted blocks is meaningful.
3. **Live routing path** — a skill routes a finding to the other, so the comparison happens.

Operationally: *could a consumer pour rows from both skills into one column and sort, count and
filter them together?* If yes, register the field here — registration commits all 83 skills and arms
the checker against any that disagree, so it carries the same sign-off as publishing.

If any condition fails, **the two skills must not share the name**. A shared name with unshared
values is worse than two distinct names, because a reader who sees the same label assumes the tokens
are commensurable. Never union two unrelated enums under one name to silence a collision: it makes
both enums wider than either skill can produce and still forces consumers to know which skill a row
came from. Only **token-list values** are governed here: a name used as an enum in one skill and as
free text in another cannot mismatch — `window` is an enum in two skills and a plain time window in
six.

## T1 — REGISTERED

Every user of these names emits a subset of the canonical set. `narrowing` is `declared` where a
proper subset is legal and must be declared; `no` where the full set is load-bearing.

| field | values | narrowing | meaning |
|---|---|---|---|
| `class` | `design` `infrastructure` `unknown` | no | Which side of the design/infrastructure line a finding lands on — the coarse routing decision, used by 44 skills. `unknown` is the honesty escape hatch and may not be dropped; without it the reader has to guess. Skills state their local mapping in prose (a substituted model is `infrastructure`, however much it feels like a design bug). |
| `phase` | `compile` `elab` `run` `finalise` `post` | declared | When it broke. This is the phase token of `_shared/failure-signature-schema.md` — that file is the authority, cited not restated, so a phase column joins against a signature prefix. |
| `proof status` | `proven` `falsified` `bounded` `inconclusive` `vacuous` `not-read` | declared | What the formal engine concluded about one property run; the spellings are the tool-report words. `not-read` is a *reading* status, not an engine outcome — exclude it from proof-outcome denominators rather than counting it as a failure to prove. |
| `action` | `fix-rtl` `fix-setup` `waive` `needs-a-human` | no | What to do with a triaged static-analysis violation. Shared by the deliberate siblings dv-lint-triage and dv-cdc-rdc-triage. |
| `fired` | `confirmed` `not-confirmed` `not-run` | no | Whether the authored checker was observed to fire on the stimulus written to provoke it. |
| `strength` | `shall` `shall-not` `should` `may` `reserved` | no | The normative force the specification gives the statement a checker or test is built from. |
| `window` | `same-cycle` `next-cycle` `within-n` `bounded-eventually` | no | The temporal scope a property or checker rule asserts over. |

Normalise older blocks pasted into trackers: in `proof status`, **full** = `proven` and
**counterexample** = `falsified`. One vocabulary wearing two spellings.

`action`, `fired`, `strength` and `window` are registered because they *already agree* in the two
skills that carry them. That registration is mandatory rather than optional: without those four rows
the shared-name rule invents an error on four files that are already correct.

## T2 — NARROWINGS

A **proper subset** of a canonical set is legal where T1 says `declared`, and must be declared —
either as a row here, or as an inline reason on the value line:
`phase : run — a trap is always a run-phase failure`. Subsets are lenient and disjoint sets fatal
because a subset is safe for **joins** (every token still means the same thing) but unsafe for
**denominators**: "0 of 12 finalise-phase failures" is meaningless if half the contributing skills
structurally cannot emit `finalise`. The declaration warns the consumer about the denominator. Where
narrowing is `no`, dropping a token is an error.

| field | skill | values |
|---|---|---|
| `phase` | `dv-build-filelist-hygiene` | `compile` `elab` |
| `phase` | `dv-isa-step-compare` | `run` `post` |
| `phase` | `dv-trap-exception-triage` | `run` |
| `proof status` | `dv-formal-apps` | `proven` `falsified` `bounded` `inconclusive` `vacuous` |
| `proof status` | `dv-formal-overconstraint-credit` | `proven` `falsified` `bounded` `inconclusive` `not-read` |

dv-formal-apps drops `not-read` — it always reads the result. dv-formal-overconstraint-credit drops
`vacuous`, which it reports through its own dedicated vacuity field; two vacuity verdicts in one
block is the drift this file exists to prevent.

## T3 — HELD / SHAPE

`shape` — the spelling is locked, there is no enum, and the name may not be reused for anything else.

`held` — a bare generic noun reads as a universal column. Each is registered above, held by one
skill, or must be **qualified with the axis it classifies** — `match key`, `card result`,
`input parity`, `req chain`. This is the rule that prevents the *next* collision rather than
repairing the last one, and it costs one rename while you are already choosing the name. A holder of
`-` means the noun is reserved and unclaimed: qualify it before use.

`retired` — the name was a field of that skill and is not any more. Each held noun was taken back
from a second skill that used it for a different axis, so prose left behind is stale; the note
carries the values the field used to offer, which is how a sentence naming one of them is still
found.

| name | kind | holder | note |
|---|---|---|---|
| `signature` | shape | - | Per `_shared/failure-signature-schema.md`: phase, kind, where, what, in that order. The pack's most load-bearing join key — the thing that stops two engineers debugging the same bug twice. Never "sig", never "failure signature". |
| `run id` | shape | - | Whatever identifies one run for this team, per the profile's **Run identity** fact. Not run-id, not runid, not run. |
| `owner` | shape | - | The name from the profile's area-to-owner map, or blank plus candidates. Blank is a question; invented is a wrong answer that looks right. |
| `evidence` | shape | - | A file path and line for every claim in the block above it. |
| `notes` | shape | - | Anything the next person would otherwise rediscover. Always last in the block. |
| `chain` | held | - | Reserved and unclaimed: two skills reached for it to mean two different traceability chains. |
| `checked` | held | `dv-security-negative-tests` | What the negative test was checked against. |
| `closure` | held | `dv-escape-analysis` | How an escape was closed. |
| `culprit` | held | `dv-isa-step-compare` | Which of model, RTL or environment produced the divergence. |
| `disposition` | held | `dv-tool-bug-testcase-extraction` | What the vendor did with the extracted testcase. |
| `divergence` | held | - | Reserved and unclaimed: two skills reached for it to classify two different kinds of difference. |
| `inputs` | held | `dv-coverage-merge-report` | What went into the merge. |
| `kind` | held | - | Reserved: it is already the second token of the shared failure signature. |
| `match` | held | `dv-rnm-authoring-correlation` | Whether the real-number model tracked the analog reference. |
| `mechanism` | held | `dv-ams-view-binding-audit` | Which binding mechanism selected the view. |
| `mode` | held | - | Reserved. |
| `outcome` | held | `dv-release-gate` | Whether the gate let the release through. |
| `reason` | held | `dv-coverage-merge-report` | Why a run was excluded from the merge. |
| `result` | held | - | Reserved. |
| `ruling` | held | `dv-cross-tool-mismatch-adjudication` | Which side of a two-tool disagreement the standard supports. |
| `state` | held | `dv-waiver-corpus-audit` | The lifecycle state of a waiver. |
| `status` | held | `dv-error-injection-ras` | Whether the injected error was reported, corrected or missed. |
| `type` | held | - | Reserved. |
| `verdict` | held | `dv-regression-triage-routing` | Where a triaged regression failure was routed. |
| `chain` | retired | `dv-safety-req-trace-audit` | now `req chain`; was `broken` `full` `plan-only` `test-only` `waived` |
| `chain` | retired | `dv-testplan-traceability-review` | now `plan chain`; was `complete` `no-checker` `no-cov-item` `no-test` `unresolved` |
| `checked` | retired | `dv-spec-feature-extract` | now `checked against`; was `errata` `neither` `not-readable` `prior-revision` |
| `culprit` | retired | `dv-mem-timing-check-triage` | now `timing source`; was `clock-period` `controller-schedule` `mode-register` `model-config` `tb-init` `unresolved` |
| `disposition` | retired | `dv-undetected-fault-closure` | now `fault verdict`; was `mechanism-gap` `observation-gap` `safe-candidate` `stimulus-gap` `undecided` |
| `divergence` | retired | `dv-ams-view-binding-audit` | now `view match`; was `matches` `not-in-matrix` `not-in-report` `unresolved` `wrong-view` |
| `divergence` | retired | `dv-emulation-sim-mismatch-triage` | now `divergence class`; was `model-difference` `transformed-construct` `two-state` `uninit-state` `zero-delay-race` |
| `inputs` | retired | `dv-tool-release-behaviour-diff` | now `input parity`; was `differ` `same` `unknown` |
| `match` | retired | `dv-waiver-corpus-audit` | now `match key`; was `file-line` `object` `signature` |
| `mechanism` | retired | `dv-signal-trace-localisation` | now `localised as`; was `control` `data` `not-localised` `sampling` `undriven` `x-source` |
| `ruling` | retired | `dv-tool-feature-testplan` | now `card result`; was `as-expected` `disagrees` `known-deviation` `not-yet-run` `test-defect` |

## Naming a new field

- **Space-separated, not hyphenated** — `plan call`, `bin class`, `fix kind`, `reported as`, `case
  key`. Hyphens inside a single token (`fix-rtl`, `not-read`) stay.
- **The field name is everything left of the first colon, trimmed.** Consumers compare it whole and
  must not prefix-match: `match` and `match key` are different fields. Spelling separators are the
  one thing normalised: `proof status`, `proof-status` and `proof_status` are one field.
- **No slug namespacing.** `ams-view-binding-audit-divergence` widens every column for eight fields.
- **Retired senses stay retired.** If you touch one, grep the body for the old bare word, prose
  included — a renamed field leaves references behind that no value-level rule can see.

Value-level synonym drift *across different fields* is deliberately unpoliced: the pack spells its
escape hatch `unknown`, `unresolved`, `undecided`, `not-checked`, `not-read` and `not-yet-run` in
different skills, and many of those distinctions are real. `strength` and dv-tool-feature-testplan's
`force` are a genuine synonym field — same question, same object, two names, four shared tokens; the
checker surfaces it, and reconciling it is a follow-up ADR rather than this one.
