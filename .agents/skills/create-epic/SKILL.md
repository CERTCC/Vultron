---
name: create-epic
description: >
  Create a GitHub Epic issue for a priority group and wire existing leaf
  issues as its sub-issues. Uses the GitHub Epic issue type (via GraphQL)
  and the GraphQL addSubIssue mutation. Invoke this skill whenever a priority
  group needs an Epic created or updated (PAD-02-008, PAD-02-009).
---

# Skill: Create Epic

Create a GitHub Epic issue for a priority group and link leaf issues as
sub-issues. This skill is the canonical way to create Epics to ensure
consistent use of the `Epic` issue type, `group:` label, and sub-issue wiring.

## Inputs

- `GROUP_LABEL`: the `group:` label slug, e.g. `architecture-hardening`
- `EPIC_TITLE`: one-line Epic title, e.g.
  `Architecture Hardening (Phase 2): Import violations and BT sync`
- `EPIC_BODY`: multi-line body text (summary, open tasks list, rationale)
- `LEAF_ISSUES`: space-separated issue numbers to link as sub-issues,
  e.g. `428 439 429`
- `REPO`: `CERTCC/Vultron` (default)

## Workflow

### Step 1 — Verify no existing open Epic

Query GitHub for existing open Epics in this group to avoid duplicates
(PAD-02-008):

```bash
gh issue list --repo CERTCC/Vultron \
  --label "group:${GROUP_LABEL}" \
  --state open \
  --json number,title,issueType \
  | python3 -c "
import json, sys
issues = json.load(sys.stdin)
epics = [i for i in issues if (i.get('issueType') or {}).get('name') == 'Epic']
if len(epics) > 1:
    nums = ', '.join(str(e['number']) for e in epics)
    print(f'ERROR: {len(epics)} open Epics found for this group: {nums}')
    print('Resolve to exactly one open Epic before proceeding (PAD-02-008).')
    raise SystemExit(1)
elif len(epics) == 1:
    print('EPIC_EXISTS:', epics[0]['number'])
else:
    print('NO_EPIC')
"
```

If multiple open Epics are found, stop and report the conflict — do **not**
silently pick one. Close or merge the duplicate Epics manually until exactly
one remains.

If exactly one Epic already exists, skip Step 2 and proceed to Step 3 (link any
unparented leaf issues).

### Step 2 — Create the Epic issue via GraphQL

Use the bash helper script in this skill's directory:

```bash
.agents/skills/create-epic/create_epic.sh \
  "${GROUP_LABEL}" \
  "${EPIC_TITLE}" \
  "${EPIC_BODY}"
```

The script prints the new issue number on stdout (e.g. `443`). Capture it:

```bash
EPIC_NUMBER=$(.agents/skills/create-epic/create_epic.sh \
  "${GROUP_LABEL}" "${EPIC_TITLE}" "${EPIC_BODY}")
echo "Created Epic #${EPIC_NUMBER}"
```

### Step 3 — Link leaf issues as sub-issues

Leaf issues must be linked via the GraphQL `addSubIssue` mutation (the REST
sub-issues API is not available for this repo). First, resolve the node IDs
for the Epic and each leaf issue:

```bash
# Get node IDs for the Epic and leaf issues
gh api graphql -f query='{ repository(owner:"CERTCC", name:"Vultron") {
  epic: issue(number: <EPIC_NUMBER>) { id }
  i1: issue(number: <LEAF_1>) { id }
  i2: issue(number: <LEAF_2>) { id }
} }'
```

Then link each leaf:

```bash
gh api graphql -f query='
mutation {
  addSubIssue(input: {
    issueId: "<EPIC_NODE_ID>"
    subIssueId: "<LEAF_NODE_ID>"
  }) {
    issue { number }
    subIssue { number }
  }
}'
```

### Step 4 — Update PRIORITIES.md

Record the Epic issue number next to the group heading in
`plan/PRIORITIES.md` (PAD-02-010). Change the heading from:

```markdown
## Priority NNN: Title
```

to:

```markdown
## Priority NNN — Epic #M: Title
```

**Note**: `PRIORITIES.md` may only be modified by the `review-priorities`
skill or a human. If invoking `create-epic` from another skill, pass the
Epic number back to the caller and let `review-priorities` perform the
PRIORITIES.md update.

### Step 5 — Return Epic number

Output the Epic issue number so the caller can record it:

```bash
echo "${EPIC_NUMBER}"
```

## Constraints

- Never create more than one open Epic per `group:` label (PAD-02-008).
- Always check for an existing open Epic before creating a new one.
- The `Epic` issue type ID for `CERTCC/Vultron` is `IT_kwDOAjf0s84B_E1A`.
  If this ID changes (e.g. after repo transfer), re-query:

  ```bash
  gh api graphql -f query='{ repository(owner:"CERTCC", name:"Vultron") {
    issueTypes(first:10) { nodes { id name } } } }'
  ```

- The repo node ID for `CERTCC/Vultron` is `R_kgDOIn77fA`.
- Do not call this skill for groups with fewer than 2 open leaf issues
  (PAD-02-008).
