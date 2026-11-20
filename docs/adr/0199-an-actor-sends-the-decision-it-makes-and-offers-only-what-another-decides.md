---
status: accepted-provisional
status_override: >-
  Revisions 2 and 3 edited in place with the decider's approval (Allen D.
  Householder, issue #6487 planning interview, 2026-11-17, and issue #6626
  planning interview, 2026-11-19); neither the announced ownership Offer of
  revision 2 nor any of revision 1 was built, and the implementation issues
  rewrite the dependent requirements. One sentence edited in place on
  2026-11-20 with the decider's approval (#6465 build, epic run #6509): an
  Owner that is also the CASE_MANAGER sends its removal or reinstatement to
  its own inbox, which admits it through the same received tree.
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-20
revision: 3
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0053, ADR-0109, ADR-0113, ADR-0114, ADR-0116, ADR-0122,
  ADR-0146, ADR-0148, ADR-0180, ADR-0196, ADR-0202, ADR-0203, ADR-0205;
  specs/case-management.yaml CM-16, CM-17, CM-21, CM-24, CM-31;
  specs/embargo-policy.yaml EP-09; specs/participant-case-replica.yaml PCR-08;
  specs/message-semantics-mapping.yaml MSM-07; specs/vultron-as2-mapping.yaml VAM-05;
  notes/activitystreams-semantics.md, notes/as2-vocabulary-alignment.md;
  issues #6245, #6293, #6487, #6626
informed: []
partially_supersedes:
  - 0116-removing-a-participant-withdraws-entitlement-not-membership.md
  - 0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md
  - 0180-the-case-owner-adds-an-embargo-to-the-case-and-answers-a-proposal-by-pointing-at-it.md
stakeholder_type: [project-contributor]
---

# An Actor Sends the Decision It Makes, and Offers Only What Another Actor Decides

## Context and Problem Statement

A Vultron activity states something its sender has done; it is not a command.
The CASE_MANAGER holds the case file and writes every change to it, while other actors decide many of those changes.
A participant decides its own embargo consent.
The Case Owner decides who leaves the case, who is let back in, whether a proposed embargo is put in force or rejected, when an embargo ends early, and who is offered ownership of the case.

The protocol has answered "who sends the act?" in two ways.

- **The decider declares, and the CASE_MANAGER records.**
  A participant's `Accept(Invite(EmbargoEvent))` is its own act, and the ledger entry that carries it is the CASE_MANAGER's admission of it (ADR-0122).
  The Owner's removal, `Remove(CaseParticipant)` (ADR-0116), its activation, `Add(EmbargoEvent, target=VulnerabilityCase)` (ADR-0180), and its early end, `Remove(EmbargoEvent)`, are ledgered the same way.
- **The decider asks, and the CASE_MANAGER acts.**
  The ownership transfer is `Offer(Offer(VulnerabilityCase))`, and the CASE_MANAGER makes the transfer Offer itself (ADR-0148).
  Revision 1 of this record extended that form to removal and reinstatement, on the ground that the actor that writes the record is the actor that acts.

The two answers disagree about every Owner decision.
Revision 1's ground, "the writer acts", is applied nowhere else: the CASE_MANAGER writes every consent row too, yet a participant's consent is the participant's own act.
Applied consistently, it would make every participant's consent an Offer as well.
The disagreement showed when the Owner's activation was left as a bare act while its early end became an Offer (issue #6487).

Which actor sends a decision on the case as the act itself, and when is the act offered to another actor instead?
And when a decision asks another actor for an answer, which message does that actor receive and answer?

## Decision Drivers

- An activity states what its sender did. A decision is something its maker does, even when another actor writes the record of it.
- One rule decides the form of every message, so a peer that implements from the rules sends each one correctly.
- The ledger is the CASE_MANAGER's record of admitted assertions: it judges each one *admitted* or *refused*, and commits the admitted ones as entries (CLP-02-012). Its entry wraps the act and adds its own commit time; the act keeps its author and its claimed `published` time.
- A case message reaches a participant from the CASE_MANAGER it trusts (CBT-01-006, PCR-03-004).
- One fact has one activity, so a peer does not count two removals where one happened.
- An answer names what it answers (VOC `inReplyTo`).
- An `Offer` or an `Invite` expects an answer; an `Announce` informs and expects none.
  The ledger's fan-out already follows this: it carries case state and never asks (ADR-0113).
- Distinct actors communicate only through the protocol, wherever they run (ADR-0109).
- The decider's act is the record of its decision wherever that record is kept, whether by a CASE_MANAGER service or by a ledger the participants share.

## Considered Options

