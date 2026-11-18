---
status: accepted-provisional
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-18
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0114, ADR-0116, ADR-0172 (the records this one
  consolidates); ADR-0199, ADR-0205 (live records whose parts on this lifecycle it
  restates); ADR-0203, ADR-0212 (the embargo-end notice); ADR-0093, ADR-0121,
  ADR-0124; specs/case-management.yaml
  CM-10, CM-11, CM-17, CM-23, CM-31; specs/rm-behavior.yaml RMB-14;
  CONCERN-4006, CONCERN-2257, CONCERN-5574; issues #6295, #6465, #6511
informed: []
supersedes:
  - 0114-joining-a-case-stub-invite-inert-participant.md
  - 0116-removing-a-participant-withdraws-entitlement-not-membership.md
  - 0172-an-active-participant-is-not-closed.md
stakeholder_type: [project-contributor]
---

# How a Participant Joins, Becomes Active and Is Removed

## Context and Problem Statement

An actor goes from "invited" to "participating" in a case, may stop receiving case content, and may be removed and let back in.
ADR-0114 decided how an actor joins: the stub Invite creates an inert participant record, entitlement to case content is an explicit check, and RM may close from *Received*.
ADR-0116 decided that removing a participant withdraws its entitlement and keeps its record.
ADR-0172 then narrowed "active" to exclude closed participants, replacing a statement in each of the two.
ADR-0199 replaced ADR-0116's removal and reinstatement messages, ADR-0203 its embargo-change notices (now stated by ADR-0212), and ADR-0205 ADR-0114's stub type.
ADR-0114 and ADR-0116 also each carried a dated in-place correction about which ledger entries a replica learns a new participant from.

So the lifecycle could be read only by laying six records over each other.
This record states the three decisions it supersedes as one, and restates the parts of ADR-0199 and ADR-0205 that bear on the lifecycle, which stay live for their other decisions.
It decides nothing they did not.

How does an actor become a participant, what makes a participant entitled to case content, and what does removing one change?

## Decision Drivers

- **The CASE_MANAGER tracks an invitee from the moment it is invited**: whether it was told, whether it answered, and how.
- **Case content reaches only entitled actors**: entitlement is having joined and, while an embargo is in force, being party to it; many cases have no embargo in force, so entitlement cannot be "is a signatory" alone.
- **A participant's status is its own declaration** (ADR-0121), so no other party writes a judgement the participant has not made, and a timeout never stands in for one.
- **Removal is a decision the case makes about a participant**, not a statement the participant makes about itself, so it is not a consent state.
- **Every change to the case is a message in the ledger**, and a replica copies what each entry carries and infers nothing from another entry (ADR-0124).
- **A receiver classifies an activity by its shape**, so two messages that mean different things differ in shape.
- **A term means what rule authors take it to mean**: "active" means "may still act and receive new case content" with no qualifier.
- **A participant bound by an embargo stays bound** however it stopped receiving case content, and must be able to learn when that obligation ends.

## Considered Options

1. **The Invite creates the record; a participant is active only while it has joined, is not removed, is not closed, and is a signatory to an embargo in force; removal is a stored fact that withdraws entitlement.**
2. **Create the record when the invitee accepts, and add recipient filters only.**
3. **As option 1, but delete the record when the invitee declines.**
4. **Delete a removed participant's record, and ledger the deletion.**
5. **Record removal as a `REVOKED` embargo-consent state that only the CASE_MANAGER sets.**
6. **Keep "active" broad, including closed participants, and coin or lint a separate term for "active and not closed".**

## Decision Outcome

Chosen option: **option 1**, because it tracks every invitee from its Invite, makes entitlement one explicit check instead of a side effect of roster membership, records only judgements the participant made, and keeps a removed participant's history in the case.

### Decision details

1. **The stub Invite creates the participant record.**
   When the CASE_MANAGER sends a stub Invite it creates the invitee's `CaseParticipant` in the same step (CM-11-006).
   The record holds the roles the Invite names, RM `RECEIVED`, VF `v` for the VENDOR role, and an `INVITED` consent row when an embargo is in force (CM-11-026).
   The Invite names at least one role, and the CASE_MANAGER substitutes no default (CM-11-019, CM-11-048 to CM-11-050).
   This is the one place a vendor participant carries `v`.

