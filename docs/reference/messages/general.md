---
stakeholder_type: [platform-developer]
level: 400
description: >
  Wire activities for the General message types GI, GK, and GE.
---

# General (GI) Messages

The General shorthands cover messages not tied to a specific state change.
`GI` **expands** across the note lifecycle and the actor-suggestion handshake; the occasion table below lists each wire activity it covers.

## Occasions

{% include-markdown "./_occasions/lookup-general.md" %}

## GI — General Inquiry

- **Protocol role:** Communicates non-state-change information — asking or answering a question, requesting a status update or a draft review, suggesting a Participant for a case, or resolving a loss of state synchronization.
- **Triggering transition:** none (any time).
- **Wire activities:** `GI` expands across the actor-suggestion handshake and the note lifecycle, one section each below.
  Suggesting a Participant is a `GI` inquiry, not a case-management message.
- **Formal definition:** [Message Types](../formal_protocol/messages.md#other-message-types).

{% include-markdown "./_occasions/sections/suggest-actor-to-case.md" heading-offset=1 %}

{% include-markdown "./_occasions/sections/request-invite-actor-to-case.md" heading-offset=1 %}

For an actor with no record on the case, or an invitee that has not answered (CM-11-015), the CASE_MANAGER sends the Stub Invite directly, because the Case Owner who would decide on a suggestion is the sender (CM-17-007).
An actor already on the case or already awaiting the Case Owner's decision gets the same answer a suggestion gets (CM-16-008, CM-16-009).

{% include-markdown "./_occasions/sections/offer-case-participant.md" heading-offset=1 %}

The original recommendation's ID is carried in the Offer's `origin`.

{% include-markdown "./_occasions/sections/accept-case-participant-offer.md" heading-offset=1 %}

The Case Owner's decision goes back to the CASE_MANAGER, which relays the outcome to the recommender.

{% include-markdown "./_occasions/sections/reject-case-participant-offer.md" heading-offset=1 %}

This handshake is a `GI` inquiry rather than a role offer.
For the `CVDRole` delegation that uses a dedicated object type, see [Offer case participant role](case_management.md#offer-case-participant-role).

{% include-markdown "./_occasions/sections/add-note-to-case.md" heading-offset=1 %}

{% include-markdown "./_occasions/sections/remove-note-from-case.md" heading-offset=1 %}

- **Who may send:** the CASE_MANAGER admits `Remove(Note)[target=VulnerabilityCase]` from the note's author while that author is an active participant, or from the Case Owner.
  Any other sender is refused, and the note stays in the case.
  A participant replica accepts it only from the CASE_MANAGER, because replicas learn of the change from the ledger entry the CASE_MANAGER fans out.

## Formal messages with no dedicated wire activity

### GK — General Acknowledgment

- **Protocol role:** Acknowledges receipt of a `GI` message.
- **Triggering transition:** any valid `GI` message.
- **Wire activity:** none dedicated. Acknowledgment of ledger-replicated state
  is cumulative and implicit through hash-chain continuity
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#other-message-types).

### GE — General Error

- **Protocol role:** Indicates a general error has occurred.
- **Triggering transition:** any unexpected `GI` message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)`, `as:Reject`, or `Add(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#other-message-types).
