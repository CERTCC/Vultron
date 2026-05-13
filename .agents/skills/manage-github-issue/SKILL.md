---
name: manage-github-issue
description: >
  Create or update a GitHub Issue with structured relationships (parent/child
  sub-issues, blocking/blocked-by) using the GraphQL API. Idempotent for all
  relationship wiring. Strips legacy body-text markers ("Blocked by #N",
  "Blocks #N", "Parent: #N") when structured relationships are applied. Call
  this skill wherever any other skill creates or modifies issues that carry
  relationships.
---

# Skill: Manage GitHub Issue

Create or update a GitHub Issue and wire structured relationships via GraphQL.
All relationship operations are **idempotent** — existing relationships are
checked and skipped before adding. When structured relationships are wired,
legacy body-text markers are stripped from the issue body.

**Never embed relationship information in the issue body as text.**
Use the structured GitHub relationship APIs documented here instead.

## Inputs

| Parameter | Default | Description |
|---|---|---|
| `REPO` | `CERTCC/Vultron` | Repository in `owner/name` format |
| `ISSUE_NUMBER` | — | Issue # to update; omit to create a new issue |
| `TITLE` | — | Issue title (required for create, optional for update) |
| `BODY` | — | Issue body markdown |
| `LABELS` | — | Comma-separated label names (e.g. `group:unscheduled,size:M`) |
| `ASSIGNEES` | — | Comma-separated GitHub usernames |
| `ISSUE_TYPE_ID` | — | GraphQL node ID of the issue type (see Constants) |
| `PARENT_ISSUE` | — | Parent issue number (sets parent/child sub-issue link) |
| `BLOCKED_BY` | — | Space-separated issue numbers that block this issue |
| `BLOCKS` | — | Space-separated issue numbers this issue blocks |
| `SUB_ISSUES` | — | Space-separated issue numbers to wire as children |

## Outputs

- The issue number is printed on **stdout** so callers can capture it.
- Progress and status messages go to **stderr**.

## Quick Start (helper script)

For the common case, use the bundled helper script. It handles all steps
including idempotency checks.

```bash
# Create a new issue with a parent and one blocker
ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "Implement X" \
  --body "$(cat body.md)" \
  --label "group:unscheduled,size:M" \
  --parent 42 \
  --blocked-by 50)

# Update an existing issue and wire blocked-by relationships
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --issue-number 99 \
  --blocked-by "50 51" \
  --blocks "100 101" \
  --clean-body

# Wire sub-issues onto a parent
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --issue-number 42 \
  --sub-issue 99 \
  --sub-issue 100
```

## Workflow

### Step 0 — Resolve node IDs

All GraphQL mutations require node IDs, not issue numbers.

```bash
# Resolve node IDs for this issue and any related issues in one query.
# Replace <N>, <M>, <P> with actual issue numbers.
gh api graphql -f query='
{
  repository(owner:"CERTCC", name:"Vultron") {
    repo_id: id
    this_issue: issue(number: <N>) { id number }
    blocker1:  issue(number: <M>) { id number }
    parent:    issue(number: <P>) { id number }
  }
}'
```

Store the `id` values for use in subsequent mutations.

### Step 1 — Create or update the issue

#### Creating a new issue

Use `createIssue`. If `PARENT_ISSUE` is known at creation time, set
`parentIssueId` directly — this is more efficient than a separate
`addSubIssue` call.

```bash
TITLE_JSON=$(printf '%s' "${TITLE}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "${BODY}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${ISSUE_TYPE_ID}\"       # omit if no specific type
    parentIssueId: \"${PARENT_NODE_ID}\"    # omit if no parent
  }) {
    issue { number id url }
  }
}"
```

After creating, apply labels by name (label name lookup is handled by the
REST API):

```bash
gh issue edit "${ISSUE_NUMBER}" \
  --repo "${REPO}" \
  --add-label "${LABELS}"
```

#### Updating an existing issue

