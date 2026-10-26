---
stakeholder_type: [platform-developer]
level: 400
page_type: reference
description: >
  Wire activities for the Embargo Management message types EP, ER, EA, EV, EJ, EC, ET, EK, and EE, the Case Owner's decision on a proposal, and a participant's withdrawal from the embargo in force.
---

# Embargo Management (EM) Messages

The EM process is global to the case. A Participant emits an EM message when the
case's EM state changes. The AS2 wire vocabulary **collapses** the
revision-negotiation shorthands onto their initial-negotiation counterparts:
`EV` is sent as `EP`, `EJ` as `ER`, and `EC` as `EA`, discriminated by EM state
context rather than by a payload field (MSM-02).

An embargo proposal carries its `EmbargoEvent` inline on the `Invite` that proposes it.
The protocol names `Invite(EmbargoEvent)` as the one form; a received `Create(EmbargoEvent)` is not a protocol message, and its receiver must not change the case file because of it ([ADR-0137](../../adr/0137-case-records-are-attached-by-one-message-never-created-first.md), VAM-01-011).
This implementation's inbox refuses one as an unrecognized activity and changes nothing (VAM-01-010).

## Occasions

{% include-markdown "./_occasions/lookup-em.md" %}

{% include-markdown "./_occasions/sections/embargo-proposal.md" %}

- **Triggering transition:** None or Proposed → Proposed ({N,P} → P).
- **Wire form:** `Invite(EmbargoEvent)[context=VulnerabilityCase]`, and no other (MSM-02-001).

{% include-markdown "./_occasions/sections/relay-embargo-proposal.md" %}

- **Recipient:** one Invite per participant other than the proposer, each addressed to that participant alone, so its answer names the Invite it received (EP-09-002, EP-09-010).

{% include-markdown "./_occasions/sections/announce-embargo.md" %}

When the CASE_MANAGER activates a revision that ends no later than the embargo it replaces, it sends `Announce(EmbargoEvent)` with the new terms directly to each bound signatory that no longer receives ledger entries (removed, or at Report Management (RM) `CLOSED`).
That participant applies the new terms only when the CASE_MANAGER sent them.
A revision that ends later sends no such notice, because those participants never agreed to it.

{% include-markdown "./_occasions/sections/announce-embargo-termination.md" %}

- **Recipient:** every active participant other than the CASE_MANAGER and any Closed Participant, after the CASE_MANAGER applies a Case Owner's `Remove(EmbargoEvent)` that arrives before the end time (EMB-19-001, CM-10-004, CM-23-004).
  A termination the CASE_MANAGER starts itself, or one at the end time, sends no `Announce(EmbargoEvent)`.
  A bound signatory that no longer receives ledger entries gets the CASE_MANAGER's own `Remove(EmbargoEvent)` instead (CM-31-009).

{% include-markdown "./_occasions/sections/embargo-proposal-rejection.md" %}

