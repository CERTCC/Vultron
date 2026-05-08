---
title: check-priority-status Reference
---

# Check Priority Status — Reference

Technical details, configuration, and implementation notes for the priority status check.

## Data Model

### Priority Group Structure

Parsed from `plan/PRIORITIES.md`:

```yaml
Priority: <number>
Title: <string>
Description: <string>
Issues:
  - Epic or root issue (GitHub URL or #<number>)
  - Child issues (sub-tasks, linked via GitHub sub-issue relationships)
  - Related issues (mentioned in description, marked as related)
Dependencies:
  - Prerequisite issues (noted as "Prerequisite:")
  - Blocked items (issues with "blocked by" annotation)
```text

### Issue State

For each issue linked to a priority:

- **State**: Open, closed
- **Type**: Epic, bug, feature, chore
- **Activity**: Last update timestamp, last actor
- **PRs**: List of open/closed PRs that reference this issue
- **Sub-issues**: For epics, aggregated state of linked issues
- **Blockers**: Explicit dependencies or prerequisite tags

## Computation

### Coverage Analysis

**Uncovered issues**:

```text
Open issues (all types) NOT in any priority group
= All open issues - Union of all issues linked to priorities
```text

**Empty priorities**:

```text
Priorities with:
- Zero linked open issues (all linked issues are closed)
- No open PRs addressing the priority
```text

**Orphaned PRs**:

```text
Open PRs where:
- PR does not reference any GitHub issue
- PR references only closed issues
- Referenced issue(s) not in any priority group
```text

### Activity Age

Measured from **most recent event** among:

- Last status change (label change, opened/reopened)
- Last commit pushed to PR or linked branch
- Last comment

Does **not** include creation date.

**Stale threshold**: 1 week (7 days) — items inactive for 7+ days are flagged

### Progress Calculation

For each priority group (or epic):

```text
Done         = Count of closed issues
Pending      = Count of open issues with no PR
PR Pending   = Count of open issues with ≥1 open PR
Blocked      = Count of issues labeled "blocked" or with explicit dependency
Total        = Done + Pending + PR Pending + Blocked

% Complete = Done / (Done + Pending + PR Pending + Blocked)
Status:
  🟢 ≥75% done OR all sub-items have active PRs
  🟡 25–75% done with some pending items
  🔴 <25% done OR has blocked items with no ETA
```text

## Configuration

### Staleness Threshold

Environment variable or config file:

```

PRIORITY_STATUS_STALE_DAYS=7  # Default: 1 week

```text

Activity age measured from status change, commit, or comment—not creation date.

### Date Range Filtering

Optional: Report only on activity within a date range:


```

PRIORITY_STATUS_FROM=2025-01-01
PRIORITY_STATUS_TO=2025-12-31

```text

### Issue Type Filters



By default, all types (bug, feature, chore, epic) are included. To focus on specific types:

```

PRIORITY_STATUS_TYPES=bug,epic  # Comma-separated

```text

## Queries

### GitHub Query Examples

**All open issues in a repo**:

```graphql
GET /repos/{owner}/{repo}/issues?state=open&per_page=100
```text

**Issues linked to an epic** (via GitHub GraphQL):

```graphql
query {
  repository(name: "Vultron", owner: "CERTCC") {
    issue(number: 464) {
      epic {
        issues(first: 20) {
          edges {
            node { number, title, state }
          }
        }
      }
    }
  }
}
```text

**PRs referencing an issue**:

```graphql
GET /repos/{owner}/{repo}/issues/{issue_number}/pull_requests
```text

## Limitations

- **Stale is approximate**: Activity age is based on visible GitHub events; local work not pushed is invisible.
- **Nested epics not flattened**: If an epic contains child epics, only direct child issues are counted (not transitive).
- **Manual dependencies**: Dependencies noted in text (e.g., "Prerequisite: #440") are parsed via regex; format must be consistent.
- **Cross-repo dependencies**: If Vultron has dependencies on other repos, those are not tracked.

## Extending the Skill

### Custom Report Sections

Add a new section by:

1. Write a query function to gather data (e.g., `fetch_recent_label_changes()`)
2. Add a section render function
3. Insert into report output sequence



### Export Formats

Extend output to JSON, CSV, or Markdown table for downstream tooling:

```

check-priority-status --format json --output report.json

```text


### Integration with update-priorities

After status check, if significant uncovered work is found:

```

Suggest: Run `update-priorities` to add new priority groups
or `update-priorities --group 470` to refine an existing group

```text

## Troubleshooting

### Issue not showing in report

1. Check `plan/PRIORITIES.md` has correct GitHub issue links (format: `#123` or full URL)
2. Verify the issue is open (closed issues should appear under "Done", not "pending")
3. Check GitHub API token has sufficient permissions (`repo` scope required)

### Stale items showing as active

Activity age is computed from GitHub events. If a PR has been stale locally but not pushed, it won't show as stale. Push regularly to keep the report accurate.

### Empty priority with open PRs

This indicates PRs are not linked to the priority's issues. Add a link by:

1. Update PR description to reference the issue: `Fixes #<issue_number>`
2. Re-run the check