2. **Every change has a ledger message, and a replica copies it.**
   The ledger holds the wire messages exchanged, and one trigger can yield several entries.
   The stub Invite is the `invite_actor_to_case` entry, from which a replica applies nothing.
   Seating the record is the CASE_MANAGER's own `add_case_participant_to_case` entry, an `Add(CaseParticipant)` with the case as its `target`, carrying the whole record as stored; a replica stores it exactly so, in the list its `target` names (CM-11-023 to CM-11-025, CLP-07-021).
   The invitee's `Accept` and `Reject` are the entries for their own effects, and a vendor's VF change is its own status entry.
   A replica applies each entry through the functions the CASE_MANAGER uses, and moves a record only forward when it replays an older entry over a seed (CM-31-037 to CM-31-039).

3. **A participant is active when four things hold, and inert otherwise.**
   It joined, by being seated by case initialization (CM-14-001) or by accepting its stub Invite; it has not been removed; its closure is not recorded in the case's ledger; and, while an embargo is in force, it is a signatory to that embargo (CM-10-004).
   One case-level check computes the answer from stored facts; the answer is never stored, and no participant-level property computes part of it under a name that reads as "active" (CM-31-002, CM-31-018, CM-31-019).
   "Is an embargo in force" is case state a participant record cannot see, which is why the check belongs to the case.
   The check runs in the shared recipient selection every case-content send uses, never at a send site (CM-10-007).
   Being on the roster is not entitlement (CM-17-005).
   A participant becomes inert again when its consent lapses under a newly activated embargo, and active again when it consents (ADR-0093).
   Authority to act on a case requires being active; the CASE_MANAGER's authority comes from its role.

4. **Invites reach an inert participant; case content does not.**
   An inert participant receives no ledger entries, case announcements, status broadcasts or embargo announcements.
   The stub Invite and an embargo Invite are addressed to it because it is not yet active, are not case content, and reach it unless it was removed (CM-10-009).

5. **The case publishes who is active.**
   The case's `activeParticipants` collection holds exactly the active participants (CM-31-003), while `case_participants` stays the full roster that role resolution reads.
   A receiver recomputes the collection rather than refusing it as an unknown key, and refuses a supplied value that contradicts its own (CM-31-020, CM-31-021).
   No collection of invited, removed or closed participants is published; the roster and the ledger hold that history.

6. **A closed participant is inert, and is owed three deliveries only.**
   It receives the ledger entries that record its own closure, chosen by their subject, and only if it was entitled apart from its closure (CM-23-031).
   It waits for those entries rather than writing its own `CLOSED` (CM-23-032).
   A `Reject(CaseLedgerEntry)` from it is answered with a replay capped at those entries (CM-23-048).
   As a signatory, it receives the notice that the embargo it is bound by ended or was shortened (detail 15).
   Nothing else reaches it, and it may act on nothing else.

7. **The stub Invite has two replies, and either one shows awareness.**
   `Accept` joins the case and consents to the embargo in force: RM stays `RECEIVED`, VF becomes `V`, consent becomes `SIGNATORY` when an embargo is in force, and the CASE_MANAGER records no RM transition from it (CM-11-001, PCR-08-012).
   `Reject` is a hard no: RM `CLOSED`, VF `V`, consent `DECLINED` when an embargo is in force, and the record is kept, inert (CM-11-007).
   `TentativeReject` is not a reply to a stub Invite and is refused (CM-11-028): the invitee has seen only the preview, and its judgement of the case answers the full-case Invite (ADR-0121).
   A reply for an invitee with no record is refused with a reported reason and writes nothing (CM-11-018, CM-11-021, CM-11-052).

