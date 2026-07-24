---
source: ISSUE-1661
timestamp: '2026-07-24T16:29:01.423861+00:00'
title: 'Architecture ratchet: attributed_to mutations must use save_many()'
type: implementation
---

## Issue #1661 — Architecture ratchet: attributed_to mutations must use save_many()

Adds `test/architecture/test_attributed_to_requires_save_many.py` — AST ratchet enforcing CM-21-004 and BTND-06-008: any BT node `update()` that assigns to `attributed_to` AND calls `self.datalayer.save()` (instead of `save_many()`) fails the test. `KNOWN_VIOLATIONS` is empty because `AcceptCaseOwnershipTransferNode` already uses `save_many()` correctly. Includes 7 synthetic detector-validation tests covering direct and local-dl-rebind true-positives, and 5 false-positive cases. AC-4/AC-5 pitfall entries were pre-existing from #1653.

PR: <https://github.com/CERTCC/Vultron/pull/1668>
