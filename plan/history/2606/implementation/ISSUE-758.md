---
source: ISSUE-758
timestamp: '2026-06-04T16:44:17.434601+00:00'
title: Add BT to AddCaseStatusToCaseReceivedUseCase
type: implementation
---

## Issue #758 — Add BT to AddCaseStatusToCaseReceivedUseCase (case status received)

Migrated `AddCaseStatusToCaseReceivedUseCase` from a fully procedural
implementation to the canonical BT delegation pattern used throughout the
status workflow.

### Changes

- **New** `vultron/core/behaviors/status/add_case_status_tree.py`:
  `add_case_status_tree()` factory composing a 3-node `AddCaseStatusToCaseBT`
  Sequence.
- **Updated** `vultron/core/behaviors/status/nodes.py`: added
  `CheckCaseStatusIdempotencyNode` (AC-1), `ValidateCaseStatusTransitionNode`
  (EM/PXA, AC-2), `AppendCaseStatusToCaseNode`, and
  `CASE_STATUS_ALREADY_PRESENT` sentinel constant.
- **Updated** `vultron/core/use_cases/received/status.py`: rewrote `execute()`
  to delegate via `BTBridge`; removed 3 dead private helpers and 4 unused
  imports.
- **New** `test/core/behaviors/status/test_add_case_status_bt.py`: 18 tests
  covering all nodes, tree factory, and use-case integration (AC-3).

### Outcome

All 2783 tests pass. mypy and pyright clean. PR #776 opened.

PR: [#776](https://github.com/CERTCC/Vultron/pull/776)