```bash
gh api graphql -f query="
mutation {
  updateIssue(input: {
    id: \"${ISSUE_NODE_ID}\"
    title: ${TITLE_JSON}    # omit fields you are not changing
    body: ${BODY_JSON}
  }) {
    issue { number id url }
  }
}"
```

### Step 2 — Wire parent relationship (if not set at create time)

Skip this step if `parentIssueId` was already provided in `createIssue`.

**Idempotency check** — skip if parent is already set:

```bash
EXISTING_PARENT=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${ISSUE_NUMBER}"') { parent { number } }
  }
}' | python3 -c "
import json, sys
d = json.load(sys.stdin)
p = d['data']['repository']['issue']['parent']
print(p['number'] if p else '')
")
```

Wire the parent only if `EXISTING_PARENT` is empty or differs:

```bash
gh api graphql -f query="
mutation {
  addSubIssue(input: {
    issueId: \"${PARENT_NODE_ID}\"
    subIssueId: \"${CHILD_NODE_ID}\"
  }) {
    issue { number }
    subIssue { number }
  }
}"
```

### Step 3 — Wire blocked-by relationships (idempotent)

For each issue number `B` in `BLOCKED_BY` ("this issue is blocked by B"):

**Idempotency check** — query existing blockers:

```bash
EXISTING_BLOCKERS=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${ISSUE_NUMBER}"') {
      blockedBy(first: 100) { nodes { number } }
    }
  }
}' | python3 -c "
import json, sys
nodes = json.load(sys.stdin)['data']['repository']['issue']['blockedBy']['nodes']
print(' '.join(str(n['number']) for n in nodes))
")
```

Wire only if `B` is not already in `EXISTING_BLOCKERS`:

```bash
# issueId = the blocked issue (this issue)
# blockingIssueId = the blocker (B)
gh api graphql -f query="
mutation {
  addBlockedBy(input: {
    issueId: \"${THIS_NODE_ID}\"
    blockingIssueId: \"${B_NODE_ID}\"
  }) {
    issue { number }
    blockingIssue { number }
  }
}"
```

### Step 4 — Wire blocking relationships (idempotent)

For each issue number `T` in `BLOCKS` ("this issue blocks T"):

This is the mirror of Step 3 — `T` is blocked by this issue:

**Idempotency check** — query T's existing blockers:

```bash
EXISTING_BLOCKERS_OF_T=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${T}"') {
      blockedBy(first: 100) { nodes { number } }
    }
  }
}' | python3 -c "
import json, sys
nodes = json.load(sys.stdin)['data']['repository']['issue']['blockedBy']['nodes']
print(' '.join(str(n['number']) for n in nodes))
")
```

Wire only if THIS issue is not already in `EXISTING_BLOCKERS_OF_T`:

```bash
# issueId = the blocked issue (T)
# blockingIssueId = this issue
gh api graphql -f query="
mutation {
  addBlockedBy(input: {
    issueId: \"${T_NODE_ID}\"
    blockingIssueId: \"${THIS_NODE_ID}\"
  }) {
    issue { number }
    blockingIssue { number }
  }
}"
```

### Step 5 — Wire sub-issues (idempotent)

For each issue number `C` in `SUB_ISSUES` ("C is a child of this issue"):

**Idempotency check** — query existing sub-issues:

```bash
EXISTING_SUB=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${ISSUE_NUMBER}"') {
      subIssues(first: 100) { nodes { number } }
    }
  }
}' | python3 -c "
import json, sys
nodes = json.load(sys.stdin)['data']['repository']['issue']['subIssues']['nodes']
print(' '.join(str(n['number']) for n in nodes))
")
```

Wire only if `C` is not already in `EXISTING_SUB`:

```bash
gh api graphql -f query="
mutation {
  addSubIssue(input: {
    issueId: \"${THIS_NODE_ID}\"
    subIssueId: \"${C_NODE_ID}\"
  }) {
    issue { number }
    subIssue { number }
  }
}"
```

### Step 6 — Clean legacy body-text relationship markers

When any structured relationship is wired (Steps 2–5), also strip matching
legacy text from the issue body. Fetch the current body, remove the patterns,
and update via `updateIssue`.

