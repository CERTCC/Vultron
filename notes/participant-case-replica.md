---
title: Participant Case Replica — Implementation Notes
status: active
kind: guidance
description: >
  Rules for participant case replicas: one inbox per actor with internal
  routing on `context`, the CASE_MANAGER as sole replica writer, the
  locally-derived trust anchors a seeding Announce needs, the late-joiner
  cascade, report-to-case linking, and actor-scoped deferral of activities
  with an unknown case context.
related_specs:
  - specs/architecture.yaml
  - specs/participant-case-replica.yaml
  - specs/case-bootstrap-trust.yaml
  - specs/case-management.yaml
  - specs/sync-ledger-replication.yaml
related_notes:
  - notes/case-communication-model.md
  - notes/case-ledger-authority.md
  - notes/sync-ledger-replication.md
  - notes/case-joining.md
  - notes/case-bootstrap-trust.md
relevant_packages:
  - vultron/core/behaviors/case
  - vultron/core/models
  - vultron/core/use_cases
---

# Participant Case Replica — Implementation Notes

Requirements: `specs/participant-case-replica.yaml` (PCR). First-contact
bootstrap is in [case-bootstrap-trust.md](case-bootstrap-trust.md).

## One Actor, One Inbox, Routing on `context`

A participant is one externally addressable actor with one inbox; case-scoped
routing is internal. Do not create per-participant or per-case actor clones:
they explode the actor registry for no protocol benefit.

- Every case-scoped activity, in both directions, MUST carry `context` set to
  the case ID (PCR-04-002); the inbox uses it to find the local replica.
- The enacting "CaseActor" is one per container, not one per case, at
  `{case_actor_service_url}/actors/case-actor` (CP-08-002/003). Its label is
  cosmetic: gate on `CVDRole.CASE_MANAGER`, never compare `actor_id` to a
  computed case-actor id (CM-24-004, ADR-0088).

## Only the CASE_MANAGER Writes a Replica

Only the case's CASE_MANAGER may update a participant's replica; any other
sender is rejected and logged at WARNING (CM-02-002). The case owner follows the
same rule: its writes pass through the CASE_MANAGER role whether the two are one
actor or two (CM-02-010).

## A Seeding Announce Needs a Locally Derived Anchor (PCR-03-004)

A participant MUST NOT create a replica from an arbitrary
`Announce(VulnerabilityCase)`. The use case declares
`SenderRule.in_case(CASE_MANAGER)`, and the announce tree passes
`case_manager_anchored=True`, so the composed `SenderIsCaseManagerNode` admits
the sender only against an anchor the receiver derived itself (HP-01-008):

1. **Report path**: a completed `VultronReportCaseLink` recording
   `case_manager_id` (written on the creator-signed `Create(VulnerabilityCase)`).
   It comes first because ordinary case traffic never replaces it (CBT-02-003).
   Else the CASE_MANAGER role-holder on an existing replica.
2. **Invite path**: a `VultronPendingCaseInbox` anchor written when the receiver
   processed `InviteActorToCase` (`RecordInviteTrustAnchorNode`, #4185). It is
   written only if the Invite's `object` is the receiving actor; it binds to the
   Invite's `actor` field, not the transport sender; a later Invite naming a
   different CaseActor replaces an anchor the invitee has not accepted, so a
   forged Invite cannot lock out the real one; and once `FixInviteTrustAnchorNode`
   records the invitee's Accept (`invite_accepted`), such an Invite is refused,
   leaving the anchor unchanged (PCR-03-004).

No anchor means **reject**, never accept: no legitimate sequence delivers a
first-contact Announce without a preceding Create or Invite (PCR-07-010, #3273).
Do not fall back to the announced roster in the payload: the sender supplies
it, so a fabricated case naming the sender as CASE_MANAGER
passes (#3274). Do not reintroduce the retired `Service`-hosting scan
(ARCH-24-004). Whether the named CaseActor is genuine awaits signatures (#2841).

## Late Joiners: Cascade from `Accept(Invite(stub))`

The invitee's record already exists, inert, from when the stub Invite was sent
(`CreateInertInviteeParticipantNode`, CM-11-006). On the stub Accept the
accept-invite tree activates that record (RM stays RECEIVED, CM-11-001), sends
`Announce(VulnerabilityCase)` and the ledger replay (CM-11-008), then the
full-case Invite queued after the last replayed entry (CM-11-010). This cascade
is BT subtree work in `vultron/core/behaviors/case/`, not a procedural call in
`execute()`. Full flow: [case-joining.md](case-joining.md).

## Report-to-Case Linking

A reporter records a `VultronReportCaseLink` (`vultron/core/models/`, no wire
types) when it submits `Offer(VulnerabilityReport)`. When a later case snapshot
lists that report in `vulnerability_reports`, the link gains the case ID, so the
reporter recognizes the case as the outcome of its own submission.

## Unknown Case Context: Queue, Never Apply (PCR-06)

An activity whose `context` matches no local replica MUST NOT be discarded and
MUST NOT update local state; queue it, request a snapshot, and replay it once
the replica is seeded. The queue MUST be keyed by both receiving actor and case
ID (`vultron/core/models/pending_case_inbox.py`, PCR-06-004): a global queue
replays one co-located actor's activities against another's replica.