8. **An unanswered stub Invite expires; the participant does not change.**
   A stub Invite carries a reply deadline (CM-11-014).
   When it passes, the Invite closes as an expired ask and the record stays inert at `RECEIVED` with its consent row `INVITED`, which records the truth: told, never answered (CM-11-039, CM-11-040).
   A case-wide "all participants closed" check counts only joined participants (CM-11-041).
   The CASE_MANAGER may re-invite on the same record with a new deadline, naming the earlier Invite in `inReplyTo`, and refuses to re-invite a participant that joined or is at `CLOSED` (CM-11-015, CM-11-042, CM-11-043).

9. **A stub Invite outstanding across an embargo change is re-issued.**
   When the embargo in force is activated, revised or terminated while a stub Invite is outstanding, the CASE_MANAGER re-issues it on the same record with the current terms and a new deadline, naming the superseded Invite in `inReplyTo` (CM-11-016, CM-11-044).
   An `Accept` of a superseded stub Invite is refused, naming the replacement; a `Reject` of it is honoured (CM-11-045, CM-11-046).
   So nobody joins on terms that no longer apply, and the superseded Invite needs no `Undo`.
   A revision proposal is not such a change: it reaches the invitee as an embargo Invite, whose answer records consent and does not join the case (EP-09-002).

10. **Joining starts the ledger replay.**
    When the CASE_MANAGER processes an `Accept` of the stub Invite and the participant is active, it sends `Announce(VulnerabilityCase)` and replays the ledger to it at once, with no readiness signal from the participant (CM-11-008, PCR-02-002).
    It relays every open embargo proposal to the joiner (EP-09-011), and commits a vendor's VF entry after the case announcement and the backfill (CM-31-041).

11. **The stub Invite's object is the case's preview.**
    Its object is a typed reference naming the case by the case's own id, whose `preview` is the case's `CasePreview` (CM-11-013, ADR-0205).
    The preview carries a summary and, while an embargo is in force, the embargo terms, and nothing else (CM-17-010).
    A receiver tells the stub Invite from the full-case Invite by the object's form and type, never by its fields or its id (CM-11-038, MV-10-008).
    How every Invite uses AS2's slots is ADR-0205.

12. **RM closes from *Received*, and every closure is ordinary transitions.**
    The RM transition function permits `R → C` as well as `I → C`, `A → C` and `D → C`, and still forbids closing from *Valid* (RMB-14-004, RMB-14-008).
    A `Leave` from *Valid* is recorded as `V → D → C`, every closure uses only permitted transitions with no override of the table, and each transition is its own status entry, which a replica applies rather than re-deriving (RMB-14-005, RMB-14-009, CM-23-022, CM-23-038).
    A status update never creates a participant: an on-behalf assertion targets an existing participant (ADR-0121).

13. **Removal is a stored fact on a kept record.**
    Removing a participant records a removal fact on its record and deletes nothing: the record, its status history and the entries it authored stay (CM-31-001, CM-31-015, CM-31-016).
    Every actor treats a removed participant as inert (CM-31-017).
    Removal changes no consent row, so a removed signatory stays bound by the embargo it accepted (CM-31-008).
    A participant that wants to stop taking part leaves the case instead (CM-23); that is not removal.

14. **The Case Owner decides removal and reinstatement, and sends the act itself.**
    The Owner sends the CASE_MANAGER `Remove(<Actor>, origin=<case>)` or `Add(<Actor>, target=<case>)`, naming the actor as a typed reference, not the participant record (ADR-0199).
    Each actor has one participant record per case, so a reinstatement reuses it and keeps the participant's history and consent.
    The CASE_MANAGER refuses, with a refusal notice and nothing committed, an act from anyone but the Owner, one naming the CASE_MANAGER, the Owner or a non-participant, and a reinstatement naming a participant that is not removed or never joined, so reinstatement is never a way around the stub Invite (CM-31-004, CM-31-036).
    A second removal of a removed participant is skipped, and the CASE_MANAGER removes no one on its own initiative (CM-31-022, CM-31-023).
    The admitted act is the one ledger entry, with no second entry of the CASE_MANAGER's own (CM-31-005, CM-31-025).
    The removal entry's fan-out includes the removed party and is the last entry it receives until it is reinstated, and the actor the act names receives the CASE_MANAGER's `Announce` of the act (CM-31-027, CM-31-028, ADR-0199).
    A replica applies the change only from the entry (CM-31-007, CM-31-029).
    A reinstatement clears the removal fact and does not ask the participant to accept again (CM-31-034, CM-31-035).

