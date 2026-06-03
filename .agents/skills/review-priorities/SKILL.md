---
name: review-priorities
description: >
  Audit and update Project #24 ("Vultron Planning") in one workflow. Runs a
  comprehensive status check against the board and open issues/PRs, then
  offers interactive options to move items between Schedule tiers (Now/Next/
  Later/Someday), promote Triage items, archive completed Epics, and wire
  sub-issue relationships. Use when you want to review where the project
  stands and make any necessary board updates.
---

# Review Priorities

Complete audit-and-update workflow for GitHub Project #24 ("Vultron
Planning"). Combines status checking and interactive updates into a single
guided workflow.

## Quick Start

Run the review-priorities skill. The skill will:

1. **Check status** (via `check-priority-status`):
   - Audit current board tiers against open GitHub issues and PRs
   - Generate report: tier coverage, per-Epic progress, triage count,
     stale items
2. **Review findings** with you:
   - Highlight significant gaps, empty tiers, stale items, triage backlog
   - Offer insights on what might need updating
3. **Offer interactive update options**:
   - Move items between Schedule tiers (Now / Next / Later / Someday)
   - Promote Triage (Someday) items to a schedule tier
   - Create a new Epic for related leaf issues
   - Archive a completed Epic (close issue + log history entry)
   - Skip updates and just review
4. **Commit** any notes or history changes made (board changes happen live
   via API — no file commit needed for pure scheduling changes)

## Workflows

### Typical Session: Review Only

1. Run skill → review report → exit (no changes needed)

### Typical Session: Schedule Triage Items

1. Run skill → review triage backlog
2. For each Someday item that is ready: move to Now / Next / Later
3. Done (changes applied live via API)

### Typical Session: Rebalance Tiers

1. Run skill → see Now tier is overcrowded
2. Move lower-urgency Epics from Now → Next
3. Preview changes → confirm → apply

## Report Sections (from check-priority-status)

### Summary

- Items per tier (Now / Next / Later / Someday), triage count
- Coverage % (open issues on board vs. off board)
- Stale items (no activity for 1 week)

### Per-Tier Progress

Table: each Epic's sub-issue progress by tier.

### Coverage Audit

- Issues not yet on board
- Empty tiers / Epics with no open sub-issues
- Orphaned PRs

### Health Check

- Stale items, long-pending PRs, open blockers

## Interactive Update Options

After reviewing the status report:

```text
What would you like to do?
  [A] Move item(s) between Schedule tiers
  [B] Promote Triage items to Now/Next/Later
  [C] Create a new Epic for uncovered issues
  [D] Archive a completed Epic
  [E] No changes, exit
```

### Move Item Between Tiers

```bash
# Set Schedule field on an Epic or issue in Project #24
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
}' --jq ".data.node.items.nodes[] | select(.content.number == ${ISSUE_NUMBER}) | .id")

gh api graphql -f query="mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    itemId: \"${ITEM_ID}\"
    fieldId: \"PVTSSF_lADOAjf0s84BZnrezhUlFOM\"
    value: { singleSelectOptionId: \"${SCHEDULE_OPTION_ID}\" }
  }) { projectV2Item { id } }
}"
```

Schedule option IDs:

- Now: `1e84189c`
- Next: `9fca00b2`
- Later: `e2149d3e`
- Someday: `fcffa79d`

### Create a New Epic

Invoke the `create-epic` skill. Provide title, body, and the list of
leaf issue numbers to wire as sub-issues.

### Archive a Completed Epic

1. Verify all sub-issues are closed.
2. Invoke `archive-history` skill with type `priority`.
3. Close the Epic issue via `gh issue close`.

## Notes

- **Review-first**: Always check status before updating. Findings inform
  decisions.
- **User control**: No automatic changes — you decide what to update.
- **Board changes are live**: Schedule moves take effect immediately via API.
  No file commit is needed for pure scheduling changes.
- **Undo**: Board moves can be undone by moving the item back. Closed Epics
  can be reopened with `gh issue reopen`.
