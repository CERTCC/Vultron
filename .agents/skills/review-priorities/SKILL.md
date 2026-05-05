---
name: review-priorities
description: >
  Audit open tasks and GitHub issues against PRIORITIES.md and interview the
  user to place any untracked items into the priority list. Use when the user
  wants to review, triage, or update project priorities, mentions
  "review priorities", or asks what is missing from the priority list.
---

# Skill: Review Priorities

Identify open work that is not yet reflected in `plan/PRIORITIES.md`, then
interview the user (grill-me style) to decide where each item belongs.

## Quick start

1. Collect open items from `plan/IMPLEMENTATION_PLAN.md` and GitHub issues.
2. Diff against `plan/PRIORITIES.md` to find gaps.
3. Interview the user with `ask_user` for each gap.
4. Update `plan/PRIORITIES.md` with the agreed placements.
5. Invoke `commit`.

## Workflow

### Phase 1 — Collect open plan tasks

Parse `plan/IMPLEMENTATION_PLAN.md` for every unchecked task (`- [ ]`).
Record the parent task ID (e.g. `TASK-AF`, `CC.1`) and the task title.

### Phase 2 — Collect open GitHub issues

Fetch open issues from `CERTCC/Vultron` using `github-mcp-server-list_issues`
(state: `OPEN`). Paginate until all open issues are loaded.

### Phase 2.5 — Collect group:unscheduled Issues

Fetch all open Issues with the `group:unscheduled` label using
`github-mcp-server-list_issues` with `labels: ["group:unscheduled"]`.
These are Issues created by `ingest-idea`, `update-plan`, or agents during
development that have not yet been slotted into PRIORITIES.md.

Add them to the gap list as **Unscheduled Issues** — a separate category
from untracked plan tasks and untracked open issues.

### Phase 3 — Diff against PRIORITIES.md

Read `plan/PRIORITIES.md`. An item is considered **tracked** if any of the
following appear anywhere in the file:

- The GitHub issue number (e.g. `#378`)
- The full GitHub issue URL
- The task ID (e.g. `TASK-AF`, `CC.1`, `BTND5.2`)

Build two gap lists:

- **Untracked plan tasks** — task IDs present in IMPLEMENTATION_PLAN.md but
  absent from PRIORITIES.md.
- **Untracked open issues** — open GitHub issues absent from PRIORITIES.md.

> Skip issues whose titles indicate they are sub-issues of a parent already
> tracked in PRIORITIES.md, provided the parent issue is also open and the
> sub-issue is listed under its parent.

### Phase 4 — Interview the user

For each untracked item (including **Unscheduled Issues** from Phase 2.5),
use `ask_user` to ask where it belongs.
See [REFERENCE.md](REFERENCE.md) for question templates and placement rules.

For each `group:unscheduled` Issue, the choices are:

- Slot into an existing PRIORITIES.md group (update the Issue's `group:` label)
- Create a new PRIORITIES.md group for it
- Close or defer (leave as `group:unscheduled` or close the issue)

Use the grill-me skill for contentious placement decisions or when the user
wants to think through the priority ordering in depth.

### Label Naming Rules (PAD-02-007)

Before assigning or creating any `group:` label:

- **Never include a priority number** in the label name.
  Use `group:architecture-hardening`, **not** `group:473-architecture-hardening`
  or `group:473`. Priority numbers change when PRIORITIES.md is reordered; label
  names must not.
- **Derive the name** from the priority group title using short, descriptive
  kebab-case (e.g., "Cyclomatic Complexity Enforcement" → `group:cyclomatic-complexity`).
- **Check for label existence** before assigning. If the label does not yet
  exist, create it first:

  ```bash
  gh label create "group:<slug>" \
    --repo CERTCC/Vultron \
    --description "<Priority group title (no number)>" \
    --color "#1d76db"
  ```

  Use the priority group title (without the number) as the description.

### Phase 5 — Update PRIORITIES.md and Issue labels

Apply the agreed placements:

- **Insert into existing block**: add the item to the sub-issues list or body
  of the named priority block.
- **New priority block**: insert a new `## Priority NNN: Title` section at the
  agreed position. Choose a number that leaves gaps above and below for future
  insertion.
- **Update group: label**: for each `group:unscheduled` Issue that was slotted,
  update its label:

  ```bash
  gh issue edit <N> --repo CERTCC/Vultron \
    --remove-label "group:unscheduled" \
    --add-label "group:<chosen-group-name>"
  ```

- **Defer / skip**: note the item and why it was deferred; do not add it.

Preserve the ascending-number ordering of priority blocks. Do not renumber
existing blocks.

### Phase 6 — Commit

Invoke the `commit` skill with a message like
`plan: triage N untracked items into PRIORITIES.md`.
