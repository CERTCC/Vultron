---
name: update-priorities
description: >
  Interactively update GitHub Project #24 ("Vultron Planning") by moving
  items between Schedule tiers (Now/Next/Later/Someday) via the GitHub
  Projects API. Use when you want to schedule issues, promote triage items,
  or rebalance tiers based on findings from check-priority-status.
---

# Update Priorities

Interactively update the Schedule field on issues and Epics in GitHub
Project #24. Designed as a companion to `check-priority-status` — run the
status check first to understand the current state, then use this skill to
apply scheduling changes.

## Quick Start

Run the update-priorities skill.

The skill will:

1. Query Project #24 for all items and their current Schedule tiers
2. Present options:
   - **Move item(s) to a different tier** (Now / Next / Later / Someday)
   - **Promote Triage items** (Someday items to a schedule tier)
   - **Add an issue to the board** (assign Schedule=Someday)
   - **Sync Epic children to their Epic's tier** (raise Someday/off-board
     descendants of scheduled Epics)
   - **Archive a completed Epic** (close issue + history entry)
3. For each action, apply the change live via GitHub API
4. Commit if any notes/history files changed (board changes need no commit)

## Project Board Constants

Board IDs (project node ID, Schedule field ID, Schedule option IDs) are
**never hardcoded** — they rotate when the field's options are edited. Resolve
them by name at runtime via `board-id.sh`; see
`.agents/skills/shared/README.md` for the full interface:

```bash
PROJECT_ID=$(bash .agents/skills/shared/board-id.sh project)
SCHEDULE_FIELD_ID=$(bash .agents/skills/shared/board-id.sh schedule-field)
# Option ID for a given tier (Focus|Now|Next|Later|Someday):
SCHEDULE_OPTION_ID=$(bash .agents/skills/shared/board-id.sh schedule "${TIER}")
```

## Workflows

### Move Item to a Different Tier

1. Identify the issue or Epic number.
2. Resolve board IDs and find the item's project item ID:

   ```bash
   PROJECT_ID=$(bash .agents/skills/shared/board-id.sh project)
   ITEM_ID=$(gh api graphql -f query='{
     node(id:"'"$PROJECT_ID"'") {
       ... on ProjectV2 {
         items(first:100) {
           nodes {
             id
             content { ... on Issue { number } }
           }
         }
       }
     }
   }' --jq ".data.node.items.nodes[] \
     | select(.content.number == ${ISSUE_NUMBER}) | .id")
   ```

3. Apply the Schedule field update (resolve the target tier's option ID by
   name, e.g. `bash .agents/skills/shared/board-id.sh schedule Now`):

   ```bash
   SCHEDULE_FIELD_ID=$(bash .agents/skills/shared/board-id.sh schedule-field)
   SCHEDULE_OPTION_ID=$(bash .agents/skills/shared/board-id.sh schedule "${TIER}")
   gh api graphql -f query="mutation {
     updateProjectV2ItemFieldValue(input: {
       projectId: \"${PROJECT_ID}\"
       itemId: \"${ITEM_ID}\"
       fieldId: \"${SCHEDULE_FIELD_ID}\"
       value: { singleSelectOptionId: \"${SCHEDULE_OPTION_ID}\" }
     }) { projectV2Item { id } }
   }"
   ```

### Add Issue to Board

Add the issue to Project #24 and set its Schedule in one call via the shared
helper (single source of truth for board/field/option IDs; accepts
`Focus | Now | Next | Later | Someday`):

```bash
bash .agents/skills/shared/add-to-project.sh "${ISSUE_NUMBER}" "${SCHEDULE:-Someday}"
```

To **re-tier an item already on the board**, resolve its existing project item
ID and set the Schedule field directly (resolve every ID by name via
`board-id.sh` — see the "Move Item to a Different Tier" workflow above and
`.agents/skills/shared/README.md`).

### Sync Epic Children to Their Epic's Tier

New issues default to Someday even when filed under a scheduled Epic, so a
Now-tier Epic's children drift into Triage. Raise every open descendant
(recursively) that sits below its Epic's tier:

```bash
# Dry run first: prints RAISE / SKIP-* lines, changes nothing
bash .agents/skills/shared/sync-epic-schedules.sh
# Then apply (defaults to Epics in Focus, Now, Next; or name Epics explicitly)
bash .agents/skills/shared/sync-epic-schedules.sh --apply [<EPIC>...]
# Include Later Epics (--tiers is ignored when Epics are named)
bash .agents/skills/shared/sync-epic-schedules.sh --tiers "Focus Now Next Later"
```

The script only raises, never lowers, and only raises the un-prioritized
states: Someday, on-board with no Schedule, and off-board. It reports but does
not touch the rest, which need a human call: a child ranked **above** its Epic
(deliberate prioritization), a child at **Later** (deliberate deferral, unlike
the Someday default), and any non-tier value such as `Completed`
(`SKIP-OTHER`). Present those to the user rather than changing them.

### Archive a Completed Epic

1. Confirm all sub-issues are closed.
2. Invoke the `archive-history` skill:

   ```text
   TYPE    = priority
   TITLE   = <Epic title>
   SOURCE  = EPIC-<number>
   BODY    = <Epic summary, linked issues, completion notes>
   ```

3. Close the Epic issue:

   ```bash
   gh issue close <EPIC_NUMBER> --repo CERTCC/Vultron
   ```

4. The `archive-history` skill commits and pushes the history entry file.

## Notes

- **Board changes are live**: Schedule field updates take effect immediately
  via API — no file commit is needed.
- **Skill is independent**: Does not automatically run
  `check-priority-status`; run it first to identify what needs changing.
- **Undo**: Re-run the move mutation with the previous option ID, or use
  `gh issue reopen` for closed Epics.
- **Someday = Triage**: Issues on the board with `Schedule=Someday` (or no
  Schedule) appear in the Triage view and should be reviewed regularly.
