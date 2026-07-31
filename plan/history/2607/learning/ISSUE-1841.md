---
title: CheckIsCaseOwnerNode placed in vfd_role_guards.py due to BTND-07-004 line limit
type: learning
timestamp: 2026-07-30T00:00:00Z
source: ISSUE-1841
signal: design-question
---

Issue #1841 implied `CheckIsCaseOwnerNode` would live in
`vultron/core/behaviors/case/nodes/conditions.py` (alongside other idempotency guard
conditions). However, the concurrent PR for issue #1835 added
`CheckPendingProposalExistsForReport` and `WritePendingReportCaseLinkNode` to
`conditions.py`, pushing it to 436 lines on `origin/main`. Adding `CheckIsCaseOwnerNode`
(~90 lines) pushed the merged result to 530 lines — over the 500-line BTND-07-004 limit.

Decision: move `CheckIsCaseOwnerNode` to `vultron/core/behaviors/case/nodes/vfd_role_guards.py`
(184 lines before the move, 280 after). It is semantically cohesive there — it checks a
CVDRole (`CASE_OWNER`) via `actor_participant_index`, exactly like `CheckVendorRoleNode`
and `CheckDeployerRoleNode`. The `__init__.py` re-exports it alongside the other two, so
call sites import from the package and are unaware of the submodule change.

Future: if `conditions.py` continues to grow, consider extracting the proposal-related
nodes into `proposal_conditions.py`.

**Promoted**: 2026-07-31 — captured in `AGENTS.md` (CheckIsCaseOwnerNode module placement pitfall).
Docs PR: TBD.
