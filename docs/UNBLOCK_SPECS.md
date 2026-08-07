# Unblock specs — what stands between 84 authored and 84 published

Measured on 2026-08-07 against commit `c8f5fa3`, dev database `semiskill`.

## State after this session's live fixes

| Funnel stage | Count |
|---|---|
| authored | 84 |
| strict_lint_pass | 84 |
| **security_pass** | **0** ← SPEC A |
| reviewed | 0 ← SPEC B |
| recheck_ready | 0 ← SPEC B |
| approved | 0 |
| published | 0 |

**Already fixed live, no spec needed:**
- The dev catalog DB sat at migration `0015` while `0016–0023` shipped, so
  `verified_review_contract_ids_v1()` did not exist and `scoreboard --strict-gate` crashed.
  Forward migration `0015 → 0023` planned, reviewed and executed. Scoreboard now runs.
- The wave had never been run against the pack. All 84 skills are now captured and scanned;
  every one produced `skill_version` + 6 scan artifacts and `awaiting-review`.

Undocumented prerequisites for `migrate-forward`, recorded because they cost real time:
`SEMISKILL_MIGRATOR_ROLE` (must equal session user *and* database owner),
`SEMISKILL_DEVELOPMENT_DATABASE_NAME` and `SEMISKILL_PRODUCTION_DATABASE_NAME` (both set, different),
a clean git tree, and a plan whose `source_commit` matches `HEAD` — so write the plan **outside** the
repo, or committing it invalidates it.

---

# SPEC A — Resolve the judge policy (the structural publish blocker)

## The defect

All 84 skills are `security_blocked` with a single blocker code `SECURITY_BLOCKED`. Every stage that
ran scored 1.000 and the aggregate verdict is `approve`. The block comes from one contradiction:

- `semiskill/spine/pipeline.py::run_pipeline` takes `judge_required: bool = True`, and when
  `judge_risk_scanner is None` it writes a stage-5 artifact with status `not_sampled`
  (correctly — "a skipped judge is never rendered as a pass").
- `semiskill/authoring/snapshot.py` line ~642: `elif judge_required and (judge is None or
  judge["status"] != "passed"): errors.append("REQUIRED_JUDGE_NOT_PASSED")`.

The wave passes no judge scanner. Policy demands a passed judge. **No skill can ever reach
`security_pass` in this environment.** This is the exact failure class in `docs/LEARNINGS.md`:
*"when two rules can both be satisfied only by violating the other, one of them is scoped wrong."*

Note the code already anticipates the resolution — the very next branch accepts `not_sampled` when
the judge is not required:
`elif not judge_required and judge is not None and judge["status"] not in {"passed","not_sampled"}`.

## What to build

Make `judge_required` an explicit, per-skill, recorded **policy decision** rather than a hard-coded
default, and make the unsatisfiable combination impossible to reach silently.

1. **Source of truth.** `judge_required` is already projected per skill from the database registry
   (`store.py` ~line 528 selects it alongside `slug, role, level, permissions_label, active`).
   Determine how a row's value is set today and make it settable deliberately. Do **not** add a
   global override flag — a single switch that turns the judge off for everything is precisely the
   control that gets left on.
2. **The policy rule.** Propose and implement one defensible rule, and write the reasoning into
   `DECISIONS.md` as a new ADR. A defensible starting point, which you may argue against:
   *a judge is required for `regulated` and `need-to-know` permission labels, and for any skill
   whose declared `allowed-tools` exceed Read/Grep/Glob; it is not required for a `public`,
   read-only DV procedure in the `development` environment.* Whatever you choose, the rule must be
   stated in terms of risk, not convenience.
3. **Fail loudly on the impossible combination.** If `judge_required` is true and no judge scanner
   is configured, the **wave must refuse the skill up front** with a clear message naming the
   missing scanner — not scan it, write six artifacts, and let the scoreboard report
   `SECURITY_BLOCKED` a step later. A pipeline that produces evidence it knows cannot satisfy the
   gate is wasting work and hiding the cause.
4. **Re-run**: after the change, `scoreboard --snapshot-out` must show `security_pass: 84` with the
   stage-5 artifacts still honestly recorded as `not_sampled`. Never rewrite a `not_sampled` into a
   `passed`.

## Hard constraints

- Do **not** weaken any other stage, and do not make `not_sampled` look like a pass anywhere.
- Do **not** touch `skills/` content.
- The change must be visible in the snapshot: a reader must be able to see that these skills
  published **without** a judge, and why that was permitted.
- Add tests: judge required + no scanner → wave refuses; judge not required + `not_sampled` →
  `security_pass`; judge required + judge passed → `security_pass`; judge required + judge failed →
  blocked.

## Acceptance

