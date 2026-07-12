# State Management System — Non-negotiable Rules

This project uses a 5-file state system with rotation, enforcement, and
session ownership: CLAUDE.md, MEMORY.md, STATUS.md, DECISIONS.md, BLOCKERS.md.
Plus an `archive/` directory and a `.session-lock` file.

Your CLAUDE.md should reference this file — for example, add a line:
`Follow the state management system defined in STATE_RULES.md — read it before any code-modifying action.`

---

## Definitions

**Atomic step** — the smallest unit of work you can complete AND verify AND
commit in one go, producing one git commit. Heuristic: if describing what
was done requires the word "and" to join two independent outcomes, it is
two steps. Target: 2–10 minutes. Hard ceiling: 20 minutes — split longer work.

**Phase** — a named arc of work bounded by explicit entry and exit criteria,
declared in MEMORY.md's Current Phase section. Rotation happens at phase
exit, not at arbitrary checkpoints.

**Session** — one continuous conversation run with write authority over the
project. Identified by a session-id with this exact format:
`YYYYMMDDTHHMMSSZ-hostname-xxxxxx` where `xxxxxx` is 6 random hex chars.
Example: `20260419T193500Z-laptop-a3f2c1`. Generate once at session start.

**STEP-ID** — `<PHASE>-<NNN>`, e.g., P1-003, P2-012. NNN monotonically
increasing from 001 within each phase. New phase restarts NNN at 001 under
its own prefix. Globally unique because prefixes differ. Never reused for
abandoned/rolled-back steps. Corrections use the suffix form:
`P2-012-correction-of-P1-042`.

---

## Checkpoint discipline

After every atomic step, in this exact order:

1. `git pull --rebase` if a remote exists (`git remote -v` non-empty).
   Skip silently if no remote. If rebase fails, STOP and report.
2. `git add -A && git commit -m "wip: <STEP-ID> <what>"` — always before state updates
3. Append entry to MEMORY.md Completed Steps with full marker
4. Overwrite STATUS.md (including session block + crash-resume note)
5. Update DECISIONS.md if an architectural choice was made
6. Update BLOCKERS.md if blockers changed; run escalation scan
7. Refresh `.session-lock` timestamp

Never leave more than 10 minutes of work without a checkpoint. A power-off
at minute 11 that loses work is a process failure, not a hardware failure.

If you find yourself about to summarize progress instead of checkpointing,
stop and checkpoint first.

---

## Checkpoint self-check (runs BEFORE every new step)

Before starting any new step, run this gate. If any check fails, STOP and
repair state before proceeding.

