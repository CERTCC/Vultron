---
title: review-priorities Reference
---

# Review Priorities — Reference

Technical implementation details for the combined audit-and-update workflow.

## Architecture

```text
review-priorities (coordinator)
  ├─ Phase 1: Invoke check-priority-status
  │  └─ Output: Status report (by tier, per Epic, coverage, health)
  ├─ Phase 2: Summarize significant findings for user
  ├─ Phase 3: Interactive update loop (ask_user per action)
  │  ├─ Move item between tiers (API mutation)
  │  ├─ Promote triage item (API mutation)
  │  ├─ Create Epic (invoke create-epic skill)
  │  └─ Archive Epic (invoke archive-history, close issue)
  └─ Phase 4: Commit if notes/history files changed
```

## Project Board Constants

| Name | Value |
|---|---|
| Project node ID | `PVT_kwDOAjf0s84BZnre` |
| Schedule field ID | `PVTSSF_lADOAjf0s84BZnrezhUlFOM` |
| Now option ID | `1e84189c` |
| Next option ID | `9fca00b2` |
| Later option ID | `e2149d3e` |
| Someday option ID | `fcffa79d` |

## Phase 1: Run check-priority-status

Invoke the `check-priority-status` skill and capture its output. The report
provides:

- Items per tier (Now/Next/Later/Someday)
- Per-Epic sub-issue progress
- Coverage (issues on board vs. off board)
- Triage count (Someday items needing scheduling)
- Stale items (>7 days no activity)
- Orphaned PRs

## Phase 2: Summarize Findings

Surface significant findings via plain text before asking for action:

```text
📊 Board status:
  Now:     3 Epics (12 open sub-issues, 2 blocked)
  Next:    2 Epics (8 open sub-issues)
  Later:   1 Epic  (4 open sub-issues)
  Someday: 7 items (triage needed)

⚠ 14 open issues not yet on board
⚠ 3 stale items (>1 week inactive)
```

## Phase 3: Interactive Update Loop

Use `ask_user` for every choice — never ask questions in plain text.

```python
while True:
    action = ask_user(
        question="What would you like to do?",
        choices=[
            "Move item(s) between Schedule tiers (Recommended)",
            "Promote Triage items to Now/Next/Later",
            "Create a new Epic for uncovered issues",
            "Archive a completed Epic",
            "No changes, exit",
        ]
    )
    if action == "No changes, exit":
        break
    # ... delegate to sub-workflow
```

### Move Item Between Tiers

1. Ask which issue/Epic number to move.
2. Ask which tier (Now / Next / Later / Someday).
3. Look up the item's project item ID via board items query.
4. Call `updateProjectV2ItemFieldValue` with the chosen option ID.
5. Confirm to user.

### Promote Triage Items

1. List all Someday items for user to choose from.
2. Ask which tier to promote to.
3. Apply the move (same mutation as above).

### Create Epic

1. Ask for Epic title and description.
2. Ask which leaf issues to include.
3. Invoke `create-epic` skill.
4. Wire sub-issues via `manage-github-issue`.

### Archive Completed Epic

1. Confirm all sub-issues are closed.
2. Invoke `archive-history` skill with type `priority`.
3. Close the Epic: `gh issue close <N> --repo CERTCC/Vultron`.

## Phase 4: Commit (if needed)

Board changes (Schedule field updates) happen live via API — no file commit
needed.

If `archive-history` was invoked (creates a file under `plan/history/`),
or if notes files were modified, invoke the `commit` skill.

## Error Handling

### GitHub API Failure

```text
❌ Failed to fetch board items
   Cause: No token or insufficient permissions
   Action: Exit with guidance ("Check your GitHub token")
```

### Item Not on Board

If the user references an issue not in Project #24, offer to add it first
with `Schedule=Someday` before moving it to the desired tier.

## Configuration

```bash
GITHUB_TOKEN=ghp_...   # Required for API access
```

## Rollback

- Board moves: re-run the move mutation with the previous tier option ID.
- Closed Epics: `gh issue reopen <N> --repo CERTCC/Vultron`.
- History entries: immutable; document corrections in a new entry.
