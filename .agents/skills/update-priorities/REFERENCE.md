---
title: update-priorities Reference
---

# Update Priorities — Reference

Technical details and implementation guidance for the priority update workflow.

## Data Model

### Priority Group Structure

```yaml
Priority: <number>
Title: <string>
Description: <string> (markdown, may span multiple lines)
Issues:
  - Epic (root issue, typically)
  - Related issues (sub-issues, linked work)
Dependencies:
  Prerequisite: <issue_link>
  Blocks: [<issue_list>]
```text

### Parsing

When loading `plan/PRIORITIES.md`:

1. Parse heading `## Priority <N> — <Title>` → extract number and title
2. Read text until next heading or EOF → description (may include notes, PR links)
3. Extract issue links: `#123`, `[link text](#123)`, or full URLs
4. Parse dependency annotations:
   - `Prerequisite: #<N>` or `Prerequisite: [text](#N)`
   - `Blocks: #<N>, #<M>` (comma-separated)
5. Build structured list of priority groups

### Modification

When applying changes:

1. Reconstruct markdown from modified structure
2. Preserve formatting (indentation, list markers)
3. Validate section order (priority numbers ascending)
4. Write backup before overwriting

## Workflows in Detail

### Add New Priority

1. **Prompt user** for key info:
   - Root issue link (e.g., epic #464)
   - Title and description
   - Related issues (sub-issues, PRs)
   - Dependencies: "Does this block or depend on other priorities?"
2. **Determine priority number**:
   - Ask: "Higher or lower priority than [group X]?"
   - Calculate gap: suggest a number between existing boundaries
   - Validate: confirm no duplicates after insertion
3. **Construct markdown section**:

   ```markdown
   ## Priority <N> — <Title>

   <Description>

   - Epic: [text](#<epic_number>)
   - Related: #<related_1>, #<related_2>

   Prerequisite: #<prereq>

   ```text

4. **Insert at correct position** (maintain ascending order)
5. **Validate**, preview, commit

### Refine Existing Group

1. **Select priority** from interactive list
2. **Choose action**:
   - Update title or description
   - Add/remove linked issues
   - Update dependencies
   - Change priority number (re-sort)
3. **Gather changes** and apply to structure
4. **Validate**, preview, commit

### Remove Priority

1. **Confirm all issues closed**:
   - Query GitHub: verify every linked issue is closed
   - If any open issues remain, abort (user must close or move to new priority first)
2. **Archive to history**:
   - Auto-generate history entry via `uv run append-history priority`
   - Entry will be written to `plan/history/YYMM/priority/<priority_id>.md`
3. **Remove from PRIORITIES.md** and commit

## Validation

### GitHub API Checks

For each issue link:

```graphql
GET /repos/CERTCC/Vultron/issues/<number>
→ Check: state == "open" (for ADD/REFINE operations)
→ Check: epic_type or issue exists (verify link structure)
```text

Epic sub-issue query (GraphQL):

```graphql
query {
  repository(owner: "CERTCC", name: "Vultron") {
    issue(number: <N>) {
      children: linkedIssues(first: 100, direction: OUT) {
        edges { node { number, title } }
      }
    }
  }
}
```text

### Format Validation

- Issue links: `#<digits>` or `https://github.com/CERTCC/Vultron/issues/<digits>`
- Priority numbers: positive integers, ascending
- No duplicate links across priority groups
- Prerequisite issues: must exist and be open

### Markdown Validation

- Headings: `## Priority <N> — <Title>`
- Lists: consistent bullet markers (dash or asterisk)
- Links: valid markdown syntax, no broken references

### Error Handling

If validation fails:

```text
❌ Issue #999 not found (404)
   Fix: Correct the issue number, or skip this link

❌ Issue #440 is already linked to Priority 475
   Fix: Remove from Priority 475 first, or remove from this group

❌ Priority number 475 already exists
   Fix: Choose a different number
```text

Offer to **fix, skip, or abort**.

## Preview & Diff

Before writing:

```markdown
--- plan/PRIORITIES.md (before)
+++ plan/PRIORITIES.md (after)

## Priority 475 — Participant Case Replica Safety
...
-  - [#440](https://github.com/CERTCC/Vultron/issues/440)
+  - [#440](https://github.com/CERTCC/Vultron/issues/440) — Core rules
+  - [#500](https://github.com/CERTCC/Vultron/issues/500) — Validation tests

## Priority 480 — New Feature (NEW)
+
+Description here...
```text

## Commit Message

Auto-generated or user-provided. Include:

- Action: "Add Priority <N>", "Refine Priority <N>", "Archive Priority <N>"
- Summary of changes
- Co-author trailer

Example:

```

Add Priority 480 — Performance Optimization

Addresses uncovered issues #550, #551, #552.
Depends on Priority 475 (case replica safety).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

```text

## Integration with check-priority-status

**Typical workflow**:

1. Run `check-priority-status` → get status report
2. Identify uncovered issues, empty priorities, stale work
3. Run `update-priorities` → add new groups or refine existing ones
4. Repeat as needed

The skills do **not chain automatically**; user must run them sequentially and decide when updates are warranted based on findings.

## Advanced Features

### Batch Import

Import priorities from structured input (CSV, JSON):

```json
[
  {
    "priority": 480,
    "title": "Performance Optimization",
    "description": "...",
    "issues": [550, 551, 552],
    "prerequisites": [475]
  }
]
```text

### Priority Renumbering

If gaps have accumulated (e.g., 470, 475, 476, 500):

- Offer to consolidate (470, 475, 476, 477)
- Validate no external references (e.g., ADR documents)
- Generate commit

### Export

Save current state to JSON or CSV for external tools (project boards, reports):

```bash
update-priorities --export json > priorities.json
```text

### History Query

View archived priorities (completed work):

```bash
update-priorities --show-history
```text