`python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json
--snapshot-out reports/scoreboard.json --environment development` reports `security_pass: 84`,
`blocked.scan: 0`, full suite green, and a new ADR records the policy.

---

# SPEC B — Build the missing batch orchestrator

## The defect

`tools/gate_args.py` was retired with the message:
> *"Use a validated scoreboard snapshot and an orchestrator-issued exact batch contract as
> documented in docs/WORKFLOW.md."*

That orchestrator does not exist. `tools/collect_wave.py` is written to **consume** contracts
(`--contract a.json --contract b.json --results p5.json`) and `docs/WORKFLOW.md` describes them, but
nothing produces them. Both `tools/dv-gate.js` and `tools/dv-gate2.js` depended on the retired
driver, so **the content gate cannot currently be run at all**. This is the single reason
`reviewed = 0`.

## The exact contract to produce

`collect_wave.py::_validate` (read it — it is the specification, and it is strict: `set(contract)`
must **equal** the required set, no extra keys):

```
required root keys, exactly:
  schema_version        == "semiskill.review-batch/v1"
  contract_artifact_id  UUID of a GATE_DECISION artifact that already exists in the store
  batch_id              non-empty str
  run_id                non-empty str
  phase                 "review" | "recheck"
  prompt_version        non-empty str   (e.g. "P1-ADVERSARIAL-REVIEW@3" / "P5-RECHECK-CALIBRATED@3")
  attempt               int >= 1
  issuer_identity       non-empty str
  authentication_context  non-empty dict
  cells                 list of EXACTLY ONE cell

required cell keys, exactly:
  slug, skill_version_id, skill_payload_sha256, version, role, level,
  reviewer_identity, fixer_identity, lineage_id, prior_review_ref, checks
```

Two constraints that dictate the implementation order:

- `store.get(contract_artifact_id)` must return a `GATE_DECISION` artifact whose **payload equals
  the contract minus `contract_artifact_id`**. So: build the contract body → append the artifact →
  then write the JSON file with the returned ID added. Any other order fails validation.
- `skill_payload_sha256` must equal `payload_fingerprint(artifact.payload)` for the named
  `skill_version_id`, and `artifact.payload["slug"]` must equal the cell's `slug`.

## What to build

`tools/issue_batch.py` (or a `semiskill issue-batch` subcommand — pick one and say why):

```
python tools/issue_batch.py --snapshot reports/scoreboard.json --phase review \
    --prompt-version P1-ADVERSARIAL-REVIEW@3 --size 10 --out-dir reports/contracts/<batch-id>/
```

1. **Read the snapshot and verify it.** Refuse a snapshot that is stale, source-mismatched or
   database-mismatched — `snapshot_id`, `sources` and `scope` are all in the JSON for this purpose.
   A contract minted from a stale snapshot leases a payload that may no longer exist.
2. **Select eligible cells deterministically.** For `--phase review`: cells whose
   `checks.content_review.status` is `unreviewed` and which are not blocked. For `--phase recheck`:
   cells with open findings from a prior review. Selection must be a pure function of the snapshot
   — same snapshot in, same batch out.
3. **Bind exact identity per cell** from the snapshot's `artifacts.skill_version_id` and
   `payload_hashes`, plus `role`/`level` from the registry. Never re-derive a hash by reading
   `skills/` — the lease must name what was *scanned*, not what is on disk now.
4. **Append the GATE_DECISION artifact, then write one JSON file per skill.** Max 10 per batch
   (`MAX_BATCH_SIZE` in the collector).
5. **Emit the worker prompt alongside each contract**, rendered from `docs/PROMPT_LIBRARY.md` with
   every `{{PLACEHOLDER}}` substituted. An unresolved placeholder is a refused run — validate that
   none remain before writing.
6. **Refuse rather than improvise.** Missing `skill_version_id`, hash mismatch, blocked cell,
   unknown phase → refuse that cell with a typed reason and continue with the rest; report the
   refusals. Never silently shrink a batch.

## Hard constraints

- Reuse `payload_fingerprint` and the store API; do not reimplement hashing.
- The orchestrator has **no gate authority** — it leases work, it never decides readiness.
- Do not resurrect `REVIEW.json` or any mutable file-based review state.
- Do not touch `skills/` content.
- Tests: contract round-trips through `collect_wave.py::_validate`; a stale snapshot is refused; a
  hash mismatch is refused; batch size is capped; selection is deterministic for a fixed snapshot.

## Acceptance

From a fresh snapshot, `issue_batch` writes 10 valid contracts, and `collect_wave.py --contract ...`
accepts all 10 without a `BatchRejected`. Full suite green.

---

# Sequencing

SPEC A first — until `security_pass > 0` nothing downstream can complete, and SPEC B's selection
predicate depends on cells not being blocked. They can be *built* in parallel; they must be
*verified* in order.
