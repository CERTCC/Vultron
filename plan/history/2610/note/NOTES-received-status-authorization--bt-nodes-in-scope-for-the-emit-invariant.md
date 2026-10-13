---
source: NOTES-received-status-authorization--bt-nodes-in-scope-for-the-emit-invariant
timestamp: '2026-10-12T19:34:54.104349+00:00'
title: BT nodes in scope for the emit invariant
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — every row reads "Implemented (#2857)"; an inventory of the rollout, not a rule
**Superseded by:** RSH-04-002, RSH-04-003; `EmitCaseStatusUpdateNode` in `vultron/core/behaviors/status/nodes/`; notes/received-status-authorization.md § "CaseStatus emission authority (RSH-04)"

---

## BT nodes in scope for the emit invariant

| Node / Tree | EM transition | Covered by `EmitCaseStatusUpdateNode`? |
|---|---|---|
| `ProposeEmbargoLifecycleNode` in `propose_embargo_trigger_bt` (initial proposal) | NONE → PROPOSED | Implemented (#2857) |
| `ProposeEmbargoLifecycleNode` in `propose_embargo_revision_trigger_bt` (revision, with `ValidateEmbargoRevisionStateNode` guard) | ACTIVE → REVISE | Implemented (#2857) |
| `AcceptEmbargoLifecycleNode` (trigger) | PROPOSED → ACTIVE | Implemented (#2857) |
| `RejectEmbargoLifecycleNode` (trigger) | PROPOSED → NONE | Implemented (#2857) |
| `TerminateEmbargoLifecycleNode` (trigger) | ACTIVE/REVISE → EXITED | Implemented (#2857) |
| `AbandonEmbargoProposalsLifecycleNode` (cascade, CASE_MANAGER only) | PROPOSED → NONE | Implemented (#2857, #4131) |
| `ApplyEmbargoTeardownNode` (sync/announce) | ACTIVE/REVISE → EXITED | Implemented (#2857) |
