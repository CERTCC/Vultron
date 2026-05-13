---
name: check-priority-status
description: Audit and report on priority group status against open issues and PRs, tracking progress, coverage gaps, stale items, and readiness. Use when reviewing where the project stands relative to documented priorities, or before updating PRIORITIES.md.
---

# Check Priority Status

Generate a comprehensive status report comparing `plan/PRIORITIES.md` against current open issues and pull requests. Provides developer, architect, and supervisor perspective on progress, coverage gaps, stale work, and decision points.

> **HARD STOP — READ FIRST**
>
> This skill produces a report and then **stops unconditionally**. It MUST NOT
> invoke any other skill, take any follow-up action, make any file edits, or
> prompt any next step beyond printing the report. No exceptions, even when
> running in autopilot or background mode.

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
2. **Query GitHub** for live current state of every linked issue/PR — do not rely on text in `PRIORITIES.md` for status, open/closed state, or blocker relationships
3. **Resolve blockers** from GitHub issue relationship metadata only (formal "blocked by" relationships on the issue, not body text); verify every referenced blocker is currently open before reporting it as blocking
4. **Analyze** uncovered issues (open but not in PRIORITIES.md), orphaned priorities (groups with no active issues), and staleness
5. **Generate** a detailed status report with:
   - Summary statistics (groups, coverage %, activity age) and a **"Next up"** callout identifying the highest-priority group with unblocked pending work
   - Per-group progress (done ✅, pending, PR pending, blocked)
   - Coverage audit (uncovered open issues, empty priorities, orphans)
   - Health check (stale items, long-pending PRs, dependency blockers)
6. **Stop** — the report is the complete output; no further actions are taken

## Report Sections

### Summary

- Total priority groups and linked items
- Overall coverage (% of open issues in a priority group)
- Status distribution (closed, open with PR, open pending, blocked)
- Most recent activity age
- Stale threshold: **1 week** (last status change, commit, or activity)
- **Next up**: The single highest-priority group (lowest priority number) that has at least one unblocked pending issue

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

This section is intentionally omitted. The skill generates a report and stops.
Decisions about what to do with the findings are left entirely to the user.

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
- **Blocker source**: Blockers are sourced exclusively from formal GitHub issue relationship metadata (the "blocked by" relationship field on the issue). Body text mentioning "blocked by" is not parsed. Do not read blocker information from `PRIORITIES.md`.
- **Live state required**: All issue/PR open-or-closed state and blocker relationships MUST be verified against live GitHub data. Never assume a state based on what `PRIORITIES.md` text says.
- **Readiness**: A priority group is considered available for work only if (a) it has at least one unblocked pending issue AND (b) no priority group with a lower priority number has unblocked pending work. "No dependency blockage" alone does not make a group ready.
- **Hard stop**: This skill MUST stop after producing its report. It MUST NOT invoke any other skill or take any action.
