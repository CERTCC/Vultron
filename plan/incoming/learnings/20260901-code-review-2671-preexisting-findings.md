---
title: Pre-existing code review findings deferred from ISSUE-2671
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2671
signal: concern
---

Code review during ISSUE-2671 build session surfaced three findings in files
NOT part of the PR diff (`add_case_status_tree.py`, `test_case_status.py`).
All are pre-existing relative to this branch.

## Findings

**Finding 1 (Bug — deferred as #2983)**
`add_case_status_tree.py:113`: `status_id = request.status_id or ""`
(empty-string fallback) while `case_id` was hardened to `or None`.
Use-case guard at `status.py:69` only rejects `None`, so an empty-string
`status_id` slips through. `CheckCaseStatusIdempotencyNode` then fails to
find `""` in existing statuses and returns SUCCESS — idempotency guard
silently bypassed.

**Finding 2 (IMPROVE — pre-existing, no bug)**
`add_case_status_tree.py:119`: redundant `case_id or None` — `case_id` was
already normalized to `or None` on line 114. No runtime impact but could
mislead future readers.

**Finding 3 (IMPROVE — pre-existing, test quality)**
`test/core/behaviors/status/nodes/test_case_status.py:148`: assertion uses
`or` over two string-presence checks, making it weaker than intended.
A refactor that drops either word would silently pass the assertion.

## Disposition

- Finding 1 → Bug #2983 (parent: #2694, milestone 24, size:S)
- Finding 2 → can be fixed in same PR as Finding 1
- Finding 3 → can be fixed in same PR as Finding 1

Parent issue for ISSUE-2671 is #2694 (Persistence-boundary state enforcement).