15. **Catch-up follows the active check, and a bound participant hears when its embargo ends.**
    Whenever the active check turns from false to true, for any reason, the CASE_MANAGER backfills every entry the participant was not sent, in log order (CM-10-006).
    A removed participant is sent no stub, full-case or embargo Invite (CM-31-013); one reinstated into a case whose embargo in force it has not accepted is sent that embargo's Invite (CM-31-040).
    Every signatory the ledger fan-out does not reach, removed or closed, is told when the embargo it is bound by ends or is shortened, by a notice that carries no other case content (CM-31-009, CM-31-030, CM-31-031); what the notice is, is ADR-0212's.
    A participant whose stream is paused applies such a notice only from the CASE_MANAGER, and replaying the matching entry later changes nothing (CM-31-010, CM-31-032, CM-31-033).
    That is the one channel exception to taking case state from the ledger (RSH-08-003).

### Consequences

- Good, because the CASE_MANAGER sees every invitee from its Invite, including the ones that decline or never answer.
- Good, because entitlement to case content is one explicit check that every send uses, so a roster change cannot leak content by accident.
- Good, because a rule that says "active participant" excludes participants that left, and the deliveries a closed participant is owed are named where they are required.
- Good, because a removal reaches every replica through the ledger, and the case keeps a complete record of who took part and when.
- Good, because the Case Owner's decision is the ledger entry, so the record shows who decided, not only who applied it.
- Good, because every closure is an ordinary RM transition.
- Bad, because roster membership no longer means "accepted", and every roster consumer that read it that way had to change.
- Bad, because the RM model gains `R → C` and so no longer matches the original CERT MPCVD protocol paper's model.
- Bad, because a participant whose stream is paused receives direct notices the ledger does not carry, so idempotence between the two channels must be tested.
- Bad, because the serialized case carries a computed collection that must round-trip, and it changes whenever a participant closes.

## Validation

- `test/core/use_cases/received/test_stub_invite_replay.py` and `test/core/behaviors/case/test_accept_invite_tree.py` cover the record the stub Invite creates, its seating entry, and the replies.
- `test/core/use_cases/received/test_invite_resend.py` covers re-invites and re-issue across an embargo change.
- `test/architecture/test_active_participant_recipient_selection.py` and `test/core/behaviors/sync/nodes/test_active_participant_fanout.py` hold every case-content send to the shared active check.
- `test/core/states/test_rm_close_from_received.py` covers `R → C` and the absence of `V → C`.
- `test/core/use_cases/received/test_participant_removal.py`, `test/core/use_cases/received/test_participant_reinstatement.py` and `test/core/behaviors/sync/nodes/test_participant_removal_effect.py` cover removal, reinstatement and their replica effects.
- CM-10, CM-11, CM-23, CM-31 and RMB-14 carry each rule with its verification.

## Pros and Cons of the Options

### The Invite creates the record; active is computed; removal withdraws entitlement

- Good, because every invitee is tracked, entitlement is one shared check, and removal holds with or without an embargo.
- Bad, because it changes what roster membership means, which many consumers had assumed.

### Create the record at acceptance, and add filters only

- Good, because the roster keeps its old meaning.
- Bad, because the case has no record of an invitee before it answers, which is the tracking gap CONCERN-4006 found.
- Bad, because an on-behalf `v→V` has nothing to target except by minting a participant.

### Delete the record when the invitee declines

- Good, because the roster after a decline holds only actors that joined.
- Bad, because it discards the record that the actor was told and said no.

### Delete a removed participant's record, and ledger the deletion

- Good, because it keeps `Remove`'s literal ActivityStreams sense.
- Bad, because the case loses the participant's history, and its ledger entries name an actor the roster no longer holds.
- Bad, because reinstatement becomes rejoining, so a participant that never withdrew must accept again.

