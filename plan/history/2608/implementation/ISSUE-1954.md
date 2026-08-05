---
source: ISSUE-1954
timestamp: '2026-08-05T17:06:08.642061+00:00'
title: create_deploy_mitigation_tree factory and tests
type: implementation
---

## Issue #1954 — create_deploy_mitigation_tree: factory function and production nodes

Implemented `create_deploy_mitigation_tree()` in `vultron/core/behaviors/report/deploy_mitigation_tree.py` and 25 unit/integration tests in `test/core/behaviors/report/test_deploy_mitigation_tree.py`.

DeployMitigationBT (Fallback) has four arms: (1) mitigation_deployed_factory call-out short-circuit, (2) _ShouldStayInRmDeferred, (3)_DeployMitigationIfAvailable (5 children — 2 reused guards + 3 call-out seams, no CS state nodes), (4) _MonitorDeploymentIfDesired. All 6 factories from DeployMitigationCallOutBundle wired with correct DETERMINISTIC ceiling/floor defaults (BT-23-002). No TransitionCS/EmitActivity nodes — mitigation has no CS state bit (BT-20-005).

PR: <https://github.com/CERTCC/Vultron/pull/1979>
