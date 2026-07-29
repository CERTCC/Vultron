---
title: update-priorities Reference
---

# Update Priorities — Reference

Technical details for the priority update workflow.

## Project Board Constants

| Name | Value |
|---|---|
| Project node ID | `PVT_kwDOAjf0s84BZnre` |
| Schedule field ID | `PVTSSF_lADOAjf0s84BZnrezhUlFOM` |
| Focus option ID | `6bca50d7` |
| Now option ID | `22e6679d` |
| Next option ID | `1c1ed63d` |
| Later option ID | `520032ef` |
| Someday option ID | `a890eacc` |

## Querying All Board Items

```bash
gh api graphql -f query='{
  node(id: "PVT_kwDOAjf0s84BZnre") {
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

gh api graphql -f query="mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    itemId: \"${ITEM_ID}\"
    fieldId: \"PVTSSF_lADOAjf0s84BZnrezhUlFOM\"
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
