---
source: ISSUE-1474
timestamp: '2026-07-20T21:07:09.439094+00:00'
title: Migrate embargo_lifecycle em_state guards to BT nodes
type: implementation
---

## Issue #1474 — Migrate core/services/embargo_lifecycle.py guards to BT nodes

Extracted the 5 inline em_state reads and 4 em_state mutations from EmbargoLifecycle service methods into named ReadEmStateNode (DataLayerCondition) and WriteEmStateNode (DataLayerAction) BT nodes.

- New file: vultron/core/behaviors/embargo/nodes/em_state.py
- All BT callers (lifecycle.py, proposal.py, case/nodes/embargo.py) now pass em_before via ReadEmStateNode
- Service uses caller_owns_em_io guard to skip read/write when em_before is supplied
- 15 new tests in test_em_state.py; 4 new service-layer tests in TestCallerOwnsEmIo
- Follow-up #1554 tracks remaining inline accesses in SetEmbargoActiveNode / ApplyEmbargoTeardownNode (state-sync override paths)

PR: <https://github.com/CERTCC/Vultron/pull/1555>
