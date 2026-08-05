# Failure signature schema

A **failure signature** is a short, stable string that identifies *a class of failure*, not one run.
Two runs of the same bug must produce the same signature; two different bugs must not.

Several skills in this pack produce or consume signatures. They all use this shape, so a signature
produced while debugging one test can be matched against a triage table produced by someone else
last week. That matching is the whole point — it is what stops two engineers debugging the same bug
twice.

## Shape

```
<phase>|<kind>|<where>|<what>
```

| Field | Meaning | Examples |
|---|---|---|
| `phase` | when it broke | `compile`, `elab`, `run`, `finalise`, `post` |
| `kind` | the class of failure | `assert`, `scoreboard`, `timeout`, `xprop`, `fatal`, `uvm-error`, `tool` |
| `where` | the most specific stable location | a module, class, or component path |
| `what` | the normalised message | the message with all run-specific values removed |

## Normalising `what` — the part people get wrong

The message is only stable once every run-specific value is removed. Replace, in this order:

1. Times and cycles → `T` (`at 141250 ns` becomes `at T`)
2. Any hex or decimal literal that is data → `N` (`expected 0xdeadbeef got 0x0` becomes `expected N got N`)
3. Array and loop indices → `i` (`buf[37]` becomes `buf[i]`)
4. Random seeds and run identifiers → drop entirely
5. Absolute paths → keep only the file's base name
6. Instance paths → keep the last two hierarchy levels

What survives is the invariant part of the message. If two failures normalise to the same string but
are genuinely different bugs, `where` is not specific enough — push one level deeper into the
hierarchy rather than adding the value back into `what`.

## Worked example

Raw, from a log:

```
UVM_ERROR /home/eng/work/blk/tb/env/sb.sv(212) @ 141250: uvm_test_top.env.sb [MISCOMPARE]
  expected 0xdeadbeef got 0x00000000 on beat 37 (seed 918273645)
```

Signature:

```
run|scoreboard|env.sb|MISCOMPARE expected N got N on beat i
```

The same bug on another seed, at another time, on another beat, produces exactly that string again.

## Rules

- A signature is **derived**, never invented. Every field must be traceable to text that was actually
  in the log. If a field cannot be filled from the log, write `?` rather than guessing.
- Signatures are compared **exactly**. Do not paraphrase.
- One failure gets one signature. A run with fourteen failures gets fourteen signatures, then they
  are grouped — grouping first is how distinct bugs get merged and lost.

## Team-local additions

Teams normalise a few more things that are specific to their environment.

- **Extra values to normalise:** [[FILL: any other run-specific values our logs print — build ids, host names, job numbers]]
- **Our message prefixes:** [[FILL: the error prefixes our house macros emit, if not UVM_ERROR / UVM_FATAL]]
- **Where known signatures are recorded:** [[FILL: the file, page, or tracker query holding our known-issue list]]

If a slot is unfilled, say so and ask — do not guess a convention.
