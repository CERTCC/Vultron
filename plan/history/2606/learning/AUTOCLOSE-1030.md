---
source: AUTOCLOSE-1030
timestamp: '2026-06-22T19:35:22.731325+00:00'
title: Autoclose trigger must be idempotent with respect to CaseLedger commits
type: learning
---

When implementing the `AutoCloseCaseNode` BT leaf, ensure the transition
from `RM.OPEN → RM.CLOSED` is guarded by a pre-check for `RM.CLOSED`
terminal state: if the case is already closed, the node MUST return SUCCESS
without re-enqueuing a `CommitCaseLedgerEntry`. Without this guard, repeated
BT ticks on a closed case produce duplicate canonical ledger entries and break
the hash-chain. The guard is `ValidateRMTransitionNode`, which must run
BEFORE the same-state shortcut check.

**Promoted**: 2026-06-22 — captured in `specs/behavior-tree-integration.yaml`
(BT-17-001: RM terminal guard must run before same-state no-op) and
`notes/bt-integration.md` (Role Guard for All CASE_MANAGER-Only Subtrees,
autoclose variant).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
