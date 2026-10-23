---
source: CONCERN-1036
timestamp: '2026-06-18T19:10:32.546350+00:00'
title: 'Case-actor vs other-actor handling: CASE_MANAGER checks must be BT guards,
  not precomputed dispatch state'
type: learning
---

## Summary

When an activity arrives, the inbox that received it determines the handling
branch: a case actor's inbox does case-actor things (update case state, add
case ledger entries, broadcast); any other actor's inbox either receives
direct messages that don't touch case state, or receives case-ledger entries
announced by the case actor and updates its local replica. This distinction
must be visible from the very start of the inbox processor — not derived
partway through `execute()` by recomputing which actor/role is in play.
Several `execute()` methods instead started under one actor context and then
resolved a *different* actor (the case manager) mid-method to perform the
ledger commit via a second, separately-gated `execute_with_setup()` call —
the actor-switching anti-pattern this Concern targeted.

The fix is not to split into two BTs per inbox type — same dispatch is fine
— but role-gated branches (e.g. "CASE_MANAGER role only") must be guard
nodes evaluated *inside* the BT, not a boolean precomputed in Python that
gates whether a second tree execution happens at all.

## Evidence (original, 3 sites)

- `vultron/core/use_cases/received/embargo.py`:
  `RemoveEmbargoEventFromCaseReceivedUseCase.execute`,
  `InviteToEmbargoOnCaseReceivedUseCase.execute`,
  `AcceptInviteToEmbargoOnCaseReceivedUseCase.execute` — each started under
  `request.actor_id`, then resolved a separate `commit_actor_id` (case
  manager) and ran a second tree under that identity, outside any BT guard.
- `vultron/core/use_cases/received/report.py`:
  `ValidateReportReceivedUseCase.execute`, `AckReportReceivedUseCase.execute`
  — same pattern.
- `CheckIsCaseManagerNode` (used inside
  `create_guarded_commit_case_ledger_entry_tree`) already showed the correct
  shape — an in-tree guard — but was reached only via a second,
  separately-dispatched tree under a different actor_id.

## Resolved: 2026-06-18

Planning (via `plan-issue`) broadened the audit and found this exact shape in
**9 use cases across 6 modules** (roughly 3x the originally cited evidence):
`embargo.py` (3), `report.py` (2), `note.py`, `status.py`,
`case/lifecycle.py`, and `actor/case_manager_role.py`.

Investigation also resolved an open architectural question: whether the
inbox dispatch pipeline itself needed restructuring so a use case never has
to ask "which actor am I running as." It does not —
`receiving_actor_id` is already resolved before dispatch
(`FastAPIDispatchAdapter.dispatch()`), and the dispatcher has no CaseActor
awareness and needs none (pure routing-table lookup). The gap is entirely at
the use-case/BT boundary.

**ADR-0022** (`docs/adr/0022-single-bt-execution-for-received-side-case-actor-routing.md`)
amends ADR-0021's call shape: a received-side use case MUST execute exactly
one BT per inbox delivery (`actor_id=receiving_actor_id`); CASE_MANAGER-gated
commits must be an in-tree Selector/Sequence/Success branch of that same
tree. `specs/case-ledger-processing.yaml` CLP-10-005 codifies the rule.
`notes/bt-integration.md` and `notes/case-communication-model.md` were
updated with the finding. A ratchet test
(`test/architecture/test_single_bt_execution_received_side.py`) enumerates
the 9 known-violating use cases as `KNOWN_VIOLATIONS`.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1049>.
Spec: `specs/case-ledger-processing.yaml` CLP-10-005.
Implementation tracked in #1050 (embargo.py — foundation issue, absorbs
superseded issue #1038), #1051 (report.py, blocked-by #1050), #1052
(note.py/status.py/case/lifecycle.py/actor/case_manager_role.py,
blocked-by #1050).
