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
| `plan/incoming/learnings/` | Count of `.md` files (excluding `.gitkeep`)? |
| GitHub Issues — type: Idea | Count of open issues |
| GitHub Issues — type: Bug | Count of open issues |
| GitHub Issues — type: Concern | Count of open issues — **this is the only concern source; do not read `docs/reference/codebase/CONCERNS.md`** |
| GitHub Project #24 — `Schedule=Someday` (Triage) | Count of issues needing scheduling |
| GitHub Pull Requests — open | Count of open PRs |
| GitHub Project #24 — `Schedule=Now` Epics | List of open Epics driving current work |

See [REFERENCE.md](REFERENCE.md) for the exact `gh` and `git` commands.

## Report Format

Print a single table followed by a "Next up" callout:

```text
## Vultron Status — YYYY-MM-DD HH:MM

| Queue                  | Count | Skill                |
|------------------------|-------|----------------------|
| Incoming Learnings     |   2   | learn                |
| Ideas (open)           |   1   | plan-issue           |
| Bugs (open)            |   3   | bugfix               |
| Concerns (open)        |   0   | —                    |
| Open PRs               |   2   | pr-comprehensive-fix |
| Triage (Someday)       |   5   | review-priorities    |
| Ready to build         |   4   | build                |

Now: #691 Migrate project tracking | #476 Bug Fixes and Demo Polish

**Next up**: learn — plan/incoming/learnings/ has unprocessed files.
```

- **Incoming Learnings count**: number of `.md` files in `plan/incoming/learnings/`
  (zero if the directory is empty or contains only `.gitkeep`)
- **Ready to build**: open leaf issues in a Now-scheduled Epic that have no
  open blockers — determined entirely from the GitHub API
- **Triage**: issues in Project #24 with `Schedule=Someday` and no Epic parent
- **Now** line: titles of all open Epics with `Schedule=Now` on Project #24

## Recommendation Logic

Ranked priority (first matching condition wins for the primary recommendation;
list all non-zero conditions as `ask_user` choices):

1. `learn` — plan/incoming/learnings/ has files
2. `process-concerns` — open Concern issues
3. `plan-issue` — open Idea or Concern issues
4. `bugfix` — open Bug issues
5. `pr-comprehensive-fix` — open PRs > 0
6. `review-priorities` — triage items > 0 (Schedule=Someday with no Epic)
7. `build` — ready-to-build count > 0
8. *(stop)* — all queues empty, nothing actionable

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