- **Triggering transition:** Proposed → None (P → N), or Proposed → Proposed (P → P) while another proposal is open (EMB-18-005).
- **Who decides:** a participant's `Reject` of the Invite is its own refusal of those terms, the Case Owner's included.
  It changes no embargo on the case (see [The Case Owner's Decision](#the-case-owners-decision)).
- **The Case Manager's `Reject`:** when the case becomes public, an exploit is public or attacks are observed while a proposal is open, the Case Manager rejects each proposal it received.
  That `Reject` cancels the proposal (EMB-16-001).
  A replica tells it from a participant's `Reject` by its `actor`.
  The Case Manager never sends a `Reject` of an Invite as its own consent: a Case Manager with a stake in the embargo records its answer as its own update of its consent row.
- **Refusal on a public case:** a receiver answers an `EP` with `ER` when the case is public, an exploit is public, or attacks are observed.
  The `ER` names the Invite by id, so it is sent even when the Invite named its terms only by URI.
  A receiver sends one `ER` per Invite: a re-delivered Invite is skipped.
- **Malformed Invite:** an `EP` that names no `to` recipient or several is not answered with `ER`.
  It is received but not understood, so the receiver sends `Create(ProcessingFault)` to the sender.

{% include-markdown "./_occasions/sections/withdraw-embargo-invite.md" %}

- **Triggering transition:** Proposed → None (P → N) with the last open proposal, when the `Undo` withdraws the Case Manager's own proposal; otherwise none.
- **Order:** for each abandoned proposal, the cancel comes first: the Case Manager's `Reject` of a proposal it received, or its `Undo` of one it made itself.
  An `Undo` of each invitation it relayed for the proposal follows, and changes nothing more.
  All of them are committed together, or none is.
- **Who sends it:** only the Case Manager, which undoes only invitations it sent.
  No use case handles it on receipt.

{% include-markdown "./_occasions/sections/create-embargo-event.md" %}

- **Protocol role:** each embargo a case's creation writes, such as the default embargo, is its own ledger entry, right after the case's genesis entry, carrying the embargo in full ([CLP-07-013](../specs/protocol.md#clp-07-013)).
  A replica built from the ledger alone reads the embargo's start and end times from it.
- **Who commits it:** only the Case Manager, as a ledger entry.
  No use case handles it on receipt: each replica stores the embargo from the ledger entry.

{% include-markdown "./_occasions/sections/create-embargo-consent.md" %}

- **Protocol role:** each consent row the Case Manager brings into existence is its own ledger entry, after the act that caused it, carrying the row in full ([CLP-07-013](../specs/protocol.md#clp-07-013)).
  A proposal writes an `UNINVITED` row for each participant this way.
- **Who sends it:** only the Case Manager.
  No use case handles it on receipt: each replica writes the row from the ledger entry.

{% include-markdown "./_occasions/sections/update-embargo-consent.md" %}

- **Protocol role:** each consent row the Case Manager changes is its own ledger entry, carrying the changed row in full ([CLP-07-013](../specs/protocol.md#clp-07-013)).
  An invitation whose deadline passes unanswered moves to `TIMED_OUT` this way, and the rows carried over at activation are written the same way.
- **The Case Manager's own consent:** a Case Manager with a stake in the embargo records a change of its own consent as this `Update`, never as a `Reject` of the Invite (MSM-07-004).
- **Who sends it:** only the Case Manager.
  No use case handles it on receipt: each replica writes the row from the ledger entry.

{% include-markdown "./_occasions/sections/embargo-proposal-acceptance.md" %}

- **Triggering transition:** Proposed → Active (P → A), or Proposed → Revise (P → R) while another proposal stays open as a revision (EMB-18-005).
- **Who decides:** an `Accept` of the Invite is always the sender's own consent to those terms, the Case Owner's included.
  It moves the sender's consent to that embargo to `AGREED` and changes no embargo on the case (see [The Case Owner's Decision](#the-case-owners-decision), MSM-07-003).
- **The embargo in force:** an `Accept` or `Reject` may answer an Invite for the embargo already in force, such as a proposal that was activated before the sender answered it, an invitation whose deadline has passed, or a re-invitation after a lapse, while the sender's consent to it is `INVITED` or `TIMED_OUT` (EP-09-012).
  The answer names that Invite by id.

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
Its object is the proposed `EmbargoEvent` itself, not the Invite that proposed it, and its target is the case.
Only the Case Owner may send either activity, and it sends them to the Case Manager.
Any other sender is refused.
The Case Manager records the decision in the case ledger, and every participant learns it from there.

These two activities carry no shorthand of their own.
They are how the case takes the `EA`, `EC`, `ER`, and `EJ` transitions above, while the `Accept` and `Reject` of each Invite record each participant's consent.

{% include-markdown "./_occasions/sections/activate-embargo.md" heading-offset=1 %}

The activation supersedes the embargo in force, if there is one, in the same register step, and any other open proposal stays open as a revision.
The Case Owner's own consent to the activated terms is recorded with it, as `AGREED`.
A Case Owner that had declined those terms may still activate them: activating is the Case Owner changing its answer, so its consent moves straight to `AGREED` (MSM-07-008).
When the new terms end no later than the ones they replace, every participant that agreed to the old terms is carried over to the new ones; when they end later, a participant that has not agreed to them is no longer bound (MSM-07-005).
The Case Manager refuses an activation once the case is public, an exploit is public, or attacks are observed, and refuses one whose `EmbargoEvent` is not an open proposal of the case.

{% include-markdown "./_occasions/sections/reject-embargo-proposal.md" heading-offset=1 %}

If an embargo is active, it stays in force on its current terms (`EJ`); otherwise the case has no embargo (`ER`).
While another proposal is still open, the case stays in negotiation.
No participant's consent changes, the Case Owner's included.
If the case is public, an exploit is public, or attacks are observed when the Case Owner rejects the last open revision, the Case Manager also ends the embargo in the same act (`ET`).
The ledger then holds two entries: the `Reject`, which leaves the revision rejected, and the Case Manager's own `Remove`, which leaves the embargo terminated.
If the termination is refused, neither entry is committed.

{% include-markdown "./_occasions/sections/embargo-termination.md" %}

- **Triggering transition:** Active or Revise → eXited ({A,R} → X).
  The same register step cancels every open proposal, and no participant's consent is written (EP-08-004, MSM-07-006).
- **Reason:** `content` says what ended the embargo, exactly `END_TIME_REACHED` or `EARLY`.
  A receiver refuses a `Remove` whose `content` is anything else.
  `summary` is a human-readable account that the protocol does not read.
- **Why it ended:** `terminationCause` gives the cause, when the sender names one, and the Case Manager's embargo register records it beside the reason (EMB-13-004, EMB-13-005).
  Its `kind` is `THREAT_SIGNAL` (with the `signals` `P`, `X` or `A`), `FIX_READY` (with the `vendors` whose readiness made the quorum), `FIX_DEPLOYED`, or `OTHER` (whose account is the `summary`).
  Every cause goes with `EARLY`; a `Remove` that carries `END_TIME_REACHED` names no cause.
  A receiver refuses a `Remove` with an unknown `kind`, a missing or malformed detail, or a cause on `END_TIME_REACHED`.
  The Case Owner's `Remove` may name `FIX_READY`, `FIX_DEPLOYED` or `OTHER`, and the Case Manager records the cause as given.
  Only the Case Manager's own `Remove` may name `THREAT_SIGNAL`.
  A Case Owner reports public awareness, a public exploit or observed attacks as a case status update setting `P`, `X` or `A`; the Case Manager then ends the embargo with the signals the case carries.
  Each replica copies the cause from the ledger entry onto its own register, and never works a cause out from its own case state.
- **At the end time:** when the end time of the embargo in force has passed, the Case Manager ends it with `END_TIME_REACHED`.
  It does so the next time it handles the case, or when an outside service such as a [Sentinel](../glossary.md) asks it to.
  Whichever comes second finds the embargo already ended and sends nothing.
  A `Remove` that claims `END_TIME_REACHED` before the embargo's end time is refused.
- **Bound participants that are no longer active:** a signatory that was removed from the case, or that left it and is at RM `CLOSED`, stays bound by the embargo but no longer receives ledger entries.
  The CASE_MANAGER sends each such participant `ET` directly, one activity per participant, outside the ledger stream.
  The notice carries the embargo, the reason and the cause the Case Manager recorded, and nothing else.
  It is not a ledger entry.
  The participant applies it only when the CASE_MANAGER sent it.
  A termination on or after the embargo's agreed end date is expiry, and sends no notice.

{% include-markdown "./_occasions/sections/embargo-termination-notice.md" %}

- **Recipient:** one `Remove(EmbargoEvent)` per participant other than the CASE_MANAGER, never the CASE_MANAGER itself (EMB-19-001).

{% include-markdown "./_occasions/sections/embargo-withdrawal.md" %}

- **Triggering transition:** none; the case's EM state does not move.
  The sender's consent to the embargo in force moves from `AGREED` to `DECLINED` (MSM-07-010).
- **Who sends it:** a participant that agreed to the embargo in force, sent to the Case Manager.
  It answers no Invite, so a participant whose consent was recorded when the case was created, or when it joined, can send it too.
- **Open revisions:** every open revision the sender had agreed to is declined with it, because each one would replace the embargo it left.
- **Refused:** a `Leave` of an embargo that is not in force, from a sender whose consent to it is not `AGREED`, or from the Case Owner, which ends an embargo by terminating it (`ET`).
- **Not a Reject:** a `Reject` of the Invite for the embargo in force, sent by a participant that agreed to it, is refused; withdrawal is this activity (MSM-07-004).

## When the Case Manager Refuses a Message

When the Case Manager refuses an embargo message because the case cannot take it, nothing is committed.
The Case Manager tells the sender why with the [refusal notice](faults_and_acknowledgements.md#refusal-notice) (CLP-02-005, CLP-05-001).
The notice is a `Reject` whose `object` is the refused activity, inline, whose `inReplyTo` names that activity's id, and whose `summary` gives the reason.
It goes to the sender alone, and the sender closes its pending request when the notice arrives.

| Message | Refused, with the notice, when |
|---|---|
| `Invite(EmbargoEvent)` (`EP`, `EV`) | the embargo has ended (EM `EXITED`), which admits no proposal. The notice is a `Reject` of the Invite, the same shape as a decline, and the proposer reads it as one (EP-09-008). |
| `Accept(Invite(EmbargoEvent))` (`EA`, `EC`) | the `EmbargoEvent` is neither the embargo in force nor an open proposal: the register does not hold it, or the proposal was already decided, replaced or ended (CM-18-003). |
| `Reject(Invite(EmbargoEvent))` (`ER`, `EJ`) | the `EmbargoEvent` is neither the embargo in force nor an open proposal, or the sender agreed to the embargo in force, since withdrawal is `Leave(EmbargoEvent)` (MSM-07-004). |
| `Accept(EmbargoEvent)[target=VulnerabilityCase]` | the `EmbargoEvent` is not an open proposal of the case, or the case is public, an exploit is public, or attacks are observed (MSM-07-008, EMB-02-002). |
| `Reject(EmbargoEvent)[target=VulnerabilityCase]` | the `EmbargoEvent` is not an open proposal of the case, or the termination the rejection would cause is refused (MSM-07-009). |
| `Remove(EmbargoEvent)` (`ET`) | it claims `END_TIME_REACHED` before the embargo's end time, or a Case Owner's `Remove` names a `THREAT_SIGNAL` cause (EMB-13-005). |
| `Leave(EmbargoEvent)` | no embargo is in force, the `EmbargoEvent` is not the embargo in force, the sender's consent to it is not `AGREED`, or the sender is the Case Owner (MSM-07-010). |

Some deliveries get no notice:

- A message the sender has no standing to send is refused with no answer (HP-01-006).
- A repeat of an answer already recorded, under a new id or the same one, is skipped and gets no notice (CM-13-005).
- An `Invite` or `Accept` that arrives once the case is public, an exploit is public, or attacks are observed is answered with `ER` instead (EMB-01-002, EMB-02-002).
  The Case Manager's `ER` to an `Accept` reaches the participant, which closes its pending `Accept`.
- A late `Accept` of the embargo in force is recorded as an on-time `Accept` is, and a late `Accept` of replaced terms is answered with a relayed invitation to the current ones (EMB-17).
  A late `Accept` of an embargo the case no longer has changes nothing, so the Case Manager records and sends nothing for it (EMB-17-004).
- A failure inside the Case Manager is not a refusal, and is never answered with a notice.

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
  `Create(ProcessingFault)`, `as:Reject`, or `Add(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#em-message-types).
