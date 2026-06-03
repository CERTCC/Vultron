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
   - **Archive a completed Epic** (close issue + history entry)
3. For each action, apply the change live via GitHub API
4. Commit if any notes/history files changed (board changes need no commit)

## Project Board Constants

| Name | Value |
|---|---|
| Project node ID | `PVT_kwDOAjf0s84BZnre` |
| Schedule field ID | `PVTSSF_lADOAjf0s84BZnrezhUlFOM` |
| Now option ID | `1e84189c` |
| Next option ID | `9fca00b2` |
| Later option ID | `e2149d3e` |
| Someday option ID | `fcffa79d` |

## Workflows

### Move Item to a Different Tier

1. Identify the issue or Epic number.
2. Find the item's project item ID:

   ```bash
   ITEM_ID=$(gh api graphql -f query='{
     node(id:"PVT_kwDOAjf0s84BZnre") {
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

3. Apply the Schedule field update:

   ```bash
   gh api graphql -f query="mutation {
     updateProjectV2ItemFieldValue(input: {
       projectId: \"PVT_kwDOAjf0s84BZnre\"
       itemId: \"${ITEM_ID}\"
       fieldId: \"PVTSSF_lADOAjf0s84BZnrezhUlFOM\"
       value: { singleSelectOptionId: \"${SCHEDULE_OPTION_ID}\" }
     }) { projectV2Item { id } }
   }"
   ```

### Add Issue to Board

1. Resolve the issue's node ID:

   ```bash
   NODE_ID=$(gh api graphql -f query='{
     repository(owner:"CERTCC", name:"Vultron") {
       issue(number: '"${ISSUE_NUMBER}"') { id }
     }
   }' --jq '.data.repository.issue.id')
   ```

2. Add to project and set Schedule:

   ```bash
   ITEM_ID=$(gh api graphql -f query="mutation {
     addProjectV2ItemById(input: {
       projectId: \"PVT_kwDOAjf0s84BZnre\"
       contentId: \"${NODE_ID}\"
     }) { item { id } }
   }" --jq '.data.addProjectV2ItemById.item.id')

   gh api graphql -f query="mutation {
     updateProjectV2ItemFieldValue(input: {
       projectId: \"PVT_kwDOAjf0s84BZnre\"
       itemId: \"${ITEM_ID}\"
       fieldId: \"PVTSSF_lADOAjf0s84BZnrezhUlFOM\"
       value: { singleSelectOptionId: \"fcffa79d\" }
     }) { projectV2Item { id } }
   }" >/dev/null
   ```

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
