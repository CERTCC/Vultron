---
title: Issue 1510 already fixed by PR 1517 before it was claimed
type: learning
timestamp: "2026-07-20T00:00:00Z"
source: ISSUE-1510
---

## Observation

Issue #1510 (make `offer_case_manager_role()` return `(activity_id, activity_dict)`) was
still OPEN when selected by the build skill, but all acceptance criteria were already
satisfied by commit `085c2f1d` in PR #1517 ("Migrate Category-A plumbing re-reads").

PR #1517 addressed the same inefficiency for five `TriggerActivityPort` methods, including
`offer_case_manager_role`. The issue was not closed when #1517 merged because the PR did
not include a `Closes #1510` footer.

## Action taken

Closed issue #1510 with a comment referencing PR #1517 and confirming all ACs were met.
No code changes were required.

## Pattern to apply

When an issue selected for build has all ACs satisfied on current main, close it
immediately with a reference to the relevant commit/PR and record a learning.
Do not attempt to re-implement already-merged work.

**Promoted**: 2026-07-22 — captured in `AGENTS.md (root)`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1608>8>8>.