Patterns to remove (case-insensitive, full lines):

| Pattern | Example |
|---|---|
| `Blocked by:?\s+#\d+.*` | `Blocked by #42` |
| `Blocks:?\s+#\d+.*` | `Blocks #50, #51` |
| `Parent:?\s+(issue:?\s*)?#\d+.*` | `Parent: #10` |
| `Sub-issues?:?\s+#\d+.*` | `Sub-issues: #11, #12` |

```bash
# Fetch current body
CURRENT_BODY=$(gh issue view "${ISSUE_NUMBER}" \
  --repo "${REPO}" --json body --jq '.body')

# Strip legacy markers
CLEANED_BODY=$(printf '%s' "${CURRENT_BODY}" | python3 -c "
import sys, re
body = sys.stdin.read()
patterns = [
    r'(?im)^\s*blocked[ -]by:?\s+#\d+[^\n]*\n?',
    r'(?im)^\s*blocks:?\s+#\d+[^\n]*\n?',
    r'(?im)^\s*parent:?\s+(?:issue:?\s*)?#\d+[^\n]*\n?',
    r'(?im)^\s*sub-?issues?:?\s+#\d+[^\n]*\n?',
]
for p in patterns:
    body = re.sub(p, '', body)
print(body.strip())
")

# Update only if body changed
if [ "${CLEANED_BODY}" != "${CURRENT_BODY}" ]; then
  CLEANED_JSON=$(printf '%s' "${CLEANED_BODY}" \
    | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
  gh api graphql -f query="
  mutation {
    updateIssue(input: {
      id: \"${ISSUE_NODE_ID}\"
      body: ${CLEANED_JSON}
    }) { issue { number } }
  }"
  echo "  Stripped legacy body-text relationship markers" >&2
fi
```

## Conventions

- Always use `manage-github-issue` (or its helper script) when creating or
  updating issues that carry relationships. Never write `Blocked by #N`,
  `Blocks #N`, or `Parent: #N` into an issue body.
- When detecting blockers before claiming work (e.g., in the `build` skill),
  query `blockedBy { nodes { number } }` via GraphQL — do **not** parse the
  issue body for text markers.
- `BLOCKS` and `BLOCKED_BY` are inverses: setting `BLOCKS 50` on issue 42 is
  equivalent to setting `BLOCKED_BY 42` on issue 50. The helper script accepts
  both for convenience.

## Constants

These are the stable node IDs for `CERTCC/Vultron`. If the repository is
transferred or recreated, re-query using the commands in
**API Discovery** below.

| Name | Value |
|---|---|
| Repo node ID | `R_kgDOIn77fA` |
| Task issue type ID | `IT_kwDOAjf0s84AcFLo` |
| Epic issue type ID | `IT_kwDOAjf0s84B_E1A` |

## API Discovery

Use these commands to re-discover node IDs and mutation names if they change.

### Re-query repository node ID

```bash
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") { id }
}'
```

### Re-query issue type IDs

```bash
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issueTypes(first:10) { nodes { id name } }
  }
}'
```

### Re-discover blocking/sub-issue mutation names

```bash
gh api graphql -f query='{
  __schema {
    mutationType {
      fields { name }
    }
  }
}' | python3 -c "
import json, sys
fields = json.load(sys.stdin)['data']['__schema']['mutationType']['fields']
for f in fields:
    if any(k in f['name'].lower() for k in ['block','sub','depend']):
        print(f['name'])
"
```

### Inspect mutation input fields

```bash
# e.g., for AddBlockedByInput:
gh api graphql -f query='{
  __type(name:"AddBlockedByInput") {
    inputFields { name description type { name kind ofType { name } } }
  }
}'
```

### Query relationships on an issue

```bash
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: 42) {
      parent          { number title }
      subIssues(first:50) { nodes { number title } }
      blockedBy(first:50) { nodes { number title } }
      blocking(first:50)  { nodes { number title } }
    }
  }
}'
```
