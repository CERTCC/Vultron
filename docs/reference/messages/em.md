---
stakeholder_type: [platform-developer]
level: 400
description: >
  Wire activities for the Embargo Management message types EP, ER, EA, EV, EJ, EC, ET, EK, and EE, and the Case Owner's decision on a proposal.
---

# Embargo Management (EM) Messages

The EM process is global to the case. A Participant emits an EM message when the
case's EM state changes. The AS2 wire vocabulary **collapses** the
revision-negotiation shorthands onto their initial-negotiation counterparts:
`EV` is sent as `EP`, `EJ` as `ER`, and `EC` as `EA`, discriminated by EM state
context rather than by a payload field (MSM-02).

## Occasions

{% include-markdown "./_occasions/lookup-em.md" %}

{% include-markdown "./_occasions/sections/create-embargo-event.md" %}

- **Triggering transition:** none (object construction).
- **Context:** the case, or the report before a case exists (VAM-05-001).

{% include-markdown "./_occasions/sections/embargo-proposal.md" %}

- **Triggering transition:** None or Proposed → Proposed ({N,P} → P).
- **Wire form:** `Invite(Event)[context=VulnerabilityCase]`, and no other (MSM-02-001).

{% include-markdown "./_occasions/sections/announce-embargo.md" %}

`Announce(Event)` also carries notice of a change significant enough to warrant attention beyond the corresponding `CaseStatus` message, such as an embargo being removed from a case.

When the CASE_MANAGER activates a revision that ends no later than the embargo it replaces, it sends `Announce(Event)` with the new terms directly to each bound signatory that no longer receives ledger entries (removed, or at Report Management (RM) `CLOSED`).
That participant applies the new terms only when the CASE_MANAGER sent them.
A revision that ends later sends no such notice, because those participants never agreed to it.

{% include-markdown "./_occasions/sections/embargo-proposal-rejection.md" %}

- **Triggering transition:** Proposed → None (P → N), or Proposed → Proposed (P → P) while another proposal is open (EMB-18-005).
- **Who decides:** a `Reject` of the Invite is always the sender's own refusal of those terms, the Case Owner's included.
  It changes no embargo on the case (see [The Case Owner's Decision](#the-case-owners-decision)).
- **Refusal on a public case:** a receiver answers an `EP` with `ER` when the case is public, an exploit is public, or attacks are observed.
  The `ER` names the Invite by id, so it is sent even when the Invite named its terms only by URI.
  A receiver sends one `ER` per Invite: a re-delivered Invite is skipped.
- **Malformed Invite:** an `EP` that names no `to` recipient or several is not answered with `ER`.
  It is received but not understood, so the receiver sends `Create(ProcessingFault)` to the sender.

{% include-markdown "./_occasions/sections/embargo-proposal-acceptance.md" %}

- **Triggering transition:** Proposed → Active (P → A), or Proposed → Revise (P → R) while another proposal stays open as a revision (EMB-18-005).
- **Who decides:** an `Accept` of the Invite is always the sender's own consent to those terms, the Case Owner's included.
  It changes no embargo on the case (see [The Case Owner's Decision](#the-case-owners-decision)).

{% include-markdown "./_occasions/sections/embargo-revision-proposal.md" %}

- **Triggering transition:** Active → Revise (A → R).

{% include-markdown "./_occasions/sections/embargo-revision-rejection.md" %}

- **Triggering transition:** Revise → Active (R → A), or Revise → Revise (R → R) while another proposal is open (EMB-18-005).
- **Who decides:** as for `ER`, the `Reject` is the sender's own refusal (see [The Case Owner's Decision](#the-case-owners-decision)).

{% include-markdown "./_occasions/sections/embargo-revision-acceptance.md" %}

- **Triggering transition:** Revise → Active (R → A), or Revise → Revise (R → R) while another proposal is open (EMB-18-005).
- **Who decides:** as for `EA`, the `Accept` is the sender's own consent (see [The Case Owner's Decision](#the-case-owners-decision)).

## The Case Owner's Decision

The Case Owner decides each embargo proposal for the case with an activity of its own.
Its object is the proposed `Event` itself, not the Invite that proposed it, and its target is the case.
Only the Case Owner may send either activity, and it sends them to the Case Manager.
Any other sender is refused.
The Case Manager records the decision in the case ledger, and every participant learns it from there.

These two activities carry no shorthand of their own.
They are how the case takes the `EA`, `EC`, `ER`, and `EJ` transitions above, while the `Accept` and `Reject` of each Invite record each participant's consent.

{% include-markdown "./_occasions/sections/activate-embargo.md" heading-offset=1 %}

The Case Owner's own consent to the activated terms is recorded with it.
When the new terms end no later than the ones they replace, every participant that agreed to the old terms is bound by the new ones too.
The Case Manager refuses an activation once the case is public, an exploit is public, or attacks are observed.
It also refuses one from a Case Owner that has refused those terms, until that Case Owner is invited again.

{% include-markdown "./_occasions/sections/reject-embargo-proposal.md" heading-offset=1 %}

If an embargo is active, it stays in force on its current terms (`EJ`); otherwise the case has no embargo (`ER`).
While another proposal is still open, the case stays in negotiation.
No participant's consent changes, the Case Owner's included.
If the case is public, an exploit is public, or attacks are observed when the Case Owner rejects the last open revision, the Case Manager ends the embargo instead (`ET`).

{% include-markdown "./_occasions/sections/embargo-termination.md" %}

- **Triggering transition:** Active or Revise → eXited ({A,R} → X).
- **Reason:** `content` says what ended the embargo, exactly `END_TIME_REACHED` or `EARLY`.
  A receiver refuses a `Remove` whose `content` is anything else.
  `summary` is a human-readable account that the protocol does not read.
- **Why it ended:** the Case Manager's embargo register records a cause beside the reason when it knows one.
  A termination caused by public awareness, a public exploit or observed attacks carries `EARLY`, and the register names the signal.
  The termination message does not carry the cause, so a replica that learns of the termination from it records only the reason.
- **At the end time:** when the end time of the embargo in force has passed, the Case Manager ends it with `END_TIME_REACHED`.
  It does so the next time it handles the case, or when an outside service such as a [Sentinel](../glossary.md) asks it to.
  Whichever comes second finds the embargo already ended and sends nothing.
  A `Remove` that claims `END_TIME_REACHED` before the embargo's end time is refused.
- **Bound participants that are no longer active:** a signatory that was removed from the case, or that left it and is at RM `CLOSED`, stays bound by the embargo but no longer receives ledger entries.
  The CASE_MANAGER sends each such participant `ET` directly, one activity per participant, outside the ledger stream.
  The notice carries the embargo and nothing else, and it is not a ledger entry.
  The participant applies it only when the CASE_MANAGER sent it.
  A termination on or after the embargo's agreed end date is expiry, and sends no notice.

## Formal messages with no dedicated wire activity

### EK — Embargo Acknowledgment

- **Protocol role:** Acknowledges receipt of an EM message.
- **Triggering transition:** any valid EM message.
- **Wire activity:** none dedicated. Acknowledgment of ledger-replicated state
  is cumulative and implicit through hash-chain continuity; a per-message `EK`
  would be redundant
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types).

### EE — Embargo Error

- **Protocol role:** Indicates a Participant received an unexpected EM message.
- **Triggering transition:** any unexpected EM message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)`, `as:Reject`, or `Create(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types).
