---
title: update-priorities Reference
---

# Update Priorities — Reference

Technical details for the priority update workflow.

## Project Board Constants

Board IDs are **never hardcoded** — resolve them by name via `board-id.sh`
(see `.agents/skills/shared/README.md`). They rotate when the Schedule field's
options are edited, so any pasted literal drifts stale.

```bash
PROJECT_ID=$(bash .agents/skills/shared/board-id.sh project)
SCHEDULE_FIELD_ID=$(bash .agents/skills/shared/board-id.sh schedule-field)
SCHEDULE_OPTION_ID=$(bash .agents/skills/shared/board-id.sh schedule "${TIER}")  # Focus|Now|Next|Later|Someday
```

## Querying All Board Items

```bash
PROJECT_ID=$(bash .agents/skills/shared/board-id.sh project)
gh api graphql -f query='{
  node(id: "'"$PROJECT_ID"'") {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          id
          content {
            ... on Issue { number title state }
          }
          fieldValueByName(name: "Schedule") {
            ... on ProjectV2ItemFieldSingleSelectValue { name optionId }
          }
        }
      }
    }
  }
}'
```

## Moving an Item Between Tiers

```bash
# Look up item ID by issue number (from items query above)
ITEM_ID="<project item node ID>"

PROJECT_ID=$(bash .agents/skills/shared/board-id.sh project)
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

## Adding an Issue to the Board

Add the issue and set its Schedule in one call via the shared helper, which is
the single source of truth for the project / field / option IDs (accepts
`Focus | Now | Next | Later | Someday`, default `Someday`):

```bash
bash .agents/skills/shared/add-to-project.sh "${ISSUE_NUMBER}" "${SCHEDULE:-Someday}"
```

Do not re-implement the `addProjectV2ItemById` + set-Schedule mutation inline —
that inline duplication is exactly how the option IDs drifted stale.

## Archiving a Completed Epic

1. Verify all sub-issues closed via GraphQL `subIssues` query.
2. Call `uv run append-history priority` via the `archive-history` skill.
3. Close the Epic: `gh issue close <N> --repo CERTCC/Vultron`.

## Error Handling

### Item Not on Board

If an issue referenced by the user is not in Project #24, offer to add it
with `Schedule=Someday` first.

### API Authentication

```text
❌ GraphQL API error: Must have push access to repository
   Action: Verify GITHUB_TOKEN has `project` scope
```

## Integration with check-priority-status

Typical workflow:

1. Run `check-priority-status` → get status report
2. Identify items to reschedule, promote from triage, etc.
3. Run `update-priorities` → apply changes
4. Repeat as needed

The skills do **not chain automatically**; run them sequentially.
