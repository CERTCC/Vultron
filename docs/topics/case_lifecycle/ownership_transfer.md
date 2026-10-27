---
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: explanation
subject: protocol
introduces: [Case Ownership Transfer]
description: >
  How the CASE_OWNER role moves between participants via the CASE_MANAGER.
---

# Case Ownership Transfer

{% include-markdown "../../includes/specification_governs.md" %}

A case has at most one owner at a time: the participant holding the `CASE_OWNER` role, who makes decisions for the case ([CM-21-001](../../reference/specs/protocol.md#cm-21-001)).
Ownership can move from one participant to another — for example, when a vendor hands a case to a coordinator.
This page explains how that transfer works and why every step of it goes through the [CASE_MANAGER](case_manager_and_ledger.md).

---

## Why the transfer goes through the CASE_MANAGER

A change of owner matters to everyone in the case, not only to the two participants involved.
Every participant needs to know who decides for the case now.
A participant learns about a change to the case only through an entry in the case ledger.
Only the CASE_MANAGER writes those entries ([The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md)).

So the owner's proposal, the answer, and a withdrawal are all sent to the CASE_MANAGER, not to the other party directly ([CM-21-005](../../reference/specs/protocol.md#cm-21-005), [CM-21-006](../../reference/specs/protocol.md#cm-21-006), [CM-21-010](../../reference/specs/protocol.md#cm-21-010), [CM-21-015](../../reference/specs/protocol.md#cm-21-015), [ADR-0053](../../adr/0053-ownership-transfer-routed-via-caseactor.md)).
If they went directly between the two parties, no ledger entry would be written, and the other participants would never learn that ownership had changed.

---

## The proposal and the offer

```text
Owner sends trigger: offer-case-ownership-transfer
  → Owner sends Offer(Offer(VulnerabilityCase))    ← the proposal
      inner target: transferee
      context:      case_id
      actor:        owner_id          (the owner's own activity)
      to:           [case_actor_id]   ← MUST route through Case Actor (CM-21-005)

Case Actor inbox receives the proposal:
  0. Checks the sender holds CASE_OWNER
     (anyone else: refused, nothing written).        ← CM-21-019
  1. Checks no offer for the case is open,           ← CM-21-014
     and the inner Offer names this case and a
     transferee it can address                       ← CM-21-005
     that is an active participant.                  ← CM-21-021
  2. Commits CaseLedgerEntry (the proposal).
  3. Makes the offer and queues it to the transferee:
       Offer(VulnerabilityCase)
       target:        transferee
       id:            derived from the proposal
       actor:         case_actor_id   (delegated-message contract)
       attributed_to: owner_id
  4. Commits CaseLedgerEntry (the offer).
  5. Announce(CaseLedgerEntry) → all participants.   ← all parties learn the offer
```

The owner asks for the transfer by sending a proposal to the CASE_MANAGER — in the prototype, the Case Actor ([ADR-0148](../../adr/0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md)).
The proposal is an `Offer` whose object is the `Offer` the owner wants made.
The inner offer names the case, the proposed new owner as its `target`, and an optional deadline.
The proposal leaves from the owner's own outbox, under the owner's own identity.
No container sends a message as an actor it does not host ([CM-24-004](../../reference/specs/architecture.md#cm-24-004), [ADR-0109](../../adr/0109-a-container-emits-only-as-actors-it-hosts.md)).

The CASE_MANAGER admits a proposal only from the current Case Owner.
It refuses a proposal from anyone else before it writes or sends anything ([CM-21-019](../../reference/specs/protocol.md#cm-21-019)).

The CASE_MANAGER checks the inner offer and does not copy it.
The inner offer must name the proposal's case.
Its `target` must be an actor the CASE_MANAGER can address, and must be neither the CASE_MANAGER nor the owner.
The `target` must also be an [active participant](../../reference/glossary.md#cvd-roles-and-participants) of the case ([CM-21-021](../../reference/specs/protocol.md#cm-21-021)).
An active participant has joined the case, has not been removed, and has agreed to the active embargo while one is in force ([CM-10-004](../../reference/specs/protocol.md#cm-10-004)).
A participant whose closure is recorded is refused too, because it receives no further case content ([CM-23-004](../../reference/specs/protocol.md#cm-23-004)).
The offer carries the case in full, with its embargo and participant records, so the CASE_MANAGER offers it only to an actor that may already see that content.
So an owner that wants to hand the case to an actor that is not an active participant invites that actor first, and proposes the transfer once the actor has joined.
The owner's `offer-case-ownership-transfer` trigger makes the same check on the owner's own copy of the case, and refuses such a transferee before it sends anything.
The CASE_MANAGER ignores any `id`, `actor` or `to` the owner put inside the inner offer.

The CASE_MANAGER then makes the offer itself.
The offer is a new `Offer` of the case under an `id` the CASE_MANAGER derives from the proposal.
So a repeat of the proposal makes the same offer and never a second one.
The CASE_MANAGER sends it under its own identity, with the owner who asked for it named as the author (`attributed_to`).
Every message the CASE_MANAGER sends on a participant's behalf follows this delegated-message contract ([CM-24-001](../../reference/specs/protocol.md#cm-24-001), [CM-24-002](../../reference/specs/protocol.md#cm-24-002), [CM-24-004](../../reference/specs/architecture.md#cm-24-004), [CM-24-005](../../reference/specs/project.md#cm-24-005)).

The CASE_MANAGER records the proposal and then the offer in the ledger, so every participant learns that a transfer is on offer.
That offer is the one offer of the transfer: the one the proposed new owner answers, and the one the ledger closes.
The offer carries the proposed new owner (`target`) as a full actor object, not as an `id` alone.
The CASE_MANAGER holds that actor's participant record but need not hold its actor record, so the offer carries the actor in full, and the ledger entry records the offer as sent ([CLP-07-006](../../reference/specs/protocol.md#clp-07-006)).
The proposed new owner takes the offer only from the CASE_MANAGER.

## The answer

```text
Accepting actor sends trigger: accept-case-ownership-transfer
  → Accept(Offer(VulnerabilityCase))
      to: [case_actor_id]     ← MUST route through Case Actor (CM-21-006)

Case Actor inbox receives Accept:
  0. Checks the sender is the proposed owner of an open
     offer it recorded (anyone else: refused),          ← CM-21-011
     and is still an active participant.                ← CM-21-021
  1. Commits CaseLedgerEntry (ownership-transferred).   ← CM-21-007
  2. Announce(CaseLedgerEntry) → all participants.
  3. Applies the CASE_OWNER role change (CM-21-001 through CM-21-004).
  4. Commits one entry per changed object, each        ← CLP-07-013
     Announce(CaseLedgerEntry) → all participants:
       update_case_participant  (previous owner, CASE_OWNER removed)
       update_case_participant  (new owner, CASE_OWNER added)
       update_case_owner        (the case, attributed_to = new owner)
```

The proposed owner answers the CASE_MANAGER, not the participant who made the offer.
The CASE_MANAGER acts on an acceptance only when its sender is the proposed owner named in an offer it recorded for the case ([CM-21-011](../../reference/specs/protocol.md#cm-21-011)).
That offer must also still be open, with no other answer to it recorded.
The proposed owner must also still be an active participant when its acceptance arrives ([CM-21-021](../../reference/specs/protocol.md#cm-21-021)).
A proposed owner that was removed or left the case after the offer, or has not agreed to an embargo that became active since, is refused, and ownership stays where it was.

The answer names the CASE_MANAGER's offer by its `id`, the same `id` the ledger records.
So the CASE_MANAGER needs no other link to find the offer.
It refuses an `Accept` from anyone else, or a second `Accept` of the same offer, and ownership stays where it was.

The new owner is the actor the recorded offer names, not whoever sent the acceptance.
A participant's own copy of the case takes the ownership change only from the CASE_MANAGER.
On an acceptance, the CASE_MANAGER moves the `CASE_OWNER` role in a single step.
The previous owner loses the role and the new owner gains it together, so the CASE_MANAGER's case never has two owners or none ([CM-21-001](../../reference/specs/protocol.md#cm-21-001), [CM-21-002](../../reference/specs/protocol.md#cm-21-002), [CM-21-003](../../reference/specs/protocol.md#cm-21-003), [CM-21-004](../../reference/specs/project.md#cm-21-004)).

The previous owner keeps any other roles it held and stays a participant in the case ([CM-21-008](../../reference/specs/protocol.md#cm-21-008), [CM-21-009](../../reference/specs/protocol.md#cm-21-009)).
The CASE_MANAGER records the acceptance in the ledger and sends the entry to every participant ([CM-21-007](../../reference/specs/protocol.md#cm-21-007)).

The acceptance entry records what the proposed owner sent, not the changes it causes.
Each change the CASE_MANAGER makes because of it follows as an entry of its own, in the order the CASE_MANAGER writes them ([CLP-07-013](../../reference/specs/protocol.md#clp-07-013)):

1. An `update_case_participant` entry carries the previous owner's participant record, without `CASE_OWNER`.
2. An `update_case_participant` entry carries the new owner's participant record, with `CASE_OWNER`.
3. An `update_case_owner` entry carries the case, whose `attributed_to` now names the new owner.

Each entry is an `Update` that the CASE_MANAGER authors, and it carries the changed object in full.
A participant's copy of the case changes only by copying what these entries carry.
It stores each participant record as received and takes `attributed_to` from the carried case ([CM-23-016](../../reference/specs/protocol.md#cm-23-016)).
It does not decide for itself who the new owner is, and it assigns no ids or times of its own.
So every copy holds the same owner and the same roles as the CASE_MANAGER.

The previous owner's record changes first, so no copy ever shows two owners.
A copy applies the entries one at a time.
So between the first two entries it briefly shows no participant with `CASE_OWNER`.
Until the third entry, its `attributed_to` still names the previous owner.

The CASE_MANAGER records all three entries before it saves the change, so it never makes a change that has no entry.
The same entries update the new owner's own copy, and nothing goes to it separately.

```text
Declining actor sends trigger: reject-case-ownership-transfer
  → Reject(Offer(VulnerabilityCase))
      to: [case_actor_id]     ← MUST route through Case Actor (CM-21-010)

Case Actor inbox receives Reject:
  0. Checks the sender is the proposed owner of an open
     offer it recorded (anyone else: refused).          ← CM-21-013
  1. Commits CaseLedgerEntry (transfer-declined).       ← CM-21-012
  2. Announce(CaseLedgerEntry) → all participants.
```

The proposed owner declines an offer by sending a `Reject` with the `reject-case-ownership-transfer` trigger ([TRIG-11-005](../../reference/specs/project.md#trig-11-005)), and the `Reject` is also sent to the CASE_MANAGER ([CM-21-010](../../reference/specs/protocol.md#cm-21-010)).
The protocol treats a `Reject` like an `Accept`: the CASE_MANAGER records it in the ledger and sends the entry to every participant.
That entry is how the participant who made the offer learns of the `Reject` ([CM-21-012](../../reference/specs/protocol.md#cm-21-012)).

Only the proposed owner named in an open offer may decline it ([CM-21-013](../../reference/specs/protocol.md#cm-21-013)).
The CASE_MANAGER does not act on a `Reject` from anyone else: it records nothing, and the offer stays open.
Ownership stays where it was: the ledger entry closes the offer, and no participant's copy of the case changes in any other way.

## Offering again, withdrawing, and the deadline

A case has at most one open offer at a time ([CM-21-014](../../reference/specs/protocol.md#cm-21-014)).
An offer stays open until the ledger records that it was accepted, declined, or withdrawn, or until its deadline passes.
While it is open, the CASE_MANAGER refuses a new proposal for the case, and neither records it nor makes an offer from it.
It answers the refused proposal with a `Reject` of it, the [refusal notice](../../reference/messages/faults_and_acknowledgements.md#refusal-notice).
The owner reads that notice as the decline of its proposal ([CLP-05-001](../../reference/specs/protocol.md#clp-05-001)).

Once the offer is closed, the owner may propose the case again to anyone, including a participant that declined, with nothing to clear first.
A closed offer cannot be answered again: an `Accept` after a `Reject`, or a `Reject` after an `Accept`, is refused.

```text
Owner sends trigger: withdraw-case-ownership-transfer
  → Undo(proposal), that is Undo(Offer(Offer(VulnerabilityCase)))
      to: [case_actor_id]     ← MUST route through Case Actor (CM-21-015)

Case Actor inbox receives Undo:
  0. Finds the offer it made from the proposal, and
     checks the sender is the Case Owner it was made
     for, and the offer is open (anyone else: refused). ← CM-21-015
  1. Commits CaseLedgerEntry (offer withdrawn).         ← CM-21-015
  2. Announce(CaseLedgerEntry) → all participants.
```

The owner may withdraw the offer while it is open, with the `withdraw-case-ownership-transfer` trigger.
The trigger sends an `Undo` of the owner's own proposal to the CASE_MANAGER ([CM-21-015](../../reference/specs/protocol.md#cm-21-015), [TRIG-11-006](../../reference/specs/project.md#trig-11-006)).
The owner names the proposal, the one activity of the transfer it holds, and the CASE_MANAGER withdraws the offer it made from that proposal.
The CASE_MANAGER acts on a withdrawal only when its sender is the Case Owner that offer was made for, and the offer is still open.

The CASE_MANAGER records the withdrawal in the ledger and sends the entry to every participant.
So the proposed owner learns that it can no longer accept, and the offer is closed.
It refuses a withdrawal from anyone else, or of an offer already accepted, declined, withdrawn, or expired, and records nothing.
It answers a withdrawal of a closed offer with the refusal notice, and a withdrawal from anyone else with nothing.
Ownership stays where it was, and the owner may propose the case again at once.

```text
Owner sends trigger: offer-case-ownership-transfer
  with end_time (optional)                              ← TRIG-11-007
  → Offer(Offer(VulnerabilityCase)), inner endTime: deadline
  → the Case Actor's Offer(VulnerabilityCase), endTime: deadline

Case Actor inbox receives an Accept, Reject or Undo of the offer,
or a new proposal for the case:
  0. Is the offer past its endTime?                     ← CM-21-017
     yes: the offer is closed; nothing is recorded
          or sent for the expiry.
  1. Handles the activity: an answer to or withdrawal
     of the expired offer is refused, and a new
     proposal is admitted.                              ← CM-21-016
```

An offer may also carry an `end_time`, the deadline to answer it ([CM-21-016](../../reference/specs/protocol.md#cm-21-016)).
The owner sets it with the `end_time` field of the `offer-case-ownership-transfer` trigger.
That field must be a future time with a timezone ([TRIG-11-007](../../reference/specs/project.md#trig-11-007)).
Without it, the offer stays open until it is answered or withdrawn.

The trigger puts the deadline on the proposal's inner offer, and the offer the CASE_MANAGER makes carries it.
So the proposed owner knows when it can no longer answer.
The CASE_MANAGER reads the deadline in Coordinated Universal Time (UTC), whatever offset the offer was sent with.

The deadline is binding: the CASE_MANAGER refuses an `Accept` or `Reject` it processes after the deadline, so every participant knows who decides for the case once it passes.
A refused late answer moves no role and is not recorded in the ledger.
This is stricter than the deadline on an embargo invitation, which is a strong suggestion.

The CASE_MANAGER checks the deadline only when it handles an `Accept`, `Reject` or withdrawal of the offer, or a new proposal for the case.
Nothing runs on a timer ([CM-21-017](../../reference/specs/protocol.md#cm-21-017)).
An offer past its deadline is closed like an accepted, declined or withdrawn one.
So the CASE_MANAGER refuses a late answer and a withdrawal of the expired offer, and admits a new proposal for the case.

The CASE_MANAGER records nothing and sends nothing for the expiry ([ADR-0152](../../adr/0152-a-case-managers-act-shares-the-participants-semantic-type-and-an-observation-is-not-ledgered.md)).
Any participant that holds the case can read the deadline from the offer in the ledger.
No participant's copy of the case changes when the deadline passes, so an entry would add nothing.
Only the CASE_MANAGER judges a late answer, so only it compares the deadline with its clock.

Without withdrawal and the deadline, a proposed owner that never answered would block every later transfer of the case.

---

## The same pattern as an invitation

Ownership transfer follows the same pattern as inviting an actor to join a case ([ADR-0026](../../adr/0026-caseactor-routed-actor-suggestion.md)):

| Invite/Accept | Ownership Transfer |
|---|---|
| `Invite` sent **by** the CASE_MANAGER | Proposal addressed **to** the CASE_MANAGER; `Offer` sent **by** the CASE_MANAGER |
| `Accept(Invite)` addressed **to** the CASE_MANAGER | `Accept(Offer)` addressed **to** the CASE_MANAGER |
| The CASE_MANAGER creates the `CaseParticipant` | The CASE_MANAGER moves the `CASE_OWNER` role |
| `CaseLedgerEntry` → every participant | `CaseLedgerEntry` → every participant |

In both, the CASE_MANAGER sits in the middle because it is the only participant that writes to the ledger, and its entries reach everyone.

---

## See also

- [How to Decide Who Owns a Case](../../howto/decide_who_owns_a_case.md) — when to submit a report, create a case yourself, or transfer one
- [Case Management Messages](../../reference/messages/case_management.md#propose-case-ownership-transfer) — the proposal, `Offer`, `Accept`, `Reject`, and `Undo` activities on the wire
- [Other Demos: transfer-ownership](../../tutorials/other_demos.md#transfer-ownership) — run a transfer end to end
- [The Case Model](case_model.md) — `VulnerabilityCase`, participants, and the `CASE_OWNER` role
- [The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md) — how a ledger entry reaches every participant
- [Case Ownership in a federation](../future_work/federation.md#case-ownership) — future work on ownership when each organization runs its own service
- [Open questions: cases and participants](../future_work/open_questions.md#cases-and-participants) — including where the CASE_MANAGER lives after ownership moves
- [ADR-0053](../../adr/0053-ownership-transfer-routed-via-caseactor.md) — decision record for CASE_MANAGER-routed ownership transfer
- [ADR-0148](../../adr/0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md) — decision record for the owner's proposal and the CASE_MANAGER's offer
- [ADR-0026](../../adr/0026-caseactor-routed-actor-suggestion.md) — CaseActor-routed actor suggestion and invitation flow
