---
title: check-priority-status Reference
---

# Check Priority Status — Reference

Technical details, configuration, and implementation notes for the priority
status check.

## Project Board Constants

| Name | Value |
|---|---|
| Project node ID | `PVT_kwDOAjf0s84BZnre` |
| Schedule field ID | `PVTSSF_lADOAjf0s84BZnrezhUlFOM` |
| Schedule: Now | `1e84189c` |
| Schedule: Next | `9fca00b2` |
| Schedule: Later | `e2149d3e` |
| Schedule: Someday | `fcffa79d` |

## Data Model

### Board Item Structure

Queried from Project #24:

```yaml
ScheduleTier: Now | Next | Later | Someday | null
IssueNumber: <int>
IssueTitle: <string>
IssueState: open | closed
IssueType: Epic | Task | Bug | Concern | Idea
SubIssues: (for Epics) list of child issue numbers
```

Items with `ScheduleTier = null` are on the board but have no Schedule value
set — treat as uncategorized.

### Issue State

For each issue on the board:

- **State**: open, closed
- **Type**: Epic, Task, Bug, Concern, Idea
- **Activity**: Last update timestamp, last actor
- **PRs**: List of open/closed PRs that reference this issue
- **Sub-issues**: For Epics, aggregated state of linked issues
- **Blockers**: Formal "blocked by" relationships

### Blocker Detection

Blockers are sourced **exclusively** from formal GitHub issue relationship
metadata — specifically the "blocked by" relationship on an issue.
Body text mentioning "blocked by" is **not** parsed.

For each issue with a "blocked by" relationship:

1. Fetch the live state of the blocking issue/PR from GitHub.
2. If the blocker is **closed**, do not report it as blocking.
3. If the blocker is **open**, report the dependent issue as blocked.

### Coverage Analysis

**Issues not on board**:

```text
Open issues (all types) NOT in Project #24
= All open issues − Union of all issues on the board
```

**Empty tiers**:

```text
Schedule tiers with no open issues
```

**Epics with no open sub-issues**:

```text
Epic issues on the board where all sub-issues are closed or none exist
```

**Orphaned PRs**:

```text
Open PRs where referenced issue(s) are not in Project #24
```

### Activity Age

Measured from **most recent event** among:

- Last status change (label change, opened/reopened)
- Last commit pushed to PR or linked branch
- Last comment

Does **not** include creation date.

**Stale threshold**: 1 week (7 days)

### Progress Calculation

For each Epic (or tier):

```text
Done         = Count of closed sub-issues
Pending      = Count of open sub-issues with no PR (not blocked)
PR Pending   = Count of open sub-issues with ≥1 open PR
Blocked      = Count of sub-issues with ≥1 open "blocked by" relationship
Total        = Done + Pending + PR Pending + Blocked

% Complete = Done / Total
Status:
  🟢 ≥75% done OR all sub-items have active PRs
  🟡 25–75% done with some pending items
  🔴 <25% done OR has blocked items with no ETA
```

### Readiness

A Now-tier Epic is **actionable** ("Next up") only when it has at least one
unblocked open sub-issue with no open PR.

## GitHub Query Examples

### All items in Project #24 with Schedule tier

```graphql
{
  node(id: "PVT_kwDOAjf0s84BZnre") {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          content {
            ... on Issue { number title state }
          }
          fieldValueByName(name: "Schedule") {
            ... on ProjectV2ItemFieldSingleSelectValue { name optionId }
          }
        }
      }
    }
  }
}
```

### Sub-issues of an Epic

```graphql
{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: <N>) {
      subIssues(first: 50) {
        nodes { number title state }
      }
    }
  }
}
```

### All open issues in repo

```bash
gh issue list --repo CERTCC/Vultron \
  --state open --json number,title,labels --limit 500
```

### PRs referencing an issue

```bash
gh pr list --repo CERTCC/Vultron \
  --search "linked:issue:<number>" --json number,title,state
```

## Configuration

### Staleness Threshold

Default: 7 days. Items with no activity (status change, commit, comment)
for 7+ days are flagged as stale.

## Limitations

- **Stale is approximate**: Activity age is based on visible GitHub events;
  local work not pushed is invisible.
- **Nested Epics not flattened**: Only direct sub-issues are counted, not
  transitive.
- **Cross-repo dependencies**: External repo dependencies are not tracked.
- **100-item pagination**: Board queries fetch up to 100 items by default;
  paginate if the board grows beyond that.

## Hard Stop

This skill MUST stop after delivering its report. It MUST NOT invoke any
other skill or take any follow-up action. The report is the complete,
final output.

## Troubleshooting

### Issue not showing in report

1. Check that the issue is in Project #24 (visit the board or run the
   items query above).
2. Verify the issue is open (closed issues appear under "Done").
3. Check that your GitHub token has sufficient permissions (`repo` scope).

### Stale items showing as active

Activity age is computed from GitHub events. Push branches regularly to
keep the report accurate.
