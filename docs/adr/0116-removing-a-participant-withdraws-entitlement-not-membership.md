---
status: accepted
date: 2026-10-01
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; CONCERN-2257; ADR-0093, ADR-0108, ADR-0109, ADR-0113,
  ADR-0114, ADR-0115 (PR #4068); specs/case-management.yaml CM-10, CM-17, CM-23, CM-24;
  specs/received-status-handling.yaml RSH-08;
  docs/reference/vultron-spec/_participant-lifecycle.md § 11.4
informed: []
stakeholder_type: [project-contributor]
---

# Removing a Participant Withdraws Entitlement, Not Membership

## Context and Problem Statement

The published specification says "A Case Owner or Case Manager MAY remove a participant from a case" and leaves the mechanics unspecified.
The implementation has a `Remove(CaseParticipant)` message whose handler deletes the participant record from `case_participants`.
CONCERN-2257 found that the deletion cannot reach anyone else:

1. No protocol flow emits the message; only an exchange demo does.
2. `("Remove", "CaseParticipant")` is not a canonical ledger signature, and no replica apply node exists, so a removal applied by the CASE_MANAGER is invisible to every replica.
   That is a permanent roster divergence by construction.
3. Deleting the record erases the participant's history from the case: the ledger entries it authored now name an actor the roster no longer holds.

The concern also found that the CASE_MANAGER's direct `Add(CaseParticipant)`, emitted to every participant after an invitee accepts the stub Invite, is redundant.
CM-17-004 does not call for it.
Replicas already learn of the new member from the `Accept(Invite)` ledger entry (`ApplyInviteAcceptFromLedgerNode`).
A replica usually refuses the message anyway, because it holds no copy of the `CaseParticipant` record it names.
The CASE_MANAGER also commits it as a second ledger entry for a move the first entry already recorded.

The question: **what does removing a participant change, who may do it, how does every replica learn it, and what does the removed party still receive?**

## Decision Drivers

- Removal is a decision the case makes about a participant, not a statement the participant makes about itself.
  It must not be modelled as a consent state (ADR-0084: participant status is self-declaratory).
- Entitlement to case content is already an explicit, computed check (the active participant, CM-10-004, ADR-0114), not roster membership.
- Only the CASE_MANAGER turns an assertion into case state, and replicas take case state from the ledger (ADR-0108).
  One move gets one ledger entry, authored by the actor that made the move.
- A participant bound by an embargo stays bound however it stopped receiving case content, and must be able to learn when that obligation ends.
- Inferred statuses are computed from stored facts, never stored themselves (the precedent is `embargo_adherence`, CM-18-008 and CM-18-014).

## Considered Options

1. **Delete the record and ledger the deletion.** Keep today's semantics and make the deletion replicate.
2. **Add a `REVOKED` embargo-consent state that only the CASE_MANAGER sets.**
3. **Record removal as a stored fact on the participant; removal withdraws entitlement to case content and keeps the record.**

## Decision Outcome

Chosen option: **Option 3**.
It keeps the participant's history in the case, expresses removal on the axis it belongs to (entitlement, not consent), and reuses the active-participant check that every case-content send already goes through.

### Removal is a stored fact; being active is computed

A participant record carries a stored removal fact.
The record, its status history and the ledger entries it authored all stay.
Whether a participant is active is computed by **one case-level check** from stored facts: joined (seated by case initialization, or accepted its stub Invite), not removed, and `SIGNATORY` when an embargo is active.
The answer is never stored.
RM `CLOSED` is not part of the check, but it ends content delivery all the same: a closed participant receives only the entry that records its own closure, and `case_fully_closed` reaches only participants not yet closed (CM-23-004, ADR-0114).

The check is a case method, not a participant property.
"Is an embargo active" is case state that a participant record cannot see, and a participant-level property covering only part of the answer would read as "active" at a send site and leak embargoed content to a non-signatory.
That is the ambiguity the glossary already flags for "joined participant".

Authority to act on a case requires being active.
No situation calls for an actor to act on a case whose content it may not see.
An inert participant's only messages are its replies to the Invites addressed to it, and those answer the Invite; they do not act on the case.
This is the rule `notes/case-joining.md` § "Authority to act" already records, and ADR-0115 (PR #4068) is deciding for the sender-entitlement checks; removal adds only that a removed participant loses its authority with its content.
The CASE_MANAGER's authority to commit comes from its role (CLP-09), not from being active.

### The case publishes `activeParticipants`; `Remove` takes a participant out of it

The case exposes a computed `activeParticipants` collection on the wire, derived by the active check.
`case_participants` stays the full roster: the authoritative membership that `actor_participant_index` and role resolution read (CM-19-001).
`Remove(CaseParticipant, target=VulnerabilityCase)` therefore says what it does: the participant leaves the active collection.
The target stays the case, so the existing message pattern is unchanged.

Removal is not the only way out of `activeParticipants`.
A participant whose consent lapses also leaves it, and returns when it consents.
The view says who receives case content now; `Remove` is the case's decision to take a participant out and keep it out.

Because `activeParticipants` is computed and appears in the serialized case, reading that serialized form back in must ignore or recompute it, never refuse it as an unknown key.

### Only the Case Owner requests removal; the CASE_MANAGER applies it

The Case Owner sends `Remove(CaseParticipant)` to the CASE_MANAGER (PCR-03-006, ADR-0109).
Where they are the same actor, the actor posts to its own inbox.
The CASE_MANAGER refuses a removal requested by anyone else, a removal of the CASE_MANAGER (the role is never unfilled, CM-24-006), and a removal of the Case Owner (ownership is transferred first, CM-21).
A second removal of an already-removed participant is skipped.
The CASE_MANAGER does not remove a participant on its own initiative.
No spec gives it a policy for doing so, and the ledger must show the removal as the Case Owner's decision.

A participant that wants to stop taking part leaves the case (`Leave(VulnerabilityCase)`, CM-23).
That is not removal and needs nothing new.

### One ledger entry, and a direct notice to the removed party

The Case Owner's received `Remove` is the single ledger entry, committed by the receive pipeline (intake, guards, commit, effects, CLP-10-006), and `("Remove", "CaseParticipant")` becomes a canonical signature.
The CASE_MANAGER commits no second entry of its own.

The CASE_MANAGER sends the removed party a direct `Remove(CaseParticipant)` naming it, as the CASE_MANAGER, crediting the Case Owner (CM-24).
The notice is delivery, not a record, and is not ledgered.
The removal entry's fan-out selects its recipients before the removal is applied, so the removed party receives that entry too.
It is the last ledger entry the removed party receives until it is reinstated, and its replica applies it through the replica apply node that every other replica uses.

### Removal changes no consent, and bound participants hear when the embargo ends

Removal leaves the participant's embargo consent and `accepted_embargo_ids` untouched.
A removed signatory stays bound; releasing it would reward the conduct that got it removed.

A bound participant must learn when its obligation ends or shortens.
So when the active embargo ends or is replaced by a shorter one, the CASE_MANAGER sends every `SIGNATORY` participant that the ledger fan-out no longer reaches a direct notice, outside the ledger stream.
That covers a removed participant and a participant whose RM is `CLOSED` after `Leave`, whom CM-23-004's fan-out skips and who has the same gap today.
The messages are the existing ones:

| Change | Notice |
|---|---|
| Termination, including the case going public | `Remove(EmbargoEvent)` (ET) |
| A shorter revision activated (ADR-0093 containment) | `Announce(EmbargoEvent)` with the new terms |
| A longer revision activated | none: the participant never agreed to it and its own terms stand |
| Expiry on the agreed date | none: the participant already knows the date |

A past-dated `Announce(EmbargoEvent)` is not used.
Its meaning would depend on the receiver's clock, and early termination is an event, not a date that passed.

A participant whose ledger stream is paused cannot take these changes from the ledger, so it applies them from the notice: a narrow exception to RSH-08-003.
The exception is to the channel, not to the authority.
The notice must come from the CASE_MANAGER (PCR-03-001), and replaying the corresponding ledger entry later, after reinstatement, must change nothing.

### `Add(CaseParticipant)` reinstates, and only reinstates

The Case Owner reverses a removal by sending `Add(CaseParticipant, target=VulnerabilityCase)` to the CASE_MANAGER, through the same pipeline as removal: owner-only, one ledger entry, a direct notice, a replica apply node.
The participant does not accept again; it never withdrew.
An `Add` naming a participant that is not removed, or that never joined, is refused.
Joining requires accepting a stub Invite (ADR-0114), and `Add` must not become a way around that.

The CASE_MANAGER's direct `Add(CaseParticipant)` after an invitee accepts the stub Invite, and its `add_case_participant` ledger entry, are dropped.
Replicas keep learning of new members from the `Accept(Invite)` entry.

### Catch-up follows the active check, and a removed participant is not invited

A removed participant's replica is a prefix of the ledger ending at the removal entry.
When it becomes active again, the existing backfill (CM-10-006) sends it every entry it was not sent, in log order, and the hash chain joins with no gap.
Backfill fires whenever the active check turns from false to true, for any reason.
That includes a participant reinstated into a case whose embargo it has not accepted: it stays inert, and catch-up waits for its consent.

A removed participant receives no Invites: not the stub, not the full-case Invite, and not an embargo Invite.
The only exception is the embargo-ending notices above.
A participant reinstated into a case with an active embargo it has not accepted is sent that embargo's Invite on reinstatement.

### Consequences

- Good, because a removal reaches every replica through the ledger, so the divergence CONCERN-2257 found cannot occur.
- Good, because the case keeps a complete record of who took part and when.
- Good, because removal is enforced by the one active check every send already uses; no send site gains a rule of its own.
- Good, because the Case Owner's decision is the ledger entry, so the record shows who decided, not only who applied it.
- Good, because a bound participant can always learn that its embargo ended, which also closes the same gap for participants that left.
- Bad, because `Remove` and `Add(CaseParticipant)` change meaning.
  The manage-participants demo, the message reference, the how-to and the existing tests that pin record deletion all change.
- Bad, because a non-active participant now receives a class of direct messages that the ledger does not carry, and its replica must apply them, so idempotence between the two channels has to be tested.
- Neutral, because the full roster and the stub-Invite join flow are unchanged.

## Validation

- Strict `xfail` goal tests carry the CM-31 markers until each implementation issue lands.
- A received-side test drives a removal from the Case Owner and asserts the record remains, the participant is absent from `activeParticipants`, one ledger entry was committed, and the removed party was sent the notice and the entry.
- A test asserts a reinstated participant receives the withheld entries in order, and that replaying an embargo change it already took from a direct notice changes nothing.

Spec requirements: `specs/case-management.yaml` CM-31 (new); CM-10-004, CM-10-006 and CM-10-007 amended; `specs/received-status-handling.yaml` RSH-08-003 amended; `specs/vultron-as2-mapping.yaml` VAM-06-002 and VAM-06-003 annotated.

## Pros and Cons of the Options

### Delete the record and ledger the deletion

- Good, because it keeps the message's literal ActivityStreams meaning.
- Bad, because the case loses the participant's history, and ledger entries name an actor the roster no longer holds.
- Bad, because reinstatement becomes rejoining, so a participant who never withdrew must accept again.

### A `REVOKED` embargo-consent state set only by the CASE_MANAGER

- Good, because the content gate already reads consent.
- Bad, because consent gates content only while an embargo is active, so a revoked participant would receive content again on a case with no embargo.
- Bad, because embargo termination resets every participant's consent to `UNBOUND`, erasing the revocation, and the next embargo would invite the participant back automatically.
- Bad, because consent is the participant's own statement (CM-18-005).
  Revocation is a decision about it, and placing both on one machine invites confusing `DECLINED` with `REVOKED`.

### A stored removal fact; removal withdraws entitlement

- Good, because removal holds with or without an embargo and survives embargo resets.
- Good, because it composes with the active check that every send already uses.
- Bad, because the case gains a computed collection that must round-trip through serialization.
