# Issue Creation Requirements

Every new issue created via `manage_github_issue.sh` **must** supply three fields
plus a reason it exists (below). Missing any one causes the script to exit non-zero. Task and Bug bodies also
need a `Governing specs:` line (see below).

## Required fields

| Field | Flag | Why |
|---|---|---|
| **Issue type** | `--issue-type-id ID` | Determines the issue's workflow lane (Task, Bug, Idea, Concern). Without it the issue has no type and is invisible to type-filtered views. |
| **Parent epic** | `--parent N` | Routes the issue into the epic forest so it appears in sprint planning and prioritisation. An orphaned issue is invisible to capacity planning. |
| **Milestone** | `--milestone N` | Anchors the issue to a delivery target. Without it the issue floats outside every milestone filter. |

## Why the issue exists (`--opened-as` or `--planned`)

Exactly one of these is required on create. It lets a run's net issue count be
read from labels (see `completeness-doctrine.md` § "Net Issues: Close More Than
You Open").

| Flag | Use when | Label |
|---|---|---|
| `--planned` | The issue comes from planning or a user request (`plan-issue`, `update-plan`, `new-item`, a user-reported bug) | none |
| `--opened-as excursion` | Filed so the current PR can close it (an "also" excursion) | `opened:excursion` |
| `--opened-as separate-defect` | A real defect in code the PR does not touch, or a prerequisite found mid-task | `opened:separate-defect` |
| `--opened-as debt --where X` | A known weakness seen but not fixed now. `--where` names the file, directory, or spec so the nearby-debt rule can find it. Use issue type `Concern` | `opened:debt` |
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

# Open milestones with numbers
gh api repos/CERTCC/Vultron/milestones \
  --jq '.[] | "\(.number): \(.title)"'
```

## Determining the right values

- **Issue type**: infer from the work — implementation tasks → `Task`, regressions → `Bug`,
  exploratory captures → `Idea` or `Concern`.
- **Parent epic**: use `calve-epics` Mode 1 to find the best-fit open Epic; if none
  matches, run Mode 2 to propose a new one. Never leave an issue without a parent.
- **Milestone**: inherit from the source issue (the Idea/Concern/Bug being planned or fixed)
  when one exists; otherwise pick the milestone whose scope best matches the work.
  "Project Health" (milestone 25) is the default for tooling and process improvements.

## Exemptions

Epics are created via `create_epic.sh`, which bypasses this guard (Epics are
legitimately root-level and do not have a parent issue). No other exemptions exist.
