# Team profile — author once, vendor per skill

Every skill in this pack needs a handful of the same facts about how your team works. The source is
authored **here**, once, rather than being independently guessed in each skill. Capture then vendors
the exact candidate/source snapshot bytes under each skill's own `_shared/` directory because Agent Skills resolves
relative references from the skill root.

Fill this file in first. It takes about twenty minutes and it is the difference between a pack that
knows the method and a pack that knows your flow. Individual skills add their own extra slots for
things only they need; those stay in the skill.

> **If a slot below is unfilled, a skill that needs it must stop and ask.** None of them may be
> guessed. A confidently invented log path or rerun command costs more time than it saves.

> **Never put a credential, a customer name, a host name, or anything export-controlled in this
> file.** If a slot seems to be asking for one, that is a bug in the pack — say so. Run
> `python tools/lint_body.py _shared/team-profile.md` after filling it in; it catches the common
> mistakes.

---

## Where things are

| Fact | Fill in | Used by |
|---|---|---|
| **Log location** | [[FILL: where our simulation and regression logs land]] | most skills |
| **Build log location** | [[FILL: where compile and elaboration output lands, if it differs from the above]] | build/filelist work |
| **Regression summary** | [[FILL: where a regression's per-test result summary lands, and its format]] | triage |
| **Coverage output** | [[FILL: where merged coverage lands]] | coverage work |
| **Known-issue list** | [[FILL: where our known-issue list lives, how each entry is keyed, and whether it is a file that can be read or a tracker that must be searched by a person]] | triage, debug |

## How a run identifies itself

| Fact | Fill in |
|---|---|
| **Run identity** | [[FILL: what identifies one run for us — seed, test name, configuration, build tag]] |
| **Rerun convention** | [[FILL: how someone repeats one specific run — describe it; leave blank rather than guessing]] |

## What our logs print

These three are the ones skills Grep for. Get them right and most of the pack works; get them wrong
and it looks in the wrong place.

| Fact | Fill in |
|---|---|
| **Fatal markers** | [[FILL: the strings our flow prints on a real failure, beyond UVM_ERROR and UVM_FATAL]] |
| **Pass marker** | [[FILL: the string a clean run prints at the end]] |
| **Infra markers** | [[FILL: the strings that mean the environment failed rather than the design — licence, queue, host, disk]] |

> **Fatal markers** and **Mismatch markers** are not always the same thing. If your register or
> scoreboard checks print something the general flow does not, list both — the skill that needs the
> narrower one says so.

## Who owns what

| Fact | Fill in |
|---|---|
| **Area to owner map** | [[FILL: how we map a failing area to the person who owns it, and what that map is keyed on — design hierarchy, test name, or directory]] |
| **Sign-off** | [[FILL: who signs off, and on what evidence]] |
| **Bug convention** | [[FILL: what a bug title and a bug's required fields look like here]] |

## Our tools

Name them rather than assuming. Several skills need to know which vocabulary to search for, and the
pack deliberately does not guess.

| Fact | Fill in |
|---|---|
| **Simulator** | [[FILL: which simulator we use, and the command that launches a build]] |
| **Filelist convention** | [[FILL: how our filelists nest and include, and whether a relative path resolves against the invocation directory or the filelist's own directory]] |
| **Register model source** | [[FILL: what our register model is generated from, and whether that source is a file that can be read]] |

---

## How to fill this in

Open this file in Cursor and ask:

> Fill the `[[FILL: ...]]` slots in this file from this repository. Look at the build scripts,
> filelists, regression wrappers and any recent logs. Ask me for anything you cannot work out from
> the code, and do not guess.

Then check the answers. The agent is good at finding paths and conventions that are written down; it
cannot know who signs off, and it should be asking you rather than answering that one.

## Keeping it current

When a source fact changes — a new log location, a different regression wrapper — change it once
here, then propagate it only by capturing, scanning, independently reviewing, and approving new
skill versions. Installed skills are self-contained and do carry byte-identical approval-bound
copies; editing one installed copy does not update its siblings and makes that local fork unverified.
