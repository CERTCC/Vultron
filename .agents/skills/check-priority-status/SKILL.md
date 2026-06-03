---
name: check-priority-status
description: >
  Audit and report on priority status against the GitHub Project #24 board,
  open issues, and PRs — tracking progress, coverage gaps, stale items, and
  readiness by Schedule tier (Now/Next/Later/Someday). Use when reviewing where
  the project stands relative to the board, or before running review-priorities.
---

# Check Priority Status

Generate a comprehensive status report from GitHub Project #24 ("Vultron
Planning") and current open issues and pull requests. Provides developer,
architect, and supervisor perspective on progress, coverage gaps, stale work,
and decision points.

> **HARD STOP — READ FIRST**
>
> This skill produces a report and then **stops unconditionally**. It MUST NOT
> invoke any other skill, take any follow-up action, make any file edits, or
> prompt any next step beyond printing the report. No exceptions, even when
> running in autopilot or background mode.

## Quick Start

Run this when you want to understand:

- **Progress**: What is in Now/Next/Later? How many issues/PRs are
  closed, pending, or in-progress in each tier?
- **Coverage**: Issues not yet on the board? Epics with no sub-issues?
- **Health**: Items claimed but stale? PRs pending review?
- **Readiness**: What is blocking work in the Now tier?
- **Triage**: How many Someday items need scheduling?

Output is a detailed narrative with tables, organized by section.

## Usage

Run the check-priority-status skill. The skill will:

1. **Query Project #24** for all items grouped by Schedule field
   (Now / Next / Later / Someday / unset)
2. **Query GitHub** for live current state of every linked issue/PR
3. **Resolve blockers** from GitHub issue relationship metadata only
   (formal "blocked by" relationships, not body text)
4. **Analyze** uncovered issues (open but not on the board), empty
   Schedule tiers, and staleness
5. **Generate** a detailed status report with:
   - Summary statistics and a **"Next up"** callout (first unblocked
     open issue in the Now tier)
   - Per-tier and per-Epic progress
   - Coverage audit (issues not on board, Epics with no open sub-issues)
   - Health check (stale items, long-pending PRs, blockers)
6. **Stop** — the report is the complete output; no further actions taken

## Data Sources

### Querying Project #24 by Schedule Tier

```bash
gh api graphql -f query='{
  node(id: "PVT_kwDOAjf0s84BZnre") {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          content {
            ... on Issue { number title state }
          }
          fieldValueByName(name: "Schedule") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
        }
      }
    }
  }
}'
```

Group results by `fieldValueByName.name` (Now / Next / Later / Someday /
null = unset).

### Querying Sub-Issues of an Epic

```bash
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: <EPIC_NUMBER>) {
      subIssues(first: 50) {
        nodes { number title state }
      }
    }
  }
}'
```

### Listing All Open Issues Not on Board

```bash
# Get all open issues
ALL_OPEN=$(gh issue list --repo CERTCC/Vultron \
  --state open --json number,title,labels --limit 500)

# Get all issue numbers from Project #24
BOARD_ISSUES=$(gh api graphql ... # items query above, extract numbers)

# Difference = uncovered issues
```

## Report Sections

### Summary

- Total items on board by tier (Now / Next / Later / Someday)
- Overall coverage (% of open issues on the board)
- Status distribution (closed, open with PR, open pending, blocked)
- Most recent activity age
- Stale threshold: **1 week** (last status change, commit, or activity)
- **Next up**: The first unblocked, open, PR-less issue in the Now tier

### Per-Tier Progress

For each Schedule tier (Now → Next → Later → Someday):

| Epic / Issue | #   | Sub-Issues | Done | Pending | PR Pending | Blocked | Status |
|---|---|---|---|---|---|---|---|

- **Status**: 🟢 on track (≥75% done or all have PRs), 🟡 stalled
  (25–75% done), 🔴 at risk (<25% done or blocked items)

### Coverage Audit

#### Issues Not on Board

All open issues (bugs, features, chores) not in Project #24. Organized
by type, with age and activity status.

#### Empty Tiers / Empty Epics

- Tiers with no open issues
- Epics on the board with no open sub-issues

#### Orphaned PRs

Open PRs not linked to any issue on the board.

### Health Check

#### Stale Items

Work with no activity (comments, commits, status updates) for 7+ days.

#### Long-Pending PRs

Open PRs awaiting merge for 7+ days.

#### Dependencies & Blockers

Issues with explicit "blocked by" relationships that are still open.

### Triage Summary

Count of Someday items on board — these need to be scheduled or assigned
to an Epic via `review-priorities`.

### Next Steps

This section is intentionally omitted. The skill generates a report and
stops. Decisions about what to do with the findings are left to the user.

## Notes

- **Epics are aggregators**: An Epic's status reflects its sub-issues.
- **Activity age**: Measured from last status change, commit, or comment.
  Creation date is not counted.
- **Stale threshold**: 7 days with no activity.
- **Blocker source**: Exclusively from formal GitHub "blocked by"
  relationships — never from body text.
- **Live state required**: All issue/PR states MUST be verified live.
- **Hard stop**: This skill MUST stop after producing its report.
