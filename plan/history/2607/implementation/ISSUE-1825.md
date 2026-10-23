---
source: ISSUE-1825
timestamp: '2026-07-30T19:27:00.817092+00:00'
title: create_deploy_fix_tree full deployment BT
type: implementation
---

## Issue #1825 — Implement create_deploy_fix_tree: full deployment BT with guard nodes and call-out seams

PR: <https://github.com/CERTCC/Vultron/pull/1838>

Replaced the Phase 1 `create_deploy_fix_tree` stub (PR #1357) with the full
production `DeployFixBT` Fallback, mirroring the sibling `create_develop_fix_tree`
(#1818). Closes Concern #1813 (stub lacked role/CS/RM guard nodes).

### Delivered

- Four-arm `DeployFixBT` Selector: `CSinStateFixDeployed` early-exit,
  `_ShouldStayInRmDeferred`, `_DeployFixIfReady`, `_MonitorDeploymentIfDesired`.
- Six new production-layer nodes in `report/nodes/deploy_fix.py`.
- `DeployFixCallOutBundle` reduced 5→4 fields (removed `deploy_mitigation_factory`).
- Extracted shared `resolve_case_manager_id` into `participant/common.py`;
  `develop_fix.py` refactored to use it (DRY).
- ~15 new tests; full suite green; black/flake8/mypy/pyright clean.

### Notes

- Pre-PR code review caught a VFD state-machine bug: `CheckCSFixNotYetDeployed`
  now requires exactly `VFd` (fix-ready-not-deployed) so a deployer cannot jump
  `vfd`/`Vfd` → `VFD` under a SUCCESS-returning DeployFix backend. Fixed before merge.
- Intentional scope deviation: legacy non-vendor "public aware" deploy
  precondition omitted per AC-1's enumerated guard set.
