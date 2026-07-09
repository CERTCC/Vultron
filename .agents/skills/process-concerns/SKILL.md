---
name: process-concerns
description: >
  Batch-process docs/reference/codebase/CONCERNS.md into GitHub Concern-type
  issues. Optionally runs a focused acquire-codebase-knowledge scan first.
  Deduplicates against existing open Concern issues — updating the body and
  appending a refresh comment on matches, creating new issues otherwise.
  Handles the [ASK USER] Questions section interactively. Adds all new
  issues to Project #24 with Schedule=Someday. Does not write to specs/,
  notes/, or open a PR. Use when you want to turn a codebase scan into a
  set of tracked GitHub issues.
---

# Skill: Process Concerns

Convert `docs/reference/codebase/CONCERNS.md` into GitHub `type:Concern`
issues. One issue per table row. Deduplicates against open Concern issues
before creating anything.

## Constants

```text
REPO           = CERTCC/Vultron
REPO_NODE_ID   = R_kgDOIn77fA
CONCERN_TYPE   = IT_kwDOAjf0s84B_2VT
TASK_TYPE      = IT_kwDOAjf0s84AcFLo
```

---

## Workflow

### Phase 0 — Decide on Scan Freshness

Ask the user (via `ask_user`):

> Should I run a fresh `acquire-codebase-knowledge` scan (focused on
> CONCERNS.md) to get the latest snapshot, or use the existing
> `docs/reference/codebase/CONCERNS.md` as-is?

Choices:

1. **Run a fresh focused scan (Recommended)**
2. **Use the existing CONCERNS.md**

If the user chooses a fresh scan, invoke `acquire-codebase-knowledge` with
focus area `CONCERNS.md` only (do not regenerate the other six documents).
After the scan completes, proceed with the newly generated file.

### Phase 1 — Load Situation Awareness

List **all open Concern-type issues** in the repository and display a summary
table so the agent has full context before creating or updating anything:

```bash
gh issue list \
  --repo CERTCC/Vultron \
  --state open \
  --limit 200 \
  --json number,title,issueType,labels \
  --jq '.[] | select(.issueType.name == "Concern") | "#\(.number): \(.title)"'
```

Store the resulting list (numbers + titles) for deduplication in Phase 3.

### Phase 2 — Parse CONCERNS.md

Read `docs/reference/codebase/CONCERNS.md`. Extract all rows from the
following sections as individual concern items:

| Section | Row key column |
|---|---|
| Top Risks | Concern |
| Technical Debt | Debt item |
| Security Concerns | Risk |
| Performance and Scaling Concerns | Concern |
| Fragile/High-Churn Areas | Area |
| `[ASK USER]` Questions | *(handled separately — see Phase 4)* |

For each row, collect all available columns (Severity, Evidence, Impact,
Suggested action, etc.) to populate the issue body.

### Phase 3 — Create or Update Issues (all sections except `[ASK USER]`)

For each concern item from Phase 2 (excluding the `[ASK USER]` section):

#### 3a — Deduplication Check

Compare the concern's key text against the titles of existing open Concern
issues (loaded in Phase 1). Use semantic similarity — titles do not have to
be identical, but the subject matter must clearly match.

- **Match found** → proceed to **3b (Update)**.
- **No match** → proceed to **3c (Create)**.

#### 3b — Update Existing Issue

1. Synthesize a current, descriptive title from the row data (if notably
   different from the existing title, update it; otherwise leave it).
2. Rebuild the issue body from the concern template (see **Issue Body Format**
   below) using the latest scan data.
3. Edit the issue body:

   ```bash
   gh issue edit "${ISSUE_NUMBER}" \
     --repo CERTCC/Vultron \
     --body "$(cat body.md)"
   ```

4. Append a refresh comment:

   ```bash
   gh issue comment "${ISSUE_NUMBER}" \
     --repo CERTCC/Vultron \
     --body "♻️ Refreshed from codebase scan — $(date +%Y-%m-%d)."
   ```

#### 3c — Create New Issue

Synthesize a short, descriptive title from the row data. Build a body
following the **Issue Body Format** below. Ensure labels exist, create the
issue, then apply labels:

```bash
TITLE_JSON=$(printf '%s' "${TITLE}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "${BODY}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

# Ensure concern label exists before applying it
gh label create "concern" \
  --repo CERTCC/Vultron \
  --description "Technical risk, debt, or fragile area" \
  --color "#d93f0b" 2>/dev/null || true

RESULT=$(gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${CONCERN_TYPE}\"
  }) {
    issue { number id url }
  }
}")
ISSUE_NUMBER=$(echo "${RESULT}" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['number'])")
ISSUE_NODE_ID=$(echo "${RESULT}" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['id'])")

gh issue edit "${ISSUE_NUMBER}" \
  --repo CERTCC/Vultron \
  --add-label "concern"

# Add to Project #24 with Schedule=Someday
ITEM_ID=$(gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    contentId: \"${ISSUE_NODE_ID}\"
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

echo "Created concern issue #${ISSUE_NUMBER}"
```

### Phase 4 — Handle `[ASK USER]` Questions

For each question in the `[ASK USER]` Questions section of CONCERNS.md,
surface it to the user via `ask_user` (one question at a time). Based on the
user's response:

- If the question reveals a **Concern** (a technical risk or gap) →
  create a `type:Concern` issue using the same flow as Phase 3c.
- If the question reveals a **Task** (a decision or action item) →
  create a `type:Task` issue and add to Project #24 with Schedule=Someday:

  ```bash
  TITLE_JSON=$(printf '%s' "${TITLE}" \
    | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
  BODY_JSON=$(printf '%s' "${BODY}" \
    | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
  RESULT=$(gh api graphql -f query="
  mutation {
    createIssue(input: {
      repositoryId: \"${REPO_NODE_ID}\"
      title: ${TITLE_JSON}
      body: ${BODY_JSON}
      issueTypeId: \"${TASK_TYPE}\"
    }) {
      issue { number id url }
    }
  }")
  TASK_NUMBER=$(echo "${RESULT}" | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['number'])")
  TASK_NODE_ID=$(echo "${RESULT}" | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['id'])")
  # Then add to project with Schedule=Someday (same snippet as above)
  ```

- If the question is resolved by the user's answer (no issue needed) →
  skip issue creation and note the decision in the conversation.

### Phase 5 — Summary

After processing all rows and `[ASK USER]` items, print a summary table:

```text
| # | Title | Action |
|---|-------|--------|
| 42 | ... | created |
| 17 | ... | updated |
| —  | "Which HTTP entrypoint..." | closed (decision: X) |
```

---

## Issue Body Format

All Concern issues use the structure from `.github/ISSUE_TEMPLATE/concern.md`:

```markdown
## Summary

<one or two sentences synthesized from the row's key column and impact text>

## Category

- [x] <checked item matching the CONCERNS.md section>
- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [ ] Other

## Severity

<high / medium / low — from the row's Severity column, or "medium" if absent>

## Evidence

<file paths from the Evidence column, one per bullet>

- `path/to/file.py`

## Impact if Ignored

<from the Impact / "Risk if ignored" column>

## Suggested Action

<from the "Suggested action" / "Suggested fix" / "Suggested improvement"
column>
```

Map CONCERNS.md section names to Category checkboxes:

| CONCERNS.md section | Category checkbox |
|---|---|
| Top Risks | Top risk |
| Technical Debt | Technical debt |
| Security Concerns | Security |
| Performance and Scaling Concerns | Performance / scaling |
| Fragile/High-Churn Areas | Fragile / high-churn area |

---

## Constraints

- Do **not** write to `specs/`, `notes/`, `AGENTS.md`, or open a PR.
- Do **not** delete entries from `CONCERNS.md` — it is a generated file.
- Do **not** assign a `size:` label.
- Do **not** add a parent issue or link issues to each other.
- Always check for existing open Concern issues before creating a new one.
- Use `ask_user` for all user-facing questions; never ask in plain text.

## Checklist

- [ ] User chose scan freshness (fresh focused scan or use existing)
- [ ] All open Concern issues loaded for situation awareness
- [ ] CONCERNS.md parsed into per-row items
- [ ] Each item deduplicated against open issues (by title similarity)
- [ ] Matched items: body updated + refresh comment added
- [ ] New items: Concern issue created with `concern` label, added to
      Project #24 with Schedule=Someday
- [ ] `[ASK USER]` questions surfaced via `ask_user`; issues created or
      decisions noted
- [ ] Summary table printed
