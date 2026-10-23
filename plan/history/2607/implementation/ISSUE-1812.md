---
source: ISSUE-1812
timestamp: '2026-07-29T18:13:13.797716+00:00'
title: create_develop_fix_tree factory and 5 production BT nodes
type: implementation
---

## Issue #1812 — create_develop_fix_tree: full production BT factory function for fix development

Implemented `create_develop_fix_tree` in `vultron/core/behaviors/report/develop_fix_tree.py` as the full production-layer BT factory function for the fix development workflow.

### What was delivered

- `DevelopFixBT` Fallback tree: CheckIsVendorRoleNode → CheckCSFixNotYetReady → _CreateFixForAcceptedReports (Sequence)
- 5 new production-layer nodes: CheckIsVendorRoleNode, CheckCSFixNotYetReady, CheckRMStateAccepted, TransitionCStoFixReady, EmitCFActivity
- `DevelopFixCallOutBundle` + `DEVELOP_FIX_DETERMINISTIC` in core bundles (AC-5)
- `DEVELOP_FIX_STOCHASTIC` in demo fuzzer bundles wiring CreateFix (AC-6)
- 32 unit tests covering all 8 acceptance criteria

### Key decision

`_resolve_case_manager_id` inlined in develop_fix.py to avoid behaviors→use_cases import violation (BTND-04-003); canonical source tracked by #1428.

PR: <https://github.com/CERTCC/Vultron/pull/1818>
