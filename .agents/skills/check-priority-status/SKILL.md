---
name: check-priority-status
description: Audit and report on priority group status against open issues and PRs, tracking progress, coverage gaps, stale items, and readiness. Use when reviewing where the project stands relative to documented priorities, or before updating PRIORITIES.md.
---

# Check Priority Status

Generate a comprehensive status report comparing `plan/PRIORITIES.md` against current open issues and pull requests. Provides developer, architect, and supervisor perspective on progress, coverage gaps, stale work, and decision points.

## Quick start

Run this when you want to understand:

- **Progress**: Where are priority groups? How many issues/PRs closed, pending, or in-progress?
- **Coverage**: Issues open but not linked to any priority? Priorities without corresponding issues?
- **Health**: Items claimed but stale (no recent activity)? PRs pending (waiting for review)?
- **Readiness**: What needs updating before next steps?

Output is a detailed narrative with tables, organized by section.

## Usage

Run the check-priority-status skill.

The skill will:

1. **Parse** `plan/PRIORITIES.md` to extract priority groups, linked issues, and epic structure
2. **Query** GitHub for current state of each linked issue/PR and their relationships
3. **Analyze** uncovered issues (open but not in PRIORITIES.md), orphaned priorities (groups with no active issues), and staleness
4. **Generate** a detailed status report with:
   - Summary statistics (groups, coverage %, activity age)
   - Per-group progress (done ✅, pending, PR pending, blocked)
   - Coverage audit (uncovered open issues, empty priorities, orphans)
   - Health check (stale items, long-pending PRs)
5. **Suggest** next steps (run update-priorities if significant changes found)

## Report Sections

### Summary

- Total priority groups and linked items
- Overall coverage (% of open issues in a priority group)
- Status distribution (closed, open with PR, open pending, blocked)
- Most recent activity age
- Stale threshold: **1 week** (last status change, commit, or activity)

### Per-Priority-Group Progress

Table with columns:

| Priority | Title | Issues | PRs | Done | Pending | PR Pending | Blocked | Status |
|----------|-------|--------|-----|------|---------|-----------|---------|--------|

- **Issues**: Count of linked GitHub issues
- **PRs**: Count of linked open PRs
- **Done**: Closed issues (completed)
- **Pending**: Open issues with no PR
- **PR Pending**: Open issues with open PR(s) awaiting merge
- **Blocked**: Issues marked blocked or dependent on others
- **Status**: Summary icon: 🟢 on track, 🟡 stalled, 🔴 at risk

### Coverage Audit

#### Uncovered Issues

All open issues (bugs, features, chores) not linked to any priority group. Organized by type, with age and activity status to highlight urgent or stale items.

#### Empty Priorities

Priority groups with no linked open issues (work may be completed or stalled).

#### Orphaned PRs

Open PRs not linked to any priority group or issue.

### Health Check

#### Stale Items

Claimed work with no activity (comments, commits, status updates) for N+ days.

#### Long-Pending PRs

Open PRs awaiting merge for N+ days.

#### Dependencies & Blockers

Issues or PRs with explicit blocker relationships or prerequisite notes.

### Next Steps

If significant findings (uncovered issues, stale work, empty priorities), suggest running:

```bash
# To interactively update PRIORITIES.md
# (This skill would be: update-priorities)
```text

## Advanced Features

See [REFERENCE.md](REFERENCE.md) for:

- Technical data model and computation details
- Query structure and GitHub API usage
- Limitations and extension points

## Notes

- **Epics are aggregators only**: An epic's status reflects its linked sub-issues. Individual sub-issues are rolled up; the report shows epic-level aggregates only.
- **PR linking**: A PR is linked to a priority if the PR mentions an issue that's linked to the priority.
- **Activity age**: Measured from last status change, commit push, or comment. Creation date is not considered.
- **Stale threshold**: 1 week (7 days) — items with no activity in 7+ days are flagged
- **No chaining**: This skill prints a suggestion to run `update-priorities` if findings warrant; it does not invoke it automatically
