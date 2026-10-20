---
title: Case Bootstrap Trust — Implementation Notes
status: active
kind: guidance
description: >
  Rules for establishing trust in a case and its CASE_MANAGER at non-owner
  sites: the receiver introduces the CASE_MANAGER to the reporter (ADR-0132),
  invites anchor late joiners, the bootstrap payload and the anchors to
  persist, bounded queueing of early CASE_MANAGER messages, and layer rules.
related_specs:
  - specs/case-bootstrap-trust.yaml
  - specs/architecture.yaml (ARCH-12-003)
  - specs/participant-case-replica.yaml
  - specs/actor-knowledge-model.yaml
  - specs/case-management.yaml
  - specs/case-proposal.yaml
related_notes:
  - notes/participant-case-replica.md
  - notes/activitystreams-semantics.md
  - notes/actor-knowledge-model.md
  - notes/datalayer-design.md
  - notes/devcontainer-tooling.md
  - notes/case-proposal.md
relevant_packages:
  - vultron/core/use_cases/received
  - vultron/core/use_cases/triggers
  - vultron/adapters/driving/fastapi
  - vultron/core/behaviors
  - vultron/wire/as2/factories
---

# Case Bootstrap Trust — Implementation Notes

Requirements: `specs/case-bootstrap-trust.yaml` (CBT). Replica rules after
bootstrap: [participant-case-replica.md](participant-case-replica.md).

## Every First Contact Rides an Anchor the Receiver Wrote Itself

A participant trusts a CASE_MANAGER only through an anchor it derived locally,
never through a roster in the payload the sender wrote (CBT-01-011).

- **Original report path**: the reporter's anchor is its own
  `Offer(VulnerabilityReport)` and the actor it sent it to (CBT-01-005). So the
  **report receiver**, not the CASE_MANAGER, sends the reporter the one-time
  `Create(VulnerabilityCase)` that introduces the case and names the CASE_MANAGER
  (ADR-0132, reversing ADR-0041's direct route, #4472). The reporter checks the
  sender against its Offer, the case against its report, then records the
  CASE_MANAGER. A `Create(VulnerabilityCase)` from an actor no local anchor names
  is refused and nothing is stored.
- **Late joiners** have no report exchange, so `InviteActorToCase` is the
  trust-establishing message; the CASE_MANAGER `Announce`s the case after
  acceptance.
- **The receiver's own anchor** is `case_manager_id` from the
  `Accept(CaseProposal)` recorded in `accept_case_proposal_received_tree.py`,
  admitted only from the actor the proposal was addressed to and never once a
  case exists for the report (CP-06-005, CBT-02-003).

`Create` is the introduction verb; `Announce(VulnerabilityCase)` is the
CASE_MANAGER's later sync (CBT-02-001). When owner and CASE_MANAGER are one actor
(CM-02-010), the receiver's message is the only one the reporter gets.

No extra acknowledgement is needed before trusting later CASE_MANAGER updates,
and ordinary updates can never replace the trusted CASE_MANAGER: rotation needs
the explicit transfer workflow. Authenticated or encrypted transport does not
replace this: sender authenticity is weaker than case-specific authority.

## Bootstrap Payload and Persisted Anchors

The bootstrap `Create(VulnerabilityCase)` carries the full inline case with its
participant objects embedded inline (so `store_embedded_participants` can seed
them), naming the case owner (`CASE_OWNER`), the CASE_MANAGER
(`CVDRole.CASE_MANAGER`, not delegated `CASE_OWNER`), the reporter when already
a participant, and the submitted report. The CASE_MANAGER is an identity the
receiver binds to the case, not an opaque service reference.

After a valid bootstrap, persist `report_id → case_id`, the introducing case
creator, and `case_manager_id` together on `VultronReportCaseLink`, so later
handlers reject spoofed senders without re-deriving trust.

Name an actor-id field for the role it records, not the trust relation: a name
containing "trusted" trips CodeQL's clear-text-logging heuristic on every log
line printing a public actor URI (#4020). A stored row carrying a renamed key is
refused on load via `RetiredFieldsRecord`, never aliased (see
[datalayer-design.md](datalayer-design.md) § "Renaming a Stored Field").

## Early CASE_MANAGER Messages Are Queued, Not Rejected (CBT-03)

Rejecting a CASE_MANAGER message that beats the bootstrap would make delivery
order part of protocol correctness. Instead queue it unapplied for a bounded
interval (`AppConfig.pre_bootstrap_queue_timeout_seconds`); on expiry drop it,
warn, and send an `as_Question` asking the **report receiver** — the only actor
already trusted — to resend the bootstrap.

The queue record also carries the stub Invite's trust anchor (`invite_anchored`,
PCR-03-004 path b), so expiry empties an anchored record but keeps it until the
bootstrap arrives and deletes it, and the window opens with the first activity queued,
not with the Invite: the time an invitee takes to answer must not cost it the anchor
that admits the case's `Announce` (#4915).

The queue's `case_actor_id` is a replay target until an Invite sets `invite_anchored`:
the first deferred activity's sender writes it, so any actor could otherwise anchor
itself as CASE_MANAGER of a case the receiver lacks. Read it as an anchor only when
the flag is set, and let a stub Invite replace an unconfirmed sender
(PCR-03-004, #4931).

An Invite-anchored record stays replaceable until the invitee accepts the Invite that
set it: `RecordInviteTrustAnchorNode` stores `anchor_invite_id`, and the accept
trigger's `FixInviteTrustAnchorNode` sets `invite_accepted` on the record it names.
Fixing the anchor any earlier would let a forged stub Invite lock out the real
CASE_MANAGER's until the bootstrap; a forgery the invitee accepts first still wins
until signatures (#2841, PCR-03-004).

## Layer Rules

- Trust-establishment rules live in core use cases and behaviors, not FastAPI
  routers; persisted anchors live in core models, not wire helpers.
- Build outbound bootstrap activities through `vultron.wire.as2.factories`.
- Transport security checks may support the decision but MUST NOT be the sole
  authority check for a new CASE_MANAGER.
