---
source: ISSUE-1956
timestamp: '2026-08-05T18:38:58.100946+00:00'
title: 'create_deploy_tree: fix-or-mitigate combinator tree'
type: implementation
---

## Issue #1956 — create_deploy_tree: fix-or-mitigate combinator tree

Implemented `create_deploy_tree` in `vultron/core/behaviors/report/deploy_tree.py` — a combinator factory composing `create_deploy_fix_tree` (preferred) and `create_deploy_mitigation_tree` (fallback) into a `DeployOrMitigateBT` Fallback per BT-20-005.

- 107-line factory module, delegates entirely to child factories — no logic inlined
- 18 unit tests across all 4 ACs: structure, arm identity, default singleton wiring, cross-arm isolation
- All linters clean; 6206 tests pass

PR: <https://github.com/CERTCC/Vultron/pull/2000>
