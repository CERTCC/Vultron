---
source: CONCERN-893
timestamp: '2026-06-10T21:12:10.998787+00:00'
title: Invite/Accept routing and received-side identity spoofing
type: learning
---

## Summary

In `vultron/core/use_cases/received/actor.py`,
`AcceptInviteActorToCaseReceivedUseCase.execute()` calls
`create_prioritize_subtree(actor_id=invitee_id)` using the **case
owner's** DataLayer and `trigger_activity`. This causes two violations:

1. **Identity spoofing**: `EmitEngageCaseActivity` produces an
   `RmEngageCaseActivity` with `actor=invitee_id` but authored by the
   owner's factory.
2. **PCR-model violation**: The invitee's RM state transition
   (VALID → ACCEPTED) is authored by the owner, not the invitee
   (PCR-08-001, PCR-08-002).

During planning, a second entangled concern was identified (#894): the
entire Invite/Accept handshake routes directly through the case owner,
bypassing the Case Actor as the authoritative intermediary.

## Protocol Design Decision

The correct model is "owner triggers, Case Actor executes":

- `SvcInviteActorToCaseUseCase` resolves the Case Actor ID and builds
  `RmInviteToCaseActivity` with `actor=case_actor_id` (optionally
  `attributedTo=case_owner_id`), placed in the Case Actor's outbox.
- The invitee's `Accept` is addressed to the **Case Actor** inbox.
- The Case Actor's `AcceptInviteActorToCaseReceivedUseCase` records the
  invitee's RM VALID→ACCEPTED inline — no `PrioritizeBT`, no spoofed
  emit. `Accept(Invite)` IS the engage decision.

## Outcome

**Resolved**: 2026-06-10 — implementation tracked in #896 (blocked by
[#893](https://github.com/CERTCC/Vultron/issues/893) and
[#894](https://github.com/CERTCC/Vultron/issues/894)).
Docs PR: [#895](https://github.com/CERTCC/Vultron/pull/895).
Spec: `specs/participant-case-replica.yaml` (PCR-08-007 through
PCR-08-010, PCR-07-008).
Notes: `notes/case-communication-model.md` § Invite/Accept Handshake
Routing.
