---
name: dev-status
description: >
  Snapshot the current state of all work queues and recommend the next skill
  to run. Reads BUILD_LEARNINGS.md, GitHub Issues (by type: Idea, Bug,
  Concern), unscheduled issues, PRIORITIES.md, and the git log to assess
  staleness. Produces a concise status report, then asks the user whether to
  invoke the recommended skill. Use when resuming work after any interruption,
  or when unsure what to do next in the development cycle.
---

# Skill: Dev Status

Snapshot every work queue and recommend the next skill. This is the cycle
entry point — run it whenever you are unsure what to do next.

> **Hard stop after pivot decision.** This skill produces a report, asks once
> whether to invoke the recommended skill, then stops. It does not chain
> further skills on its own.

## Quick Start

Run the status skill. It will:

1. Read all queue states (see Inputs)
2. Print a concise status report (see Report Format)
3. Ask: "What would you like to do?" with ranked recommendations
4. Invoke the chosen skill, or stop

## Inputs

Read these in parallel:

| Source | What to check |
|---|---|
| `plan/BUILD_LEARNINGS.md` | Non-empty beyond the header? |
| GitHub Issues — type: Idea | Count of open issues |
| GitHub Issues — type: Bug | Count of open issues |
| GitHub Issues — type: Concern | Count of open issues |
| GitHub Issues — label: `group:unscheduled` | Count of open issues |
| `plan/PRIORITIES.md` | Top group with ≥1 unblocked open issue |
| `git log -- plan/PRIORITIES.md` | Days since last commit to PRIORITIES.md |

See [REFERENCE.md](REFERENCE.md) for the exact `gh` and `git` commands.

## Report Format

Print a single table followed by a "Next up" callout:

```text
## Vultron Status — YYYY-MM-DD HH:MM

| Queue                  | Count | Skill        |
|------------------------|-------|--------------|
| BUILD_LEARNINGS        |   2   | learn        |
| Ideas (open)           |   1   | ingest-idea  |
| Bugs (open)            |   3   | bugfix       |
| Concerns (open)        |   0   | —            |
| Unscheduled issues     |   5   | review-priorities |
| Ready to build         |   4   | build        |

PRIORITIES.md last updated: 3 days ago

**Next up**: learn — BUILD_LEARNINGS.md has unprocessed entries.
```

- **BUILD_LEARNINGS count**: number of `###` entry headers in the file
  (zero if only the preamble is present)
- **Ready to build**: open leaf issues in the top-priority group that have no
  open blockers
- **PRIORITIES.md staleness**: warn if last commit > 14 days ago

## Recommendation Logic

Ranked priority (first matching condition wins for the primary recommendation;
list all non-zero conditions as `ask_user` choices):

1. `learn` — BUILD_LEARNINGS has entries, or open Concern issues
2. `ingest-idea` — open Idea issues
3. `bugfix` — open Bug issues
4. `review-priorities` — unscheduled issues > 0
5. `build` — ready-to-build count > 0
6. *(stop)* — all queues empty, nothing actionable

Always include "Nothing — just show the report" as a final choice.

## Pivot Behaviour

After printing the report, call `ask_user` once:

```text
"What would you like to do?"
choices: [<ranked list of applicable skills>, "Nothing — just show the report"]
```

If the user selects a skill, invoke it immediately and stop.
If the user selects "Nothing — just show the report", stop.

Do **not** chain further skills after the pivot unless the user explicitly
asks.
