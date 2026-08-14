---
title: Received-side use cases must pass receiving_actor_id to execute_with_setup
type: learning
timestamp: "2026-08-13"
source: ISSUE-2300
signal: spec-gap
---

BT-17-005 in AGENTS.md says *guarded-commit tests* must use the CASE_MANAGER
actor as `receiving_actor_id` in `execute_with_setup`. The same rule applies
to *production received-side use cases*.

`EngageCaseReceivedUseCase` and `DeferCaseReceivedUseCase` were passing
`request.actor_id` (the sender) instead of `request.receiving_actor_id` (the
CaseActor). `CheckIsCaseManagerNode` compared the sender against the case's
CASE_MANAGER, found a mismatch, and skipped the ledger commit via the "not a
manager" guard. `engage_case` never appeared in the CaseActor's ledger.

Rule to add to specs/BT spec: any received-side use case that executes a BT
containing `GuardedCommitCaseLedgerEntryBT` MUST call `execute_with_setup`
with `actor_id=request.receiving_actor_id`. The `actor_id` field in those
events is the *sender*; `receiving_actor_id` is the *receiver* (CaseActor).

BT nodes that need to target the *sender's* participant (e.g.
`TransitionParticipantRMtoAccepted`) must store the actor ID in a private
attribute (e.g. `_target_actor_id`) to prevent `DataLayerAction.setup()`
from overwriting it with the blackboard's `actor_id`.

Related: BT-17-005, BT-06-006, CLP-10-006, ISSUE-2300.
