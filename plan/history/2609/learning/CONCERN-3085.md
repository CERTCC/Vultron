---
source: CONCERN-3085
timestamp: '2026-09-22T14:15:02.698835+00:00'
title: 'concern(bridge): setup_tree and execute_tree share one try block — execution
  errors labelled ''BT setup failed'''
type: learning
---

At `vultron/core/behaviors/bridge.py:617`, `setup_tree()` and `execute_tree()` are called inside the same `try` block. If `execute_tree` ever raises, the error is caught and labelled 'BT setup failed' rather than 'BT execution failed', misdirecting debugging. `execute_tree` is designed to never raise and currently satisfies that invariant. But both calls sit inside the same try. If a future py_trees release causes `execute_tree` to raise, the exception is caught by the setup-phase except clauses and reported as 'BT setup failed with internal error'. Operators debugging the failure look at setup configuration rather than tree logic.

**Resolved**: 2026-09-22 — implementation tracked in #3510 (split into two separate try/except pairs).
Docs PR: <https://github.com/CERTCC/Vultron/pull/3509>.
