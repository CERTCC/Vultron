---
source: ISSUE-1499
timestamp: '2026-07-17T21:43:28.411794+00:00'
title: 'BTND-07-003 density-refactor: reduce update() to ≤30 lines'
type: implementation
---

## Issue #1499 — refactor: reduce update() methods to ≤30 lines in BT emit nodes (BTND-07-003 density-refactor)

Reduced all 13 over-30-line update() methods across 6 BT node files to ≤30 lines via helper extraction.

Added `_require_datalayer()`, `_require_datalayer_and_actor()`, `_require_factory()` guard helpers to `DataLayerAction` base class. Extracted named helpers in each affected node. All tests pass (5051 passed), all linters clean.

PR: <https://github.com/CERTCC/Vultron/pull/1511>
