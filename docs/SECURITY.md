# SemiSkill — Security Model

Security is the reason this project exists. Every control is structural (enforced by the database, the
type system, or a gate), not by prompting. Treat every submitted skill body as an untrusted injection
payload.

## Invariants (enforced structurally, proven by tests)
1. **Verification-gated publishing.** A skill advances `submitted → scanned → reviewed → approved →
   published`. The catalog is derived from a *positive, published `approval` artifact*, which only the
   gated actuator writes. `spine/lifecycle.derive_state` returns `PUBLISHED`/`APPROVED` only when such
   an approval exists. *(tests: `test_lifecycle`, `test_publish`, `test_migration_0003`.)*
2. **Submitters cannot forge verification.** The `semiskill_submitter` DB role may insert only
   `skill_version` / `comment` / `rating` / `reuse_event` (BEFORE-INSERT trigger). It structurally
   cannot create `scan_run` / `injection_test` / `review` / `approval`. *(migration 0003.)*
3. **Held-out corpus + gold-set are unreadable by the pipeline.** `injection_corpus` and
   `judge_gold_set` are behind the `semiskill_pipeline` role, which has `REVOKE ALL` on both and may
   only `EXECUTE` a SECURITY DEFINER probe that returns counts + failing class names — never the
   patterns or human labels. *(migration 0004; `test_migration_0004`, red-team `corpus_readable`.)*
4. **Append-only artifacts.** UPDATE/DELETE are blocked by a trigger; corrections are new rows via
   `corrects_ref`. Rollback/unpublish is a new correcting artifact, never a mutation.
5. **ACL at query traversal.** Reads go only through SECURITY DEFINER functions under the restricted
   `semiskill_app` role (which cannot SELECT `artifacts`); every function filters by
   `permissions_label` and pins `search_path`. A `need-to-know` skill is invisible to an unauthorized
   querier. *(test: `test_retrieve`, `test_acl`.)*

## Restricted database roles
| Role | May | May not |
|------|-----|---------|
| `semiskill_app` | EXECUTE the read/provenance functions | SELECT `artifacts` directly |
| `semiskill_submitter` | INSERT submission/interaction artifacts | INSERT verification/approval artifacts |
| `semiskill_pipeline` | EXECUTE the corpus probe | SELECT `injection_corpus` / `judge_gold_set` |

## The pipeline (L4/L6)
Six stages, each writing a `scan_run` (or `injection_test`) artifact with a safety score + `hard_fail`:
static structure, security-audit, injection corpus, secret/PII, calibrated LLM-judge, aggregate
verdict. A `hard_fail` short-circuits — no review, never publishable. The LLM-judge is **advisory**
(never hard-fails) and **fail-closed on trust**: uncalibrated / drifted (κ < 0.6) / same-model-family
judges are skipped visibly; a real verdict only counts when Cohen's κ ≥ 0.6 against the held-out
gold-set. Drift blocks the L5 controller from auto-acting.

## Rule of Two / dual-LLM
The controller may hold untrusted input + sensitive store, but **never autonomous external action** —
the human publish gate is the safety property. Retrieved content is wrapped as UNTRUSTED
(`context/untrusted.delimit`) and never executed as instructions.

## Egress & redaction
Egress is **deny-by-default** — no pipeline agent has open internet or write access beyond its
explicit actuator. Stage-2's `npx` and any external judge run only inside the egress-controlled
sandbox with a pinned registry. NUL bytes in untrusted submissions are sanitized at the L1 boundary
(a jsonb-store DoS). Secret/PII detection (stage 4) flags credentials before a skill can be approved.

## Rollback drill
`governance/rollback.unpublish_skill` appends a correcting `approval` (published=false, quarantined)
via `corrects_ref`; the catalog (active-approval-wins) drops the skill immediately, with a
ReversalProof-style `rollback_ref`. *(test: `test_unpublish_removes_from_catalog`.)*

## Calibration
`governance/report.calibration_report` reports the judge κ series, latest κ vs the 0.6 gate, and drift
status. Recalibrate on schedule and after any rubric/judge-model change.
