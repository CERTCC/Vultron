---
title: manage_github_issue.sh does not support --type flag for setting issue type
type: learning
timestamp: "2026-08-27T00:00:00Z"
source: ISSUE-2520
signal: tooling-issue
---

When creating GitHub issues via `.agents/skills/manage-github-issue/manage_github_issue.sh`,
passing `--type Bug` (or `--type Concern`) fails with "unknown option".
The script only supports `--title`, `--body`, `--label`, and `--parent`.

**Workaround**: set issue type via direct GraphQL after creation:

```bash
ISSUE_NUMBER=$(bash .agents/skills/shared/manage_github_issue.sh ...)
gh api graphql -f query='mutation($id:ID!,$typeId:ID!){
  updateIssue(input:{id:$id,issueTypeId:$typeId}){issue{number}}
}' -f id="<node_id>" -f typeId="<type_node_id>"
```

Or use the full `createIssue` GraphQL mutation with `issueTypeId` in one step.

Type node IDs for CERTCC/Vultron:

- Bug:     `IT_kwDOBSAY_s4A_Wft`
- Concern: `IT_kwDOBSAY_s4BFr3x`

**When to apply**: any `build` or `bugfix` session that needs to DEFER a
pre-existing bug as a properly-typed GitHub issue.