- ☐ `git status` shows clean working tree (prior step's changes committed)
- ☐ `git log -1 --format=%ct` timestamp is within the last 15 minutes
- ☐ MEMORY.md's last Completed entry has `status: done` AND its `artifacts`
  line references the last commit SHA (`git rev-parse --short HEAD`)
- ☐ STATUS.md's "Last updated" timestamp is within the last 15 minutes
- ☐ STATUS.md session ID matches this session's id AND matches `.session-lock`
- ☐ STATUS.md's "Active step" matches MEMORY.md's most recent entry OR
  names the step about to begin
- ☐ `.session-lock` exists and was last refreshed <15 minutes ago
- ☐ Any BLOCKERS.md entry past its `Escalate at` has been surfaced to the
  user (or user has acknowledged it in the current session)

On failure:
1. Do NOT start the new step.
2. Output: `CHECKPOINT SKIP DETECTED: <which check failed>`
3. Repair: commit pending changes, append missing MEMORY.md entry (with
   actual NOW timestamp — never backdate), overwrite STATUS.md.
4. Only then proceed.

Add `delayed: true, reason: <why>` on any repair entry whose timestamp
is later than when the work actually occurred.

---

## MEMORY entry types

```
[STEP-ID] <ISO-8601 timestamp>  status: done
  what: <one-line description>
  artifacts: <commit SHA first, then file paths, URLs, ADR-IDs>
  next: <STEP-ID of what follows, or "end-of-phase">

[STEP-ID] <ISO-8601 timestamp>  status: abandoned
  what: <one-line description>
  reason: <why abandoned — e.g., "obsoleted by ADR-012", "dead end">
  artifacts: <any commits made before abandonment, for archaeology>

[STEP-ID] <ISO-8601 timestamp>  status: rolled-back
  what: <one-line description of original work>
  rollback-commit: <SHA of the revert/reset commit>
  reason: <why rolled back>

[STEP-ID-correction-of-ORIG] <ISO-8601 timestamp>  status: correction
  what: <what the correction says>
  corrects: <original STEP-ID, including archived ones like P1-042>
  reason: <why the correction is needed>
```

Prose is never a completion marker. Only `status: done` + timestamp + commit
SHA counts. Completed entries are NEVER edited — use `status: correction`.

At most ONE In-Flight step exists at any time. Starting a new step requires
the previous one to be moved to Completed, Abandoned, or Rolled-Back.

---

## ADR trigger test

Create an ADR in DECISIONS.md if the choice matches ANY of:

- Adds, removes, or pins a dependency in `package.json`, `requirements.txt`,
  `go.mod`, `Gemfile`, `Cargo.toml`, etc.
- Introduces, renames, or retires a long-lived database table, column, or
  index, or changes a column's type or null-ability.
- Establishes or changes an auth/authorization mechanism (JWT, session,
  OAuth scope, API key scheme, ACL shape).
- Establishes or changes a public API contract (route, payload shape,
  error code, breaking response change).
- Picks, changes, or couples to a deployment target (provider, region, runtime).
- Chooses between two or more mutually exclusive libraries/frameworks that
  will live in the codebase long-term.
- Establishes or changes an environment variable contract.
- Reverses or qualifies a previous ADR.

Do NOT create ADRs for trivial choices (variable names, file layout within
a module, style, commit messages).

---

## BLOCKERS rules

Age is computed (NOW − Raised), never stored.
`Raised` and `Escalate at` are frozen forever once written.

**Escalation scan** (runs as part of the checkpoint self-check):
for each blocker, if `NOW > Escalate at` AND the user has not acknowledged
this blocker in the current session, surface to the user:
`ESCALATION: BLK-NNN is <computed age>, past escalation deadline of <Escalate at>. Action needed: <What I need to unblock>.`

Acknowledgement = user message in the current session referencing BLK-NNN
by id. A new session resets the acknowledgement; re-surface on first
checkpoint.

If BLOCKERS.md exceeds 5 active items, stop taking new work until at
least 2 clear.

BLK-NNN numbering is monotonic project-wide. Never reuse numbers.

---

## File rotation

**MEMORY.md (phase-based)**
When the current phase's exit criteria are all met:
1. Copy current MEMORY.md verbatim to `archive/MEMORY-P<N>.md`.
2. Create new MEMORY.md with:
   - `## Project` (copied over)
   - `## Carry-forward from archives` — list completed phases, artifacts
     still in use (file paths, commit SHAs, ADR-IDs), open threads.
   - `## Completed Steps` (empty)
   - `## In-Flight Step` (carry over if phase ended mid-step)
   - `## Pending Steps` (new phase's plan)
   - `## Current Phase` (new phase, with exit criteria)
3. Commit: `git commit -m "rotate: archived Phase <N>, started Phase <N+1>"`
4. Update `archive/INDEX.md` with date range, STEP-ID range, step count,
   exit criterion met.

**DECISIONS.md (quarterly or at 30 ADRs)**
1. Copy verbatim to `archive/DECISIONS-<YYYY>-Q<N>.md`.
2. Trim active file to: ADRs from current quarter + any
   superseded-but-still-referenced ADR.
3. Commit: `git commit -m "rotate: archived DECISIONS through <YYYY>-Q<N>"`
4. Update `archive/INDEX.md`.

"Still-referenced" = at rotation time, ANY of these is true:
- `grep -rFq "ADR-NNN"` matches in source OR active MEMORY/STATUS/BLOCKERS/CLAUDE.
- The decision's implementation still exists in the codebase.
- Another active ADR's `Related` or `Context` mentions it.

**Archive access**
Archives are frozen — never edit. Default resume reads ONLY active files.
Read archives only when (a) an active file explicitly references an
archived STEP-ID or ADR-ID, or (b) user explicitly asks about history.

---

## Session ownership (`.session-lock`)

Only ONE session may hold the write lock at a time.

Format — single line, space-separated:
```
<session-id> <pid> <ISO8601-UTC-timestamp> <hostname>
```
Example: `20260419T193500Z-laptop-a3f2c1 12345 20260419T194733Z laptop`

**Startup**
1. Read `.session-lock` if present. Compare timestamp to now.
   - Absent: create it with this session's values.
   - Held by this session-id: refresh timestamp.
   - Held by different session-id, timestamp <2h old: STOP. Report holder, halt.
   - Timestamp >2h old (stale crash): report contents, ASK user before takeover. Never auto-steal.
2. Update STATUS.md's Session block.
3. Refresh timestamp on every checkpoint.

**Shutdown**
- Clean end: delete `.session-lock`.
- Crash: lock goes stale; next session after user confirmation takes over.

Add `.session-lock` to `.gitignore`.

---

## Hard rules

- Never backdate timestamps. If you missed a checkpoint, timestamp is NOW.
- Never `--no-verify` a git commit without explicit user approval.
  Routine `--no-verify` defeats the entire enforcement layer.
- Never edit archive files.
- Never proceed with a failed self-check.
- Prose is never a completion marker. Only `status: done` + timestamp counts.
- One writer per project at a time (enforced by `.session-lock`).
- `git pull --rebase` before every commit when a remote exists.
- Atomic steps never exceed 20 minutes — split if longer.
