---
source: ISSUE-1736
timestamp: '2026-07-28T16:34:24.497798+00:00'
title: 'fix(vfd-role-guard): VFD role guards and notify-published fix'
type: implementation
---

## Issue #1736 — fix(vfd-role-guard): gate d→D on DEPLOYER, f→F on VENDOR; fix notify-published VFD bug

Implemented all four acceptance criteria:

- AC-1: `CheckDeployerRoleNode` gates d→D (vfd_state=VFD); returns FAILURE when actor lacks CVDRole.DEPLOYER
- AC-2: `CheckVendorRoleNode` gates f→F (vfd_state=VFd); returns FAILURE when actor lacks CVDRole.VENDOR
- AC-3: `demo_notify_published` no longer passes vfd_state=VFD (only pxa_state=Pxa)
- AC-4: All six demo scenarios updated to remove actor_notifies_fix_deployed for vendor-only actors; terminal state VFd not VFD

New files: vultron/core/behaviors/case/nodes/vfd_role_guards.py, test/core/behaviors/case/nodes/test_vfd_role_guards.py
5602 tests pass, 10 new. PR: <https://github.com/CERTCC/Vultron/pull/1765>