- **The writer acts.** Every decision another actor makes on the case is an `Offer` of the act; the CASE_MANAGER accepts it and makes the act itself (revision 1).
- **The decider acts.** An actor sends the decision it has the authority to make as the act itself; the CASE_MANAGER admits or refuses it. An `Offer` is sent only when another actor decides.
- **Each message decided case by case**, as the protocol does today.

When the decision asks another actor for an answer, as an invitation or an ownership Offer does, the answering actor can receive it in three ways:

- **The CASE_MANAGER announces the decider's act**, and the answering actor answers the announced act by its id (revision 2).
- **The CASE_MANAGER makes the ask**: the decider sends its own act to the CASE_MANAGER, and the CASE_MANAGER sends its own `Offer` or `Invite`, carrying the decider's act, which the answering actor answers.
- **The decider requests the ask**: the decider sends an `Offer` of the act it wants made, and the CASE_MANAGER makes the only act.

## Decision Outcome

Chosen option: "The decider acts", because it is the one rule that every existing message already fits or can fit, it matches what the ledger is (a record of admitted assertions), and every message states what its sender did.

For a decision that asks another actor for an answer, the chosen option is "the CASE_MANAGER makes the ask" (revision 3), because an `Announce` then always only informs, and the decider's own act is still the decision the ledger records.

### The decider sends the act

An actor that has the authority to make a decision sends the decision as the act itself.
The CASE_MANAGER checks the act against its rules.
It refuses an act that breaks them with a refusal notice (ADR-0196) and records nothing.
It admits any other act, and the act is the ledger entry's payload.
The CASE_MANAGER does not re-make an act it admits, and it sends no `Accept` of it: the entry, delivered by ledger fan-out, is how the sender learns that its act was admitted.

The case file changes when the CASE_MANAGER commits the admitted act.
That write is the CASE_MANAGER's bookkeeping, as its write of a consent row is when it admits a participant's consent.

### An Offer asks another actor to decide

An actor sends an `Offer` of an act only when another actor makes the decision.
The deciding actor answers with an `Accept` or a `Reject`, which is its own decision and follows this same rule.
A participant that proposes an item or a reference for the case offers it, because another actor decides whether the case takes it.
The CASE_MANAGER that asks the Owner to approve a status offers it, because the Owner decides.
A Case Owner that offers ownership of the case sends `Offer(VulnerabilityCase)`, because the transferee decides whether to take it.

### The Case Owner's decisions

The Case Owner decides these, and sends each as the act, to the CASE_MANAGER:

- **Removal and reinstatement.** `Remove(<Actor>, origin=<case>)` and `Add(<Actor>, target=<case>)`.
  The act names the actor the Owner decided about, as a typed reference, not the participant record.
  Each actor has one participant record per case, so the actor identifies the record, and a reinstatement reuses it, which keeps the participant's history and consent (ADR-0116).
  An Owner that also holds the CASE_MANAGER role sends the act to itself: ordinary outbox delivery brings it to its own inbox, and the same received tree admits or refuses it under the same rules.
- **Putting a proposed embargo in force.** `Update(EmbargoEvent)` setting its `status` to active, for a first proposal or a revision, with `inReplyTo` naming the `Invite(EmbargoEvent)` that proposed it.
  The proposal already put the embargo on the case's register, so its activation is a change of its status (ADR-0202).
- **Rejecting a proposed embargo.** `Update(EmbargoEvent)` setting its `status` to rejected, with `inReplyTo` naming the proposal's `Invite(EmbargoEvent)`.
  Every change of an embargo's status is then an `Update` of the embargo, and a `Reject` from the Owner only ever means its own consent, `Reject(Invite(EmbargoEvent))`.
- **Ending an embargo early.** `Update(EmbargoEvent)` setting its `status` to terminated, with its termination (ADR-0203).
- **Offering ownership.** `Offer(VulnerabilityCase)` with the transferee as its `target`.
  The transferee answers the CASE_MANAGER's Offer made from it.
- **Inviting an actor to the case.** `Invite(<case>)` with the invitee as its `target`, the case's preview as the stub (ADR-0205), and the invitee's roles.
  The invitee answers the CASE_MANAGER's Invite made from it.
  When the Owner accepts a participant's suggestion of an actor, its `Accept` of the suggestion is its decision, and the CASE_MANAGER's Invite is made from that `Accept`.

Both acts name the thing offered in `object` and the actor it is offered to in `target`, as VOC `Offer` and `Invite` do.

ADR-0180's consent effects of an activation stand.
The activation records the Owner's own agreement when the Owner has given no answer, and the CASE_MANAGER refuses an activation from an Owner that declined the proposal until the Owner accepts it.
A rejection changes no one's consent.

