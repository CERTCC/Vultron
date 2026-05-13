---
title: review-priorities Reference
---

# Review Priorities — Reference

Technical implementation details for the combined audit-and-update workflow.

## Architecture: Daisy-Chained Skills

```text
review-priorities (outer coordinator)
  ├─ Phase 1: Invoke check-priority-status
  │  └─ Output: Detailed status report
  ├─ Phase 2: Parse report findings
  │  ├─ Extract uncovered issues
  │  ├─ Identify empty priorities
  │  ├─ Flag stale items
  │  └─ Summarize for user
  ├─ Phase 3: Offer interactive updates
  │  └─ For each action: Invoke update-priorities workflows
  │     ├─ Add new priority
  │     ├─ Refine existing
  │     └─ Remove priority
  └─ Phase 4: Commit (if changes made)
```

### Phase 1: Run check-priority-status

Call the `check-priority-status` skill (or invoke its logic directly):

```python
status_report = check_priority_status()
# Returns structured report with:
#   - summary (coverage %, status distribution)
#   - per_priority_progress (table data)
#   - uncovered_issues (list)
#   - empty_priorities (list)
#   - orphaned_prs (list)
#   - stale_items (list)
#   - health_flags (list of concerns)
```

### Phase 2: Analyze Findings

Extract key insights from report:

```python
def summarize_findings(report):
    """Return user-facing summary of significant findings."""
    issues = []

    if len(report['uncovered_issues']) > 5:
        issues.append(f"⚠ {len(report['uncovered_issues'])} uncovered open issues")

    if report['empty_priorities']:
        issues.append(f"⚠ {len(report['empty_priorities'])} priorities with no active work")

    if len(report['stale_items']) > 2:
        issues.append(f"⚠ {len(report['stale_items'])} items stale (>1 week)")

    return issues  # Sorted by severity
```

### Phase 3: Interactive Update Loop

After showing report, offer update options:

```python
while True:
    action = ask_user([
        "Add new priority group",
        "Refine existing priority",
        "Remove a priority",
        "No changes, exit"
    ])

    if action == "Add new priority group":
        # Delegate to update-priorities logic
        add_priority_workflow()
        modified = True
    elif action == "Refine existing priority":
        refine_priority_workflow()
        modified = True
    elif action == "Remove a priority":
        remove_priority_workflow()
        modified = True
    else:
        break
```

Within each action, reuse `update-priorities` logic:

- Gather input (title, description, issues, dependencies)
- Validate (GitHub API checks, link validation)
- Apply changes in-memory
- Offer "Another change? [Yes/No]"

### Phase 4: Unified Preview & Commit

After all updates, show single diff of all changes:

```diff
--- plan/PRIORITIES.md (before)
+++ plan/PRIORITIES.md (after)

  ## Priority 475 — Participant Case Replica Safety
  ...
-  - [#440](...)
+  - [#440](...)
+  - [#500](...)

+ ## Priority 480 — New Feature
+
+ Description...

  ## Priority 476 — Bug Fixes
```

Then:

1. Ask: "Write these changes?"
2. If yes:
   - Generate commit message: `"Review and update priorities\n\nAdded: 1 group\nModified: 1 group\nRemoved: 0 groups"`
   - Add co-author trailer
   - Commit
3. If no:
   - Save draft to session workspace
   - Exit

## Integration Points

### With check-priority-status

- Call its core logic (or invoke via subprocess if separate implementation)
- Parse its report format
- Summarize findings in user-friendly language

### With update-priorities

- Reuse all validation logic (GitHub API, link checking, format validation)
- Reuse all user prompts and workflows
- Share diff generation logic
- Share commit message templates

## Error Handling

### If check-priority-status Fails

```text
❌ Failed to fetch GitHub issues
   Likely cause: No GitHub token or insufficient permissions
   Action: Exit with guidance ("Check your GITHUB_TOKEN environment variable")
```

### If update-priorities Validation Fails

User is already in an update workflow. Offer to:

- Fix the issue (e.g., correct a typo)
- Skip this change (go back to menu)
- Abort (exit without writing)

## Performance Considerations

- **check-priority-status**: May take 10–30s to fetch all issues and compute aggregates (GitHub API rate limits)
- **update-priorities workflows**: Fast (mostly user input gathering), validation happens async
- **Overall**: Expect 30–60s for a full session (status check + 1–2 updates)

## Configuration

Environment variables (optional):

```bash
GITHUB_TOKEN=ghp_...                  # Required for API access
PRIORITY_STATUS_STALE_DAYS=7          # Staleness threshold (default: 7)
PRIORITY_GITHUB_OWNER=CERTCC          # GitHub org (default: CERTCC)
PRIORITY_GITHUB_REPO=Vultron          # GitHub repo (default: Vultron)
```

## State Management

### In-Memory Changes

During interactive update loop, accumulate changes in-memory:

```python
changes = {
    'added': [],      # New priority groups
    'modified': {},   # Existing groups and their changes
    'removed': []     # Removed priority IDs
}
```

Before committing, reconstruct full `plan/PRIORITIES.md` from original + changes.

### Rollback

- If user cancels before commit: changes are discarded (in-memory only)
- If commit fails: changes are not lost but file state uncertain; user should check Git status
- If commit succeeds: tracked in Git (use `git revert` to undo)

## Extensibility

Future enhancements:

- **Batch import**: Load priorities from CSV/JSON file
- **Priority renumbering**: Consolidate gaps in priority numbers
- **Report export**: Save findings to JSON/CSV for external tools
- **Scheduled checks**: Hook into CI to run status check on PRs/pushes
- **Integration with project boards**: Auto-sync GitHub project board based on priorities
