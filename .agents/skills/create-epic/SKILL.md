---
name: create-epic
description: >
  Create a GitHub Epic issue for a priority group and wire existing leaf
  issues as its sub-issues. Uses the GitHub Epic issue type (via GraphQL)
  and the GraphQL addSubIssue mutation. Invoke this skill whenever a
  thematic group needs an Epic created or updated.
---

# Skill: Create Epic

Create a GitHub Epic issue for a thematic group and link leaf issues as
sub-issues. This skill is the canonical way to create Epics to ensure
consistent use of the `Epic` issue type and sub-issue wiring.

## Inputs

- `EPIC_TITLE`: one-line Epic title, e.g.
  `Architecture Hardening (Phase 2): Import violations and BT sync`
- `EPIC_BODY`: multi-line body text (summary, open tasks list, rationale)
- `LEAF_ISSUES`: space-separated issue numbers to link as sub-issues,
  e.g. `428 439 429`
- `SCHEDULE`: initial Schedule value for Project #24 — one of `Now`, `Next`,
  `Later`, `Someday` (default: `Someday`)
- `REPO`: `CERTCC/Vultron` (default)

## Workflow

### Step 1 — Verify no existing open Epic for this theme

Search for open Epics with similar titles to avoid duplicates:

```bash
gh issue list --repo CERTCC/Vultron \
  --state open \
  --json number,title,issueType \
  | python3 -c "
import json, sys
issues = json.load(sys.stdin)
epics = [i for i in issues if (i.get('issueType') or {}).get('name') == 'Epic']
for e in epics:
    print(f'  #{e[\"number\"]}: {e[\"title\"]}')
"
```

If a matching Epic already exists, skip Step 2 and proceed to Step 3.

### Step 2 — Create the Epic issue via GraphQL

Use the bash helper script in this skill's directory:

```bash
EPIC_NUMBER=$(.agents/skills/create-epic/create_epic.sh \
  "${EPIC_TITLE}" "${EPIC_BODY}")
echo "Created Epic #${EPIC_NUMBER}"
```

### Step 3 — Link leaf issues as sub-issues

Use the `manage-github-issue` skill to wire each leaf issue as a sub-issue
of the Epic. All wiring is idempotent — already-linked issues are skipped.

```bash
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --issue-number "${EPIC_NUMBER}" \
  --sub-issue <LEAF_1> \
  --sub-issue <LEAF_2> \
  --sub-issue <LEAF_3>
```

### Step 4 — Add Epic to Project #24 with Schedule

```bash
# Get Epic node ID
EPIC_NODE_ID=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${EPIC_NUMBER}"') { id }
  }
}' --jq '.data.repository.issue.id')

# Add to project
ITEM_ID=$(gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    contentId: \"${EPIC_NODE_ID}\"
  }) { item { id } }
}" --jq '.data.addProjectV2ItemById.item.id')

# Set Schedule field (Now=1e84189c Next=9fca00b2 Later=e2149d3e Someday=fcffa79d)
SCHEDULE_ID="fcffa79d"  # default: Someday
gh api graphql -f query="mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    itemId: \"${ITEM_ID}\"
    fieldId: \"PVTSSF_lADOAjf0s84BZnrezhUlFOM\"
    value: { singleSelectOptionId: \"${SCHEDULE_ID}\" }
  }) { projectV2Item { id } }
}" >/dev/null
echo "  Added to Project #24 with Schedule=${SCHEDULE}"
```

### Step 5 — Return Epic number

```bash
echo "${EPIC_NUMBER}"
```

## Constraints

- Always check for an existing open Epic before creating a new one.
- The `Epic` issue type ID for `CERTCC/Vultron` is `IT_kwDOAjf0s84B_E1A`.
  If this ID changes (e.g. after repo transfer), re-query:

  ```bash
  gh api graphql -f query='{ repository(owner:"CERTCC", name:"Vultron") {
    issueTypes(first:10) { nodes { id name } } } }'
  ```

- The repo node ID for `CERTCC/Vultron` is `R_kgDOIn77fA`.
- Project #24 node ID: `PVT_kwDOAjf0s84BZnre`
- Schedule field ID: `PVTSSF_lADOAjf0s84BZnrezhUlFOM`
- Schedule option IDs: `Now=1e84189c`, `Next=9fca00b2`, `Later=e2149d3e`, `Someday=fcffa79d`
