---
status: accepted
date: 2026-08-05
deciders: Allen D. Householder
consulted: []
informed: []
---

# Route Ownership-Transfer Offer and Accept Through the CaseActor

## Context and Problem Statement

The current ownership-transfer protocol has two routing gaps:

1. The offering actor sends `Offer(VulnerabilityCase)` (ownership-transfer
   variant) **directly to the transferee's inbox**, bypassing the CaseActor.
   No CaseLedgerEntry is committed for the offer-in-flight, so participants
   not involved in the transfer (e.g., Finder) receive no notification that
   a transfer is being negotiated.

2. The accepting actor sends `Accept(Offer(VulnerabilityCase))` **directly
   to the offerer's inbox**, bypassing the CaseActor.
   `AcceptCaseOwnershipTransferReceivedUseCase` therefore only runs when the
   Accept is manually self-delivered (as in the FVCV-handoff demo workaround).
   No CaseLedgerEntry is committed after the ownership change, so the Announce
   broadcast never fires and participants not involved in the transfer are
   never notified of the completed ownership change.

Issue: CONCERN-1755, Epic: #1753.

## Decision Drivers

- The canonical communication model (`notes/case-communication-model.md`,
  PCR-08) requires that all case-scoped state changes flow through the
  CaseActor and propagate via `CaseLedgerEntry → Announce` broadcast.
- Participants who are not the old or new owner have no reliable way to
  learn who is currently responsible for a case.  In multi-party cases
  this causes messages to be routed to the wrong actor.
- The Invite/Accept handshake (ADR-0026, PCR-08-007/008) established the
  same principle for participant invitation: the Invite is sent **by** the
  CaseActor, and the Accept is addressed **to** the CaseActor.
  Ownership-transfer should follow the same pattern.

## Considered Options

1. **Route both Offer and Accept through the CaseActor** — the Offer is
   sent to the CaseActor, which records it and forwards to the transferee;
   the Accept is addressed to the CaseActor, which applies the ownership
   change and commits a CaseLedgerEntry → broadcast.
2. **Route Accept through CaseActor only; leave Offer direct** — Accept
   routing is the critical path for the broadcast cascade; Offer routing
   can remain direct.
3. **Keep current routing; add a post-Accept notification trigger** —
   after the offerer receives the Accept, it manually emits an
   `Announce(VulnerabilityCase)` to all participants.
4. **Demo-level workaround only** — keep the protocol underspecified;
   patch the demo.

## Decision Outcome

Chosen option: **Option 1 — route both Offer and Accept through the
CaseActor**, because it aligns with the established canonical communication
model (PCR-08) and ensures all participants receive CaseLedgerEntry
notifications for both the offer-in-flight and the completed transfer.

### Concrete routing model

**Offer flow:**

```text
Offering actor triggers offer-case-ownership-transfer
  → EmitOfferCaseOwnershipTransferNode constructs
    Offer(VulnerabilityCase, target=transferee_id, to=[case_actor_id])
  → CaseActor's OfferCaseOwnershipTransferReceivedUseCase:
      1. Records the offer object.
      2. Commits a CaseLedgerEntry (offer-recorded).
      3. Announce(CaseLedgerEntry) → all participants.
      4. Forwards the Offer to the transferee's inbox.
```

**Accept flow:**

```text
Accepting actor triggers accept-case-ownership-transfer
  → EmitAcceptCaseOwnershipTransferNode constructs
    Accept(Offer(VulnerabilityCase), to=[case_actor_id])
  → CaseActor's AcceptCaseOwnershipTransferReceivedUseCase:
      1. AcceptCaseOwnershipTransferNode applies role changes (CM-21-001–004).
      2. Commits a CaseLedgerEntry (ownership-transferred).
      3. Announce(CaseLedgerEntry) → all participants.
```

### Consequences

- Good, because all participants (including Finder, Vendor2, etc.) are
  notified of both the pending offer and the completed transfer via the
  normal CaseLedgerEntry broadcast — no separate notification mechanism.
- Good, because the `AcceptCaseOwnershipTransferReceivedUseCase` now
  runs automatically on the CaseActor without a manual self-delivery
  workaround.
- Good, because the routing pattern is identical to the Invite/Accept
  handshake (ADR-0026); developers can apply the same mental model.
- Bad, because this is a breaking change to the wire routing for both
  activities; existing devlogs and test fixtures must be updated.
- Bad, because `OfferCaseOwnershipTransferReceivedUseCase` must be
  extended to forward the Offer to the transferee — currently it only
  stores the offer object.

## Validation

- Spec entries CM-21-005 through CM-21-007 in `specs/case-management.yaml`
  encode the MUST requirements; the architecture ratchet tests verify
  boundary compliance.
- The FVCV-handoff demo (`fvcv_handoff_demo.py`) removes the
  `post_to_inbox_and_wait` self-delivery workaround and verifies Finder
  receives an `Announce(CaseLedgerEntry)` for the transfer automatically.
- Unit tests confirm `EmitOfferCaseOwnershipTransferNode` and
  `EmitAcceptCaseOwnershipTransferNode` address the CaseActor.

## More Information

- `notes/case-communication-model.md` — canonical communication model (PCR-08)
- `notes/ownership-transfer.md` — implementation guidance for this routing model
- ADR-0026 — CaseActor-Routed Actor Suggestion (precedent for same pattern)
- CONCERN-1755 — source concern

Generated spec requirements: `specs/case-management.yaml` CM-21-005, CM-21-006,
CM-21-007.
