---
title: deploy_fix.py is at the 500-line BTND-07-004 limit after ports migration
type: learning
timestamp: 2026-08-21T16:30:00Z
source: ISSUE-1884
signal: concern
---

After migrating Type-A nodes in `vultron/core/behaviors/report/nodes/deploy_fix.py`
(PR #2464), the file sits at exactly 500 lines — the BTND-07-004 hard limit.

The import expansion (1-line → 5-line block for three helpers) consumed the
available margin. A single-line addition anywhere in the file will now trigger
the structure test failure.

**Recommendation**: before the next change to `deploy_fix.py`, split it by
semantic concern — e.g. `deploy_fix_conditions.py` (guards: `CSinStateFixDeployed`,
`CheckCSFixNotYetDeployed`, `RMinStateDeferred`, `CheckNoNewDeploymentInfoNode`)
and `deploy_fix_actions.py` (transitions and emit: `TransitionCStoFixDeployed`,
`EmitCDActivity`).

**Promoted**: 2026-08-24 — captured in archive only (not creating concern per user decision).
Docs PR: [PR URL TBD].
