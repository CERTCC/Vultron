---
source: CONCERN-1054
timestamp: '2026-06-26T20:07:45.486961+00:00'
title: Terminate embargo BT — routing-gated state mutation (BT-19)
type: learning
---

## Code Review — Advisory Finding

**[ADVISORY — Pre-existing, not introduced by this PR]**

The code-review agent flagged a potential issue in
`vultron/core/behaviors/embargo/nodes/lifecycle.py`
(`TerminateEmbargoNode.update()`): embargo state is committed to the DataLayer
*before* `_dispatch_activity` is called, so when dispatch returns `FAILURE`
(no factory, no Case Manager, etc.) the BT FAILURE propagates up to the use
case, which then skips `_commit_log_cascade_bt`. This means the
`Announce(CaseLedgerEntry)` fan-out — the very mechanism this PR and
\#1043/\#1046 rely on for peer notification — is suppressed on teardown
dispatch failures.

**Root cause**: `TerminateEmbargoNode` is a monolith that inlines both the EM
state-machine transition (committing `em_state=EXITED`, `active_embargo=None`,
and PEC reset to DataLayer) and the outbound activity dispatch in a single
`update()` method. When dispatch fails — most commonly because no
`CVDRole.CASE_MANAGER` participant is registered — the local state is already
committed but peers were never notified, causing silent EM state divergence.

**Dual-implementation concern**: Two independent implementations exist for
embargo termination. The trigger-side path (`SvcTerminateEmbargoUseCase` via
`terminate_embargo_trigger_bt`) is factory-composed and uses the
`EmbargoLifecycle` service. The automatic-cascade path (`PublicDisclosureBranchNode`
via `TerminateEmbargoNode`) is a monolith using the older inline `EMAdapter` +
`create_em_machine()` pattern. These drift independently.

**Resolution**: Spec requirements BT-19-001 and BT-19-002 were added to
`specs/behavior-tree-integration.yaml` to capture (1) the routing-prerequisites-
before-state-mutation ordering rule and (2) the shared-factory requirement.
The outbox is the reliability boundary: once the activity is written to the
outbox, delivery and retry are the outbox's responsibility; residual mid-send
failures are recoverable via ledger-sync catch-up (SYNC-10).

**Resolved**: 2026-06-26 — implementation tracked in #1204.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1203>.
Spec: `specs/behavior-tree-integration.yaml` BT-19-001, BT-19-002.
