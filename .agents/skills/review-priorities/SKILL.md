---
name: review-priorities
description: Audit and update PRIORITIES.md in one workflow. Runs a comprehensive status check against open issues and PRs, then offers interactive options to add, refine, or remove priority groups. Use when you want to review where the project stands relative to plans and make any necessary updates.
---

# Review Priorities

Complete audit-and-update workflow for `plan/PRIORITIES.md`. Combines status checking and interactive updates into a single guided workflow.

## Quick start

Run the review-priorities skill.

The skill will:

1. **Check status** (via `check-priority-status`):
   - Audit current priorities against open GitHub issues and PRs
   - Generate detailed report: coverage %, progress per group, uncovered issues, stale work
2. **Review findings** with you:
   - Highlight significant gaps, empty priorities, stale items
   - Offer insights on what might need updating
3. **Offer interactive update options**:
   - Add new priority groups (for uncovered work)
   - Refine existing groups (add/remove issues, update description)
   - Remove completed priorities (archive via `append-history`)
   - Skip updates and just review
4. **Stage and commit** any changes made

## Workflows

### Typical Session: Review Only

If the status report shows everything on track:

1. Run skill
2. Review findings
3. Exit (no changes needed)
4. Done

### Typical Session: Review + Update

If the status report flags uncovered issues or stale work:

1. Run skill
2. Review findings
3. Choose: "Add new priority for uncovered issues? [Yes/No]"
4. Interactively add/refine groups (uses `update-priorities` logic)
5. Preview changes
6. Commit
7. Done

### Typical Session: Review + Multiple Updates

If multiple changes are warranted:

1. Run skill
2. Review findings
3. Add new priority #480 for uncovered issues
4. Ask: "Make more updates? [Add another / Refine existing / Remove / No]"
5. Refine existing priority #475
6. Ask again: "More updates?"
7. Done adding
8. Preview all changes together
9. Commit
10. Done

## Report Sections (from check-priority-status)

### Summary

- Total priority groups, linked items, coverage %
- Status distribution (closed, pending, PR-pending, blocked)
- Activity age and stale items (1-week threshold)

### Per-Priority Progress

Table: each group's progress toward completion, with status indicators.

### Coverage Audit

- **Uncovered issues**: All open issues not in any priority (with labels, age, activity)
- **Empty priorities**: Groups with no active work
- **Orphaned PRs**: Open PRs not linked to any priority

### Health Check

- Stale items (no activity for 1+ week)
- Long-pending PRs
- Dependency chains and blockers

## Interactive Update Options

After reviewing the status report, you're offered:

```text
Based on the report:
  - 12 uncovered open issues
  - 1 empty priority (476)
  - 2 stale items (>1 week inactive)

What would you like to do?
  [A] Add new priority group(s)
  [B] Refine existing priority
  [C] Remove a priority
  [D] No changes, exit
```

### Add New Priority

- Identify root issue (epic or feature)
- List related work
- Clarify dependencies
- Assign or auto-suggest priority number
- Validate all issues exist and are open
- Add to PRIORITIES.md

### Refine Existing Priority

- Select priority to update
- Choose: title, description, add/remove issues, adjust priority number
- Validate
- Update in PRIORITIES.md

### Remove Priority

- Confirm all linked issues are closed
- Archive via `append-history priority`
- Remove from PRIORITIES.md

### Epic Hierarchy Maintenance (PAD-02-008 – PAD-02-010)

After adding, refining, or removing priority groups, enforce the Epic
hierarchy for every group that has **2 or more open leaf Issues** (a leaf
Issue is any Issue with no open sub-issues).

For each such group:

1. **Check for an existing open Epic** with the group's `group:` label:

   ```bash
   gh issue list --repo CERTCC/Vultron \
     --label "group:<slug>" \
     --state open \
     --json number,title,issueType \
     | python3 -c "
   import json, sys
   issues = json.load(sys.stdin)
   epics = [i for i in issues if (i.get('issueType') or {}).get('name') == 'Epic']
   print(epics[0]['number'] if epics else 'NONE')
   "
   ```

2. **If no Epic exists**, invoke the `create-epic` skill. Provide the group
   label slug, an Epic title derived from the PRIORITIES.md group heading,
   a body listing the open leaf Issues, and the list of leaf issue numbers.
   The skill returns the new Epic number.

3. **If an Epic exists**, use the `manage-github-issue` skill to link any
   open leaf Issues not yet wired as sub-issues.

4. **Record the Epic number** in `plan/PRIORITIES.md` next to the group
   heading (PAD-02-010):

   ```markdown
   ## Priority NNN — Epic #M: Title
   ```

   If the heading already has `— Epic #M:`, update the number only if the
   old Epic was closed and a new one was created.

Run this step for every group touched during the session, plus any group
whose Epic number is missing from PRIORITIES.md.

## Preview & Commit

Before writing to disk:

1. Show **diff preview** of all changes
2. Ask for confirmation
3. If yes:
   - Stage `plan/PRIORITIES.md`
   - Generate commit message (or prompt user for custom message)
   - Add co-author trailer and commit
4. If no:
   - Save draft to session workspace
   - Exit for manual review later

## Advanced Features

See [REFERENCE.md](REFERENCE.md) for:

- Batch operations (add multiple priorities from structured input)
- Priority renumbering (consolidate gaps)
- Report export (JSON, CSV)
- History queries

## Component Skills

This skill is built on two independent sub-skills:

- **check-priority-status** — Status auditing (read-only, reports findings)
- **update-priorities** — Interactive updates (write, validates, commits)

You can run these independently if you prefer to separate concerns:

```bash
# Status check only
check-priority-status

# Updates only (assuming you already know what to change)
update-priorities
```

## Notes

- **Review-first philosophy**: Always check status before updating. Findings inform decisions.
- **User control**: No automatic changes. You decide what updates are warranted based on report.
- **Archival requirement**: Completed priorities must be archived to `plan/history/` before removal.
- **Undo via git**: If changes are committed incorrectly, use `git revert` or `git reset --soft`.
