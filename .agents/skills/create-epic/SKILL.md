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

Use the bash helper script in this skill's directory. It creates the Epic
(with the correct Epic issue type), then adds it to Project #24 and sets its
Schedule via the shared `add-to-project.sh` helper — so board IDs live in
exactly one place:

```bash
EPIC_NUMBER=$(.agents/skills/create-epic/create_epic.sh \
  "${EPIC_TITLE}" "${EPIC_BODY}" "${SCHEDULE:-Someday}")
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

### Step 4 — Apply `needs-decomposition` label

Every newly created Epic starts without sub-issues. Apply the label
immediately so the project board and `build` can identify it:

```bash
gh issue edit "${EPIC_NUMBER}" --repo CERTCC/Vultron \
  --add-label "needs-decomposition"
```

Skip this step if `LEAF_ISSUES` is non-empty (sub-issues were linked in
Step 3, so the Epic is not empty).

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
- Board IDs (project node, Schedule field, Schedule option IDs including
  `Focus`) are **not** duplicated here — they live in one place,
  `.agents/skills/shared/README.md`, and are applied by
  `.agents/skills/shared/add-to-project.sh`, which `create_epic.sh` calls.