An `Update` of an embargo changes its status, and its termination when it ends.
An embargo's terms change only through a revision proposal.

### An Announce informs and asks nothing

An admitted act reaches the participants by ledger fan-out.
An actor that the act concerns and the fan-out does not reach receives `Announce(<the admitted act>)` from the CASE_MANAGER.
A removed participant and a reinstated participant receive one, and an end of an embargo is announced the same way (ADR-0203).
The `Announce`'s `actor` is the CASE_MANAGER, so the receiver's trust check reads the CASE_MANAGER, and the announced act keeps its own author and id.
No actor answers an `Announce`, or the act it carries.

### The CASE_MANAGER makes the ask a decision needs

When an admitted act asks another actor for an answer, the CASE_MANAGER sends that actor its own `Offer` or `Invite`, with the same `object` and `target` as the decider's act.
It sets `attributedTo` to the decider and `inReplyTo` to the decider's act.
The answering actor answers the CASE_MANAGER's act, to the CASE_MANAGER.
The CASE_MANAGER commits the decider's act it admitted as one ledger entry, and its own ask as another once the ask is in its outbox.
The ownership Offer to the transferee, the stub Invite to an invitee, and each embargo Invite to a participant other than the proposer (ADR-0113) are made this way.

The CASE_MANAGER thus carries the participants' acts, not acts of its own invention: it admits each decision, and it asks each actor whose answer the decision needs.
The decider's act is the decision, wherever its record is kept; the CASE_MANAGER's ask is how the answering actor is reached.

### The CASE_MANAGER's own acts

The CASE_MANAGER sends its own decisions as its own acts: ending an embargo at its end time or on a threat signal, abandoning a proposal, the revision it registers at case creation, the full-case Invite to a joiner, and the bookkeeping acts it makes as it commits an admitted act.
When it carries out an act another actor asked it for, it sets `attributedTo` to the asker and `inReplyTo` to the request it received.
It sets both exactly when the asker is an actor other than the `actor`.
An Owner that also holds the CASE_MANAGER role sends its ask straight to the answering actor, with neither field.

### Consequences

- Good, because one test, "who decides?", gives the form of every message, and participant consent and the Owner's decisions follow the same rule.
- Good, because every message states what its sender did: the Owner's act is its decision, and the CASE_MANAGER's entry is its admission of it.
- Good, because an ownership transfer has one decision, the Owner's Offer, which the ledger records; the CASE_MANAGER's Offer made from it is the one the transferee answers.
- Good, because an `Announce` never asks, so a receiver never has to tell an announcement it must answer from one that only informs.
- Good, because the case invitation and the embargo-proposal relay already have the CASE_MANAGER make the ask, so one shape covers every act that needs an answer.
- Good, because every change of an embargo's status is an `Update` of the embargo.
- Bad, because activation, rejection and an early end share the shape `Update(EmbargoEvent)`, so the message patterns that tell them apart read the `status` the `Update` sets.
- Bad, because the activation, rejection, ownership-transfer and direct-invitation messages change form, and with them their patterns, examples, received trees and message reference pages. Pre-1.0, the old forms are replaced outright.
- Bad, because a decision that needs an answer puts two acts on the wire, the decider's and the CASE_MANAGER's ask, and two ledger entries; `inReplyTo` links them, and only the decider's is the decision.

## Validation

- A test sends the Owner's `Remove(<Actor>, origin=<case>)` and asserts that the ledger holds one entry carrying the Owner's act, and that the removed actor receives an `Announce` of that act.
- A test sends the Owner's `Add(<Actor>, target=<case>)` reinstating a removed participant and asserts that the ledger holds one entry carrying the Owner's act, and that the reinstated actor receives an `Announce` of that act and applies the change only from the entry.
- A test sends the Owner's `Update(EmbargoEvent)` setting `status` active, and asserts that the ledger entry carries the Owner's act and that the embargo is in force.
  Another asserts that the same act from an Owner that declined the proposal is refused with nothing committed.
- A test sends the Owner's `Update(EmbargoEvent)` setting `status` rejected, and asserts that the embargo is rejected and no consent row changes.
- A test asserts that an `Update(EmbargoEvent)` that changes the embargo's terms is refused.
- A test sends the Owner's `Offer(VulnerabilityCase)` and asserts that the ledger records it, and that the transferee receives the CASE_MANAGER's own Offer with `attributedTo` naming the Owner and `inReplyTo` naming the Owner's Offer.
  Another asserts that the transferee's `Accept` names the CASE_MANAGER's Offer.
