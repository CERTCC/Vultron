---
source: CONCERN-1288
timestamp: '2026-07-14T15:46:37.523583+00:00'
title: InviteActorToCaseTriggerRequest roles field — dual-path threading
type: learning
---

## Concern: InviteActorToCaseTriggerRequest has no roles field — invited participants always get caseRoles=[]

`InviteActorToCaseTriggerRequest` (in `vultron/core/use_cases/triggers/requests.py`) has only an `invitee_id` field — there is no way to pass the intended `CVDRole` values for the new participant via the **direct trigger path**. As a result, every participant created via the `invite-actor-to-case` trigger gets `caseRoles=[]`.

Confirmed in the FVV demo logs (#1265 / PR #1270): Vendor2's participant status entries throughout the run show `roles=[]` despite being invited as a vendor.

> **Scope note (added 2026-07-09):** This issue covers the **direct trigger path** (`invite-actor-to-case` REST trigger → `InviteActorToCaseTriggerRequest`). The **suggest-actor path** (Recommender → CaseActor → `Offer(CaseParticipant)` → Case Owner → Accept → CaseActor → Invite) has its own roles thread, documented in CM-16-003 and tracked by #1300. #1288 must be implemented *after* #1300 so that `EmitInviteActorToCaseNode` already supports reading roles from the blackboard (set by either path) before the trigger-path roles injection is added.

## Root cause

`InviteActorToCaseTriggerRequest`:

```python
class InviteActorToCaseTriggerRequest(CaseTriggerRequest):
    invitee_id: NonEmptyString
    # no roles field
```

`invite_actor_to_case_trigger_bt` → `EmitInviteActorToCaseNode` constructs the `RmInviteToCaseActivity` without role information. On the received side, `CreateInviteeParticipantAtAcceptedNode` creates the `CaseParticipant` from whatever roles were embedded in the Invite wire object — which is empty.

## Impact

- All directly-triggered invites produce participants with no CVD roles, breaking AC-2 of #1265 ("all three actors have correct CVDRole values")
- The FVV scenario spec requires Vendor2 to hold `CVDRole.VENDOR`
- The three-actor demo's `coordinator_invites_actor` works around this by using `three_actor_demo.py`'s own `rm_invite_to_case_activity` factory call directly (not the trigger endpoint), which can embed roles — but the trigger endpoint cannot

## Resolution

**Resolved**: 2026-07-14 — implementation was already complete via PR #1346 (shipped with #1300). The roles field was added to `InviteActorToCaseTriggerRequest`, threaded through `SvcInviteActorToCaseUseCase._extra_execute_kwargs()` → blackboard `suggested_roles` key → `EmitInviteActorToCaseNode` → factory → wire Invite → `CreateInviteeParticipantAtAcceptedNode`. The FVV demo was updated to pass `"roles": ["vendor"]`.

Residual spec gap (dual-path blackboard threading not documented): addressed in Docs PR #1404.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1404>.
Implementation tracked in #1405 (test coverage — direct trigger path), #1406 (test coverage — suggest-actor received path).
