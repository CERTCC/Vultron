---
name: update-plan
description: >
  Perform a gap analysis between current specs/notes and the codebase, then
  create GitHub Issues for any untracked gaps and add them to Project #24.
  Observations and open questions go directly to notes/ files. Use after
  learn or `plan-issue` has updated specs/notes, and before running build.
---

# Skill: Update Plan

Perform a gap analysis between the current specifications, design notes, and
the actual codebase, then create GitHub Issues for any untracked gaps.

**Constraint**: Do not write new tasks to the plan — all new work items MUST be
GitHub Issues. Do not change
code, tests, `specs/`, or `notes/` (except when writing gap-analysis
observations). Do **not** write to `plan/incoming/learnings/` — that directory
is reserved for `build` and `bugfix`.

**Trigger**: Use after `learn` or `plan-issue` has updated specs or notes,
to translate those changes into concrete GitHub Issues. Also run periodically
to keep open Issues aligned with the codebase.

## Quick Start

1. Invoke `orient-agent` then `deepen-context` to load all specs and context.
2. Run a gap analysis: compare `specs/` + `notes/` against `vultron/` and
   `test/`.
3. For each gap, create a GitHub Issue (added to Project #24 with
   Schedule=Someday) rather than a plan entry.
4. Write any significant observations or open questions directly to the
   appropriate `notes/*.md` file (not to `plan/incoming/learnings/`).
5. Invoke `commit`.

## Workflow

### Phase 1 — Load Context

Invoke the `orient-agent` skill, then `deepen-context` to load all specs,
relevant plan files, docs/adr/, notes/, AGENTS.md, and scan vultron/ and test/.

To understand what has recently been completed and avoid re-adding finished
work, run `uv run show-history --month YYMM` (replacing `YYMM` with the
current year-month, e.g. `2604`) to see what has recently been completed.
Open individual entry files only when their titles suggest relevant context.

### Phase 1b — Resolve GitHub Issues

Fetch open issues from `CERTCC/Vultron` using `github-mcp-server-list_issues`
(state: `OPEN`). This gives a picture of what work is already tracked. When
writing new gap Issues, check this list to avoid creating duplicates.

### Phase 2 — Gap Analysis

Compare the current `specs/` + `notes/` against `vultron/` and `test/`:

- **Missing implementations**: a spec or note says X should exist, but code
  search finds no implementation.
- **Partial implementations**: code exists but tests or edge cases are
  missing.
- **Untested behaviors**: implementation exists but no test covers it.
- **Stale open Issues**: GitHub Issues for things already implemented — close
  these with a comment explaining they are done.
- **Known bugs**: open Bug-type GitHub Issues that block or relate to
  planned work.

> Do not assume missing functionality; confirm via code search first.

### Phase 3 — Create GitHub Issues for gaps

For each confirmed gap, create a GitHub Issue using the `manage-github-issue`
skill. If the issue has known blockers at creation time, wire them as
structured relationships — do **not** add `Blocked by #N` text to the body.

```bash
ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Gap description — one line>" \
  --body "## Summary

<What is missing and why it matters — one paragraph>

## Acceptance Criteria

- [ ] AC-1: <testable criterion>
- [ ] AC-2: <testable criterion>
...

## Reference

Spec: \`specs/<topic>.yaml\` <ID range>" \
  --label "size:<S|M|L>")
  # Add --blocked-by N for known blockers
echo "Created gap issue #${ISSUE_NUMBER}"
```

Set the `size:` label from AC count: 1–2 → `size:S`; 3–6 → `size:M`;
7+ → `size:L`.

Then add the issue to Project #24 with `Schedule=Someday`:

```bash
NODE_ID=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${ISSUE_NUMBER}"') { id }
  }
}' --jq '.data.repository.issue.id')
ITEM_ID=$(gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    contentId: \"${NODE_ID}\"
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
```

Do **not** add tasks to GitHub Issues outside the `manage-github-issue`
workflow documented above.

**Grouping related gaps (PAD-01-002, PAD-01-003):** When the gap analysis
identifies **2 or more closely related gaps** in the same spec area (e.g.,
multiple missing implementations of the same protocol feature), consider
creating a **parent Task Issue** first, then wire the individual gap Issues
as sub-issues. Use `manage-github-issue` for both the parent and the
sub-issue wiring:

```bash
# 1. Create the parent Task issue with the Task issue type
PARENT_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Parent task title>" \
  --body "<Summary of the related gaps>" \
  --issue-type-id "IT_kwDOAjf0s84AcFLo" \
  --label "size:<S|M|L>")

# 2. Create each gap issue and wire as sub-issue of the parent
CHILD_1=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Gap 1>" --body "..." \
  --label "size:S" \
  --parent "${PARENT_NUMBER}")

CHILD_2=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Gap 2>" --body "..." \
  --label "size:S" \
  --parent "${PARENT_NUMBER}")
```

Only create a parent Task if the gaps are genuinely related and benefit from
grouping. Independent gaps MUST remain flat leaf Issues.

### Phase 4 — Write Observations to notes/

- Any gap-analysis observations, open questions, clarified assumptions, or
  architectural risks discovered during gap analysis SHOULD be written
  directly to the appropriate `notes/*.md` file.
- Do **not** write these observations to `plan/incoming/learnings/`.
  That directory is reserved for `build` and `bugfix` outputs.

### Phase 5 — Commit

Invoke the `commit` skill. Commit only modified notes/ files with a clear,
specific message (e.g.,
`plan: gap analysis — create N issues, update notes/`).

## Constraints

- Do not modify code or tests.
- Do not write to `plan/incoming/learnings/`.
- Do not speculate about missing functionality; verify with code search first.
- Do not implement anything — that is `build`'s domain.
- Use `uv run append-history implementation` only via `build` — never from
  within `update-plan`.

## Project Board

All Issues created by this skill are added to Project #24 ("Vultron Planning")
with `Schedule=Someday`. Use `review-priorities` to move them to Now/Next/Later
when they are ready to be scheduled.