- A test sends the Owner's `Invite(<case>)` naming an invitee and asserts that the ledger records it, and that the invitee receives the CASE_MANAGER's own stub Invite with `attributedTo` naming the Owner and `inReplyTo` naming the Owner's Invite.
- A test asserts that no answer to an `Announce`, or to the act it carries, is admitted.
- A test asserts that every act the CASE_MANAGER makes on another actor's request carries `inReplyTo` naming that request.

## Pros and Cons of the Options

### The writer acts

- Good, because the actor that writes the case file sends every act that changes it.
- Bad, because it is applied nowhere else: participant consent, which the CASE_MANAGER writes too, is the participant's own act.
- Bad, because every decision becomes three messages: the Offer, the Accept and the act.

### The decider acts

- Good, because every message states what its sender did, and one rule covers consent and the Owner's decisions.
- Good, because it matches the ledger's own model, admission of assertions.
- Bad, because the CASE_MANAGER informs a removed or reinstated actor by `Announce`, a wrapper the receiver opens.

### The CASE_MANAGER announces the decider's act

- Good, because each decision is one act on the wire.
- Bad, because the receiver must answer an act carried inside an `Announce`, so an `Announce` sometimes asks and sometimes only informs.
- Bad, because "the CASE_MANAGER says the Owner invited you" reads as a report of an invitation, not as the invitation; the receiver would wait for the invitation itself.
- Bad, because a per-invitee deadline, an Invite to an actor who joins later, and a resend of an unanswered ask have no act of their own to carry them.

### The CASE_MANAGER makes the ask (chosen)

- Good, because an `Offer` or `Invite` always expects an answer and an `Announce` never does.
- Good, because it is the shape the embargo-proposal relay and the case invitation already have, so it adds none.
- Good, because it keeps the decider's own act as the decision, which a ledger the participants share could record as well as a CASE_MANAGER service.
- Bad, because a decision that needs an answer is two acts and two ledger entries.

### The decider requests the ask

- Good, because each decision is one act on the wire.
- Bad, because it brings back the `Offer` of an act that "the writer acts" used, so the decider's message is a request, not its decision.

### Each message decided case by case

- Good, because nothing changes.
- Bad, because a peer that implements from the rules cannot predict a message's form.

## More Information

Revision 1 chose "the writer acts" and made the Owner's removal, reinstatement and early end Offers of the act.
Revision 2 chooses "the decider acts" (issue #6487), before any of revision 1 was built.
Revision 3 (issue #6626) keeps that choice and changes how an act that needs an answer reaches the answering actor.
Revision 2 had the CASE_MANAGER announce the Owner's ownership Offer to the transferee, who answered the announced Offer.
Revision 3 has the CASE_MANAGER make its own Offer from the Owner's, so that an `Announce` only ever informs, and extends the same shape to the case invitation, whose direct path had the Owner send a recommend-actor `Offer(Actor)` for a decision the Owner makes.
The announced Offer of revision 2 was not built.

This record partially supersedes ADR-0116 in its choice of the removal and reinstatement messages.
These ADR-0116 statements no longer hold: the message names the participant record with the case as its `target`; the CASE_MANAGER sends the removed party a separate, unledgered notice.
ADR-0116's decision that removal is a stored fact that withdraws entitlement, not membership, stands, and so does its rule that the Owner's admitted act is the ledger entry.

It partially supersedes ADR-0148 in the Owner's transfer message: the Owner's `Offer(Offer(VulnerabilityCase))` gives way to the Owner's own `Offer(VulnerabilityCase)` naming the transferee, sent to the CASE_MANAGER and ledgered as the Owner's decision.
ADR-0148's other decisions stand: the CASE_MANAGER makes the one Offer the transferee receives and answers, under an id derived from the Owner's, only an active participant may be offered ownership, at most one open Offer per case, and the Owner withdraws with `Undo` of its own Offer.
ADR-0148 rejected relaying the Owner's Offer to the transferee because the delivered activity's `actor` would not be its sender, and the CASE_MANAGER would keep its record of the Offer under the Owner's id.
Both reasons still hold, and the CASE_MANAGER's own Offer still answers them.

It partially supersedes ADR-0180 in the Owner's two decision messages: `Add(EmbargoEvent, target=VulnerabilityCase)` and `Reject(EmbargoEvent, target=VulnerabilityCase)` become `Update(EmbargoEvent)` setting `status` active or rejected.
ADR-0180's other decisions stand: participants answer invitations and the Owner decides for the case, each decision names its proposal in `inReplyTo`, an Owner that declined accepts before it activates, and the Owner's answer does not constrain its rejection.

The vocabulary rules behind it, including that `origin` names where something comes from or leaves, are in `notes/activitystreams-semantics.md` § "Choosing AS2 Terms".
The work it implies is tracked in `notes/as2-vocabulary-alignment.md`.
