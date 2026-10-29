# Issue Creation Requirements

Agents create every issue through the `create-issue` skill, which decides the
values below and calls `manage_github_issue.sh`. Every new issue **must** supply
the required fields, a reason it exists, and a theme (below). Missing any one
causes the script to exit non-zero. Task and Bug bodies also need a
`Governing specs:` line (see below).

## Required fields

| Field | Flag | Why |
|---|---|---|
| **Issue type** | `--issue-type-id ID` | Determines the issue's workflow lane (Task, Bug, Idea, Concern). Without it the issue has no type and is invisible to type-filtered views. |
| **Parent epic** | `--parent N` | Routes the issue into the epic forest so it appears in sprint planning and prioritisation. An orphaned issue is invisible to capacity planning. The parent must be open and carry the issue's theme. |
| **Theme** | `--label theme:<name>` | Exactly one active theme from the catalog in `notes/epic-themes.md`, judged from the issue's own outcome (PAD-02-014, PAD-02-016). |
| **`Theme:` line** | in `--body` | `Theme: theme:<name> — <what this issue delivers>`, naming the label (PAD-02-018). |

A milestone is **not** required. Pass `--milestone N` only when the work belongs to a
specific release milestone (e.g. "Release 2026.10" for publish-readiness work).

## Why the issue exists (`--opened-as` or `--planned`)

Exactly one of these is required on create. It lets a run's net issue count be
read from labels (see `completeness-doctrine.md` § "Net Issues: Close More Than
You Open").

| Flag | Use when | Label |
|---|---|---|
| `--planned` | The issue comes from planning or a user request (`plan-issue`, `update-plan`, `create-issue` run by a user, a user-reported bug) | none |
| `--opened-as excursion` | Filed so the current PR can close it (an "also" excursion) | `opened:excursion` |
| `--opened-as separate-defect` | A real defect in code the PR does not touch, or a prerequisite found mid-task | `opened:separate-defect` |
| `--opened-as debt --where X` | A known weakness seen but not fixed now. `--where` names the file, directory, or spec so the nearby-debt rule can find it. Usually a `Task` or `Bug` (see § "Determining the right values") | `opened:debt` |
| `--opened-as deferred` | The current PR's own work, left undone. Unsupervised runs must not do this; it is flagged in every report | `opened:deferred` |

## Governing specs (Task and Bug bodies)

Every **Task** or **Bug** body must also carry a `Governing specs:` line
listing the spec IDs (e.g. `CS-02-003`) or group IDs (e.g. `EM-04`) the work
must satisfy — for a Bug, the requirements that define the correct behavior:

```text
Governing specs: CS-02-003, EM-04, ARCH-01-002
```

Leave it empty only as an explicit `Governing specs: none — <reason>`.
`build` and `bugfix` pass this line to `deepen-context` as the spec floor —
the requirements loaded unconditionally, before any judgment-based selection. Draw the
IDs from a `deepen-context` Spec manifest, or from
`PYTHONPATH= uv run spec-dump --index` plus targeted `--topic`/`--group`
loads. The script does not enforce this line; the authoring skill must.

Idea, Concern, and Epic bodies are exempt (Epics may carry a topic-level
line; their Tasks narrow it).

## Lookup commands

```bash
# Issue type IDs (Task, Bug, Idea, Concern, Epic)
bash .agents/skills/shared/board-id.sh issue-type Task

# Open epics (pick the best-fit parent)
# The limit MUST exceed the open-issue count — do not lower it. `gh` returns
# newest-first, so a limit below the open-issue total silently truncates the
# OLDEST issues, which is where long-lived epics live. At --limit 200 on a
# 305-open-issue repo this returned 16 of 34 open epics and hid #1190
# entirely. A truncated list is indistinguishable from a genuine no-match, and
# `calve-epics` reads no-match as a signal to create a new epic (#3319).
# Increase if the repo grows past 1000 open issues.
gh issue list --repo CERTCC/Vultron --state open --limit 1000 \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Epic") | "#\(.number): \(.title)"'
```

## Determining the right values

- **Issue type**: choose it from the shape of the work, not from why it was
  opened. The `opened:` label (excursion, separate-defect, debt, deferred) is
  independent of the type; a `debt` item is usually a `Task` or `Bug`.
  - `Bug` — current behavior is wrong against a spec, ADR, or clear intent. The
    cause may still need diagnosis (`bugfix` investigates first); what matters is
    that the correct behavior is decided. Stale spec or notes text that names
    deleted code counts.
  - `Task` — clear work with a known approach and no open design decision:
    refactors, module splits, missing docs pages, ratchets, sweeps.
  - `Concern` — a decision, investigation, or human or protocol-design call is
    needed before a work item can be written; several plausible answers exist.
  - `Feature` — a new capability that is already specified well enough to
    build.
  - `Idea` — a new capability or direction not yet shaped into work.

  When one finding holds both a ready fix and an open question, file them as
  separate issues, and wire the blocker if one gates the other.
- **Theme**: classify by outcome per `notes/epic-themes.md` § "Classify by
  Outcome". Never copy the parent's theme or the theme of the work that found
  the issue.
- **Parent epic**: use `calve-epics` Mode 1 among the open Epics that carry the
  issue's theme. If none fits, ask the user when one is present; otherwise
  calve an auto-calved Someday Epic through `create-epic` (`create-issue`
  Phase 5). Never leave an issue without a parent.

## The script gate

On create, `manage_github_issue.sh` runs `theme-gate`
(`vultron/metadata/planning/theme_fit/gate.py`) before anything is created. It
refuses, printing every violation, an issue that has:

- no `theme:` label, more than one, or one the catalog does not list as active;
- no `Theme:` line naming its theme, or one with no outcome after the dash;
- a `--parent` that is closed, carries no theme, or carries a different theme.

A refusal is a fault in the input, not in the gate: fix the theme, the line, or
the parent, and run `create-issue` again.

## Epics

Epics are created via the `create-epic` skill, whose script takes
no parent: Epics sit at the root, one layer deep. It runs the same gate in Epic
mode: one active theme, or two with a body line naming both (PAD-02-015), and a
`Theme:` line. No other exemptions exist.