### A `REVOKED` consent state

- Good, because the content gate already reads consent.
- Bad, because consent gates content only while an embargo is in force, so a revoked participant would receive content again on a case with no embargo.
- Bad, because consent is the participant's own statement, and a decision about it on the same machine invites confusing `DECLINED` with `REVOKED`.

### Keep "active" broad

- Good, because nothing on the wire changes.
- Bad, because the shorter, more natural term is the wrong one for most rules, and a lint can find the phrase but not tell what the author meant.
- Bad, because the published `activeParticipants` would keep listing participants that left.

## More Information

This record supersedes, whole:

- [ADR-0114](archived/0114-joining-a-case-stub-invite-inert-participant.md): the record created by the Invite is detail 1, its ledger entries detail 2 (as its 2026-10-09 correction left them), inert and active details 3 and 4, the replies detail 7, expiry and re-invite detail 8, re-issue detail 9, the replay detail 10, the stub detail 11, and `R → C` and on-behalf status detail 12.
- [ADR-0116](archived/0116-removing-a-participant-withdraws-entitlement-not-membership.md): removal as a stored fact is detail 13, the Owner's decision and its entry detail 14, the published collection detail 5, and catch-up and bound participants detail 15.
- [ADR-0172](archived/0172-an-active-participant-is-not-closed.md): "active" excluding closed participants is detail 3, the published collection following it detail 5, and a closed participant's deliveries detail 6.

Not carried forward, because each had been overtaken before this record:

- ADR-0114's `create_case_participant` entry, `Create(CaseParticipant)`: the seating entry is `add_case_participant_to_case`, `Add(CaseParticipant)` with the case as `target` (CM-11-023, #6295).
- ADR-0114's stub with its own type, id and `caseId`: the stub Invite's object is the case's previewed reference (ADR-0205).
- ADR-0116's `Remove(CaseParticipant)`/`Add(CaseParticipant)` with the case as `target`, the CASE_MANAGER's separate unledgered notice, and the Owner posting to its own inbox when it is also the CASE_MANAGER: the Owner's act names the actor and is announced (ADR-0199).
- ADR-0116's notice table, `Remove(EmbargoEvent)` for a termination and `Announce(EmbargoEvent)` for a shorter revision, with no notice on expiry: the notice is an `Announce` of the act that made the change, sent on every end (ADR-0212).
- ADR-0116 and ADR-0114's statement that RM `CLOSED` is not part of the active check (ADR-0172).

These records stay live for their other decisions, and restate here only their parts on this lifecycle:

- [ADR-0199](0199-an-actor-sends-the-decision-it-makes-and-offers-only-what-another-decides.md) decides who sends each decision on a case.
- [ADR-0205](0205-invites-use-as2s-slots-and-the-stub-is-the-cases-preview.md) decides how every Invite uses AS2's slots.

Related:

- [ADR-0121](0121-joined-participant-judges-the-case-by-full-case-invite.md) decides how a joined participant judges the case through the full-case Invite, and scopes on-behalf status to existing participants.
- [ADR-0212](0212-how-embargo-status-and-participant-consent-are-recorded.md) decides embargo status and consent, and how an embargo's end reaches a signatory the ledger fan-out does not reach (detail 15).
- [ADR-0093](0093-signatory-declined-pec-transition.md) decides embargo consent and its lapse.
- [ADR-0089](0089-one-participant-status-writer.md) decides the single participant-status writer.
- [ADR-0124](0124-case-is-a-projection-of-its-ledger.md) decides that a replica copies its ledger.
- [ADR-0085](0085-case-lifecycle-boundaries.md) decides the case's lifecycle boundaries.
- `notes/case-joining.md` describes the join model for readers of the old one.

Generated spec requirements: `case-management.yaml` CM-10, CM-11, CM-17, CM-23 and CM-31; `rm-behavior.yaml` RMB-14; `participant-case-replica.yaml` PCR-02 and PCR-08; `embargo-policy.yaml` EP-09.
