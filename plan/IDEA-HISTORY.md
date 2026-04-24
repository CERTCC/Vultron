# Project Idea History

Ideas that have been processed into specs, notes, or implementation plans
are archived here for traceability.

---

## IDEA-260402-01 Config files should be YAML and loaded into a structured config object

relevant on or after commit: 3fdbfa96155d87d716027c5d3a1fb929d0968b28

When we have a need for config files, we should use YAML for readability and
ease of editing. We should also load the YAML config into a structured
config object using Pydantic so that we can enforce types and have a clear
schema for our configuration. Rough sketch of the workflow: Load YAML config
into a dict (`config_dict=yaml.safe_load()`), then pass that dict to a Pydantic
model (`Config.model_validate(config_dict)`) that defines the schema for our
configuration. This can also allow us to have nested configuration sections
for different components, and modularity in how we define and validate
config for different adapters or features.

**Processed**: 2026-04-23 — design decisions captured in
`specs/configuration.md` (CFG-01 through CFG-06) and
`notes/configuration.md`.

---

## IDEA-26040903 Do not worry about backward compatibility in prototype phase

We are still squarely in a prototyping phase, and there are no outside users
of the code we are developing here. When we make changes to the codebase we do
not need to worry about backward compatibility at all. If you're making a
change, make the change all the way. Do not hedge to preserve backward
compatibility (but obviously do not break the code in a way that prevents
you from testing your changes).

**Processed**: 2026-04-23 — design decisions captured in
`specs/prototype-shortcuts.md` (PROTO-08-001 through PROTO-08-004).

---

## IDEA-26041501 Need spec to avoid compatability shims in prototype

We need a spec that is declarative about avoiding the use of compatability
shims when refactoring code. We're in prototype development mode so there
are no
external dependencies that we need to maintain downstream. When we change
something it should be complete and permanent. Search notes/ for "shim" and
you'll see where this has come up before. We just need to make it an
explicit principle in the specs. Compatibility shims are technical debt that
we do not want to take on right now.

**Processed**: 2026-04-23 — folded into IDEA-26040903 processing; design
decisions captured in `specs/prototype-shortcuts.md` (PROTO-08-001 through
PROTO-08-004).

---

## IDEA-26041001 Outbox posting must have `to:` field requirement

The fact that D5-7-TRIGNOTIFY-1 even had to be a task is an indicator that
we are missing a requirement: Only activities can be posted to an outbox.
And activities must have a `to:` field. We are not supporting `bto:` or
`cc:` or `bcc:`, and so far we are assuming that all Vultron exchanges are
DMs. There
are no public messages (which in ActivityPub would be an Activity lacking a
`to:`). So we should make it a requirement (or two) that only activities
with a `to:` field can be posted an outbox, and this should be on the outbox
port itself as an acceptance criteria that raises an exception when violated.

**Processed**: 2026-04-23 — design decisions captured in
`specs/outbox.md` (OX-08-001 through OX-08-004) and `notes/outbox.md`.

---

## IDEA-26042201 append-only means append, not "insert at specific location"

I notice that agents often try to "insert at specific location in file" even
when the file is intended to be append-only, like the implementation history.
This is a sign that the agent is not fully understanding the intended use and
structure of the file. For append-only files, the agent should just be adding
new content to the end of the file, not trying to edit or rearrange existing
content. There is no need to read or understand the existing content in
order to add new entries to an append-only file. The equivalent of a shell
command like `echo "new entry" >> file.txt` should be the mental model for how to
handle append-only files. The agent should not be trying to parse the file and
figure out where to insert the new entry, it should just be adding it to the end.

**Processed**: 2026-04-23 — design decisions captured in
`specs/project-documentation.md` (PD-05-001 through PD-05-005) and
`notes/append-only-file-handling.md`.

---

## IDEA-26042301 Do not check existence of append-only files before appending

When adding entries to append-only files like the implementation history,
idea history, priority history, etc., there is no need to check for the
existence of the file before appending. The agent can just open the file in
append mode and write the new entry, and if the file does not exist it will
be created automatically. This simplifies the logic and avoids unnecessary
checks for file existence. The agent should just assume that the file is
there or will be created as needed when appending new entries.

Antipattern:

```text
Check if IDEA-HISTORY.md exists (shell)
│ ls /Users/adh/Documents/git/vultron_pub/plan/IDEA-HISTORY.md 2>/dev/null && echo "EXISTS" || echo "NOT FOUND"
└ 3
 lines...
```

**Processed**: 2026-04-23 — design decisions captured in
`specs/project-documentation.md` (PD-05-001 through PD-05-005) and
`notes/append-only-file-handling.md`.

## IDEA-26041704 Bugfix skill prematurely locks in on simple fixes

Sometimes the bugfix skill is used to fix a bug that has a simple surface
fix but is an indication of a deeper underlying issue that is not being
addressed. The agent is often overly narrow in its analysis of the scope and
does not currently ask enough questions to get to the true root cause of the
issue, resulting in more bugs later on that are related to the same
underlying issue. I want to update the bugfix skill to be more rigorous
itself, but also to have more explicit instructions for when to use the ask user
tool to have a conversation about the bug with the user so we can come to a
shared understanding before setting off on implementation. Sort of similar
to the "grill me" skill but for bugs. Ask the user to help you understand
the bug better, and check in periodically to ask the user if you are on the
right track in your analysis and implementation plan. You are not expected
to solve the entire problem in an autonomous one-shot way. Sometimes bugfix
analysis will lead to a recognition that there are multiple issues that must
be addressed in order to fully resolve the problem, and that is okay, but
the bugfix skill should recognize when that is the case and suggest breaking
the work into new tasks in the implementation plan and/or capturing
additional bugs.

**Processed**: 2026-04-23 — design decisions captured in
`specs/bugfix-workflow.md` (BFW-01 through BFW-04) and
`notes/bugfix-workflow.md`.

## IDEA-26042202 bugfix skill should move fixed bugs out of BUGS.md

The bugfix skill should be updated (and any relevant specs as well) to adopt
similar behavior to what the build skill does with implementation plan tasks.
Namely: When a bug is fixed, the implementation history file should be
appended and then the bug should be removed from BUGS.md entirely rather
than leaving a tombstone or summary behind. BUGS.md should only contain open
bugs, not closed ones.

**Processed**: 2026-04-23 — design decisions captured in
`specs/bugfix-workflow.md` (BFW-04-001 through BFW-04-004) and
`notes/bugfix-workflow.md`.

## IDEA-26041002 Default embargo should result in `EM.ACTIVE` not `EM.PROPOSED`

Contrary to what was implemented in `D5-7-EMSTATE-1`, when a default embargo
is applied to a newly created case, the resulting embargo state should be
`EM.ACTIVE`, not `EM.PROPOSED`. The rationale for this is that if the
reporter did not request otherwise, then the submission of the report signals
the reporter tacitly accepting the receiver's default embargo. So when a
case is created and a default embargo is applied, the embargo can be
considered to be active immediately. The reporter can always propose a
revision later if desired, but we don't want to leave the case in a limbo
state of `EM.PROPOSED`, which would imply that *no embargo exists* until the
reporter explicitly accepts the default embargo. See
`docs/topics/process_models/em/defaults.md` for more discussion.

**Processed**: 2026-04-24 — design decisions captured in
`specs/embargo-policy.md` (EP-04-001 through EP-04-004) and
`notes/embargo-default-semantics.md`. Implementation task added to
`plan/IMPLEMENTATION_PLAN.md` as EMDEFAULT-1.
