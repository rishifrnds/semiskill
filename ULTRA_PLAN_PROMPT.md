# SemiSkill — Ultra-Mode Build Plan Prompt

> **How to use this file.** Paste the block below into Claude Code with the word **`ultracode`**
> included (that is the explicit opt-in that authorizes multi-agent Workflow orchestration).
> The plan is written as phases with parallelizable fan-out and adversarial verification so ultra
> mode can decompose it across subagents. Run the phases **in order** — each is one well-scoped
> fan-out; read the result before launching the next. Do not let one workflow try to build all six
> layers at once.

---

## THE PROMPT (paste from here)

`ultracode`

You are the **Principal AI-Native Systems Architect** for **SemiSkill**, an internal,
security-verified Agent-Skill marketplace. Build it as a closed-loop **AIOS** instance. Read
`CLAUDE.md`, `STATE_RULES.md`, `DECISIONS.md` (ADR-001, ADR-002), and the AIOS research at
`E:\code\aios\research\` before architecting. Follow the state system in `STATE_RULES.md` and
checkpoint after every atomic step.

### Mission
Agent Skills are blocked inside the company because an unverified skill is a prompt-injection /
data-exfiltration / tool-abuse vector. Build one **internal** place — hosted on a **SharePoint**
page, accessible to everyone in the company — where employees **publish, discover, search,
comment on, rate, and reuse** skills exactly like `skills.sh`, **except no skill becomes
discoverable until it passes an automated security-verification pipeline and a human approval
gate.** Publishing is a *gated actuator*, never a direct write.

### Non-negotiable invariants (enforce structurally, not by prompting)
1. **Verification-gated publishing.** A skill advances only `submitted → scanned → reviewed →
   approved → published`. The SharePoint catalog is written **only** by the approval actuator.
2. **Treat every submitted skill body as an untrusted injection payload.** Held-out
   injection-test corpora and the human gold-set live outside what any pipeline agent can read or modify.
3. **Model proposes, deterministic code disposes.** Security verdicts are advisory to a human
   approver until calibration (Cohen's κ ≥ 0.6) proves otherwise. Suggest-only / human-gated by default.
4. **Every action is an append-only artifact** with the canonical schema (see CLAUDE.md): immutable,
   provenanced, ACL-labeled, with a `rollback_ref`. Corrections are new rows, never UPDATEs.
5. **Egress control + tool allowlists** on every agent. No pipeline agent has open internet or
   write access beyond its explicit actuator.

### Architecture — map every component to the AIOS 6 layers (mirror `E:\code\aios`)
- **L1 Capture / Sourcing** — ingest submissions (`skills add`, git push/PR, web upload),
  comments, ratings, reuse events → raw `captured` artifacts.
- **L2 Spine + Artifacts** — canonical append-only store + five-class event spine
  (Captured → Analyzed → Proposed → Executed → Observed). Every skill_version / scan_run / review /
  approval / comment / rating / reuse_event is one immutable row.
- **L3 Context** — ACL-enforced search/browse, skill lineage, related-skill and reuse graphs;
  permissions enforced at query traversal.
- **L4 Agents + Governance** — orchestrator-worker verification pipeline + governance gates
  (tool allowlists, egress control, human-signoff on publish, redaction before retrieval).
- **L5 Intelligence (controller)** — consumes the security error-signal, proposes verdict
  (approve / reject / request-changes), re-ranks the review queue, self-corrects scan rules; six-control
  stability gate (bounded horizon, deadbands, cooldowns, hysteresis, trajectory eval, circuit breaker).
- **L6 Sensor** — eval-as-sensor: deterministic scanners on 100% of submissions + a calibrated,
  drift-monitored LLM-as-judge on a sampled fraction → emit `eval_score` / security verdict.

### Skills / tools to reuse where they fit (pull in, don't reinvent)
- **`cloudflare/security-audit-skill`** (https://github.com/cloudflare/security-audit-skill) — core
  of the L6 static security scan for submitted skills.
- **`shadcn/ui`** (https://www.skills.sh/shadcn/ui/shadcn) — component system for the catalog UI.
- **`heygen-com/hyperframes`** (`npx skills add heygen-com/hyperframes`) — motion/animation polish
  for the catalog and skill pages.
- **AIOS at `E:\code\aios`** — mirror the existing `spine/`, `artifacts/`, `context/`, `governance/`,
  `intelligence/`, `sensor/` implementations; match their schema and patterns rather than diverging.

### The security-verification pipeline (the heart of L4 + L6) — build and adversarially test it
On every submission, run in order and write a `scan_run` artifact per stage:
1. **Static structure scan** — parse `SKILL.md` frontmatter, allowed tools, referenced scripts, file
   tree; flag executable payloads, network calls, obfuscation, oversized/binary blobs.
2. **Security-audit scan** — run `cloudflare/security-audit-skill` over the skill contents.
3. **Prompt-injection / policy test** — run the skill body against a held-out injection corpus
   (data-exfiltration lures, tool-abuse, "ignore previous instructions", scope-violation à la EchoLeak
   CVE-2025-32711). The corpus is stored with a `permissions_label` the pipeline role cannot reach.
4. **Secret / PII scan** — detect embedded credentials, tokens, internal URLs, PII.
5. **LLM-as-judge risk rating** (L6, sampled + always on suspected-malicious) — calibrated against a
   human gold-set; cross-model (never judge its own family); position/verbosity-bias mitigations on.
6. **L5 verdict** — aggregate the error-signal into `approve / reject / request-changes`, surfaced to a
   **human approver** who signs off. Only on human approval does the **publish actuator** write the
   SharePoint catalog and set state `published`, with a tested `rollback_ref` (unpublish/quarantine).

### skills.sh-parity marketplace features (L1 + L3 + UI)
Submit/version a skill; browse & full-text/semantic search; skill detail page (README, allowed tools,
provenance, scan report badge, version history); **comment** threads; **rate / upvote**; **reuse**
(one-click `skills add` / copy install command); author profiles; "trending / most-reused"; reuse graph.

### Build order (run each as its own ultra-mode workflow phase; verify before advancing)
1. **Phase A — Foundation & schema.** Lock canonical artifact schema (confirm ADR-001), stand up L2
   append-only store + migrations + the five spine transitions. *Verify: schema round-trips; corrections
   append not update.*
2. **Phase B — Capture + Context (L1/L3).** Submission intake (CLI/git/web), catalog read model,
   ACL-enforced search + lineage/reuse graph. *Verify: a submitted skill is queryable only per its ACL.*
3. **Phase C — Security pipeline (L4/L6).** Build the 6-stage pipeline above. **Fan out a red-team
   subagent panel** that crafts malicious/injected skills and confirms each is caught and blocked from
   publish; adversarially verify no unverified skill can reach the catalog. *Verify: red-team pass rate;
   zero unverified publishes; injection corpus stays unreadable by pipeline role.*
4. **Phase D — Intelligence controller (L5).** Verdict aggregation, review-queue ranking, self-correction,
   six-control stability gate, model routing (cheap→premium on ambiguity). *Verify: no oscillation on a
   replayed scan stream; cost-per-verified-skill tracked.*
5. **Phase E — SharePoint hosting + UI.** shadcn/ui + hyperframes catalog embedded in a SharePoint page
   (choose & record hosting model as an ADR: SPFx web part vs. list+SPA vs. Power Platform); publish
   actuator writes only via the gate. *Verify: publish appears in SharePoint only after human approval;
   comment/rate/reuse work end-to-end.*
6. **Phase F — Governance hardening & docs.** Egress controls, tool allowlists, redaction, rollback drill,
   calibration report (κ), adoption guide. *Verify: rollback tested; κ ≥ 0.6; egress denied by default.*
7. **Phase G — Seed the catalog with role-based skills (dogfood the pipeline).** Generate one
   role-enablement skill per (role × level) across the **entire semiconductor org** using the work-list in
   `specs/ROLE_TAXONOMY.md` — Design & Verification, Physical Design, Analog/RF, CAD/EDA, Silicon
   Validation, Test, Process/Fab, Packaging, Reliability/Quality, Firmware/SW, Product, Program, Sales,
   Marketing, Finance, HR, **Payroll**, Ops/Supply-chain, IT/Security, Legal/IP, and Executive — across
   every seniority level (fresher → junior → intermediate → senior → staff → senior-staff → principal →
   distinguished → fellow/VIP → architect; lead → manager → senior-manager → director → senior-director →
   VP → EVP → C-suite). **Fan out one generator subagent per function**, each producing skills for its
   roles; **every generated skill is submitted through L1 and must pass the full L4/L6 pipeline + human
   approval before publish — no back-door inserts** (Phase C invariant applies to seed skills too). Tag
   each with `function` / `role` / `level-tier` / `owner` for L3 faceted search. Generate in waves by
   function, Design/Verification first. *Verify: 100% of seed skills carry a passing scan_run + approval
   artifact; a deliberately-broken seed skill is blocked exactly like any other submission; catalog is
   faceted by function/role/level.*

### Acceptance evals (write these FIRST, per AIOS software-factory discipline)
- A **benign** skill: submit → passes all scans → human approves → appears in SharePoint → reusable.
- A **malicious/injected** skill (from held-out corpus): submit → blocked at scan → **never** discoverable →
  quarantined with an artifact trail.
- **Publish-path invariant test:** attempt a direct catalog write bypassing the gate → rejected.
- **ACL test:** a `need-to-know` skill is invisible to an unauthorized querier.
- **Rollback test:** an approved skill can be unpublished/quarantined within the defined window.
- **Drift test:** falling judge-vs-gold-set κ blocks the L5 controller from auto-acting.
- **Seed-catalog test:** every role in `specs/ROLE_TAXONOMY.md` has a generated skill that reached
  `published` only via a passing `scan_run` + human `approval` artifact; faceted search returns skills
  by function/role/level; a deliberately-malicious seed skill is blocked identically to a normal one.

### Guardrails for you (the orchestrator)
- Confirm the three open decisions as ADRs before coding them: (a) SharePoint hosting model,
  (b) where the artifact store + pipeline run given egress control, (c) v1 scanner scope.
- Keep the artifacts table the single source of truth; wrap thin eval/tracing libs, don't adopt a
  heavyweight platform as system of record.
- Human-gated publish and any external communication stay human-approved. Do not auto-publish.
- Checkpoint per `STATE_RULES.md`; open ADRs for every architectural choice; keep changes surgical.

Begin with **Phase A**. First restate the Goal Signal (skills safely shared), the Measured Output
(verified `skill_version` + reuse artifacts), and the Feedback Mechanism (scan verdict → approval →
reuse telemetry → scan-rule self-correction). Then lock the schema and build L2.

## (end of prompt)

---

## Notes for the human (not part of the pasted prompt)
- **Repo:** https://github.com/rishifrnds/semiskill — run `git init` + first commit before feeding this.
- **Why phased, not one shot:** ultra mode fans out per phase; the security pipeline (Phase C) needs its
  own adversarial red-team panel, which is wasted if bundled with UI work.
- **The load-bearing safety property** is Phase C's invariant: *no skill is discoverable in SharePoint
  until scanned + human-approved.* Everything else is marketplace polish around that gate.
