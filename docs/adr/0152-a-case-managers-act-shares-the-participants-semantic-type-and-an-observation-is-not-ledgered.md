---
status: proposed
date: 2026-10-21
created: 2026-10-21
updated: 2026-10-21
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0085, ADR-0107, ADR-0115, ADR-0119, ADR-0124, ADR-0140;
  specs/semantic-extraction.yaml SE; specs/case-ledger-processing.yaml CLP-02, CLP-07;
  specs/case-management.yaml CM-23, CM-28; specs/em-behavior.yaml EMB-16, EMB-17;
  issues #3743, #4723, #4724
informed: []
partially_supersedes:
  - 0140-a-ledger-entrys-semantic-type-is-the-registry-label-of-its-as2-payload.md
stakeholder_type: [project-contributor]
---

# A Case Manager's Act Shares the Participants' Semantic Type, and an Observation Is Not Ledgered

## Context and Problem Statement

[ADR-0140](0140-a-ledger-entrys-semantic-type-is-the-registry-label-of-its-as2-payload.md) settled that a ledger entry's semantic type is the label the semantic registry gives its AS2 payload.
It left open how the CASE_MANAGER's own entries get such a label.

An `ActivityPattern` sees an activity's type and the types of its object, target, context and recipients.
It does not see who sent the activity.
Several CASE_MANAGER entries share a shape with a participant's act, or with another CASE_MANAGER entry, and today each carries a semantic type of its own:

- The CASE_MANAGER's abandonment of an embargo proposal and a participant's refusal of an embargo invitation are both `Reject(Invite(EmbargoEvent))`.
- A re-invite of a late accepter, a relayed invitation and a proposal are all `Invite(EmbargoEvent)`.
- The case-closure marker and an owner change are both `Update(VulnerabilityCase)`.

Other entries record what the CASE_MANAGER observed rather than an act it chose.
The expiry of an ownership-transfer `Offer` is recorded as the CASE_MANAGER's `Undo(Offer)`, though anyone can read the expiry from the `Offer`'s `endTime` and no replica changes on it.
The closure marker carries a case each replica already holds.
The acknowledgement of a late `Accept` with no embargo to bind changes nothing at any replica.

The question this record settles is which semantic type a CASE_MANAGER entry carries, and which observations reach the ledger at all.

## Decision Drivers

- The registry is Vultron's one vocabulary; a shape should mean one thing wherever it appears (ADR-0140).
- What an activity is and whether its sender may send it are different questions, and only the first belongs to routing.
- Vultron should use the standard AS2 verbs, without subclassing them or adding marker fields, for as long as they suffice.
- A replica never reads a clock or runs lifecycle logic on replay (CM-23-016, [ADR-0124](0124-case-is-a-projection-of-its-ledger.md)).
- A message that changes nothing at its receiver is noise on the wire and in the ledger.

## Considered Options

- One semantic type per shape, with the sender's standing decided after routing
- Patterns that see the sender's identity or role
- A distinct AS2 shape or marker field for each CASE_MANAGER act

## Decision Outcome

Chosen option: "One semantic type per shape, with the sender's standing decided after routing", because it keeps the semantic type a statement of what an activity is, and leaves whether the sender may send it to the use cases that already decide that ([ADR-0115](0115-received-handlers-check-sender-entitlement.md)).

1. **A semantic type says what an activity is; the sender's standing says whether it is permitted.**
   A pattern never discriminates on the sender's identity or role.
   When the CASE_MANAGER performs the same verb on the same kind of object as a participant, its activity carries the participant's semantic type.
   A receiver that must act differently for the CASE_MANAGER tells the two apart after routing, by the payload's `actor`, as a replica already tells a relayed embargo invitation from a proposal.
2. **Withdrawing an invitation one sent is `Undo(Invite)`; declining an invitation one received is `Reject(Invite)`.**
   An actor undoes only an activity it performed.
3. **An observation is not an act.**
   When anything that holds the case and its ledger could derive a fact itself, such as a deadline that has passed or a closure that is complete, the CASE_MANAGER commits no entry recording the observation.
   It commits only the case-file change the observation causes, as its own entry (CLP-07-013), so a replica copies the change and never evaluates the deadline.
   An activity that would change nothing at any of its receivers is not sent and not ledgered.

The rulings for the shapes [ADR-0140](0140-a-ledger-entrys-semantic-type-is-the-registry-label-of-its-as2-payload.md) left open follow:

| Occasion | Recorded as |
|---|---|
| An embargo invitation's RSVP deadline passes | The CASE_MANAGER's `Update(EmbargoConsent)` carrying the invitee's `TIMED_OUT` row; no act entry precedes it |
| An ownership-transfer `Offer`'s `endTime` passes | Nothing; a late `Accept` is refused from the `Offer`'s own `endTime` |
| The CASE_MANAGER honours a late `Accept` of an embargo invitation | The received `Accept` itself, as `accept_invite_to_embargo_on_case`, carrying the row it states as an on-time `Accept` does; no follow-up consent entry |
| A late `Accept` arrives when the case has no embargo for it to bind | Nothing is ledgered and nothing is sent |
| The CASE_MANAGER re-invites a late accepter to the current embargo | A relayed `Invite(EmbargoEvent)` naming the embargo's proposer in `attributedTo`, as `invite_to_embargo_on_case` |
| The CASE_MANAGER abandons an open embargo proposal (EMB-16-001) | Its `Reject(Invite(EmbargoEvent))` of the proposal it received, which carries the cancel step, then its `Undo(Invite(EmbargoEvent))` of each invitation it relayed for that proposal; when the CASE_MANAGER made the proposal itself, the cancel is an `Undo` of its own proposal |
| The case becomes fully closed | Nothing beyond the closure's status entries; the owner-close write boundary (ADR-0085) is the CASE_MANAGER's own status entry reaching `RM.CLOSED` |
| The CASE_MANAGER changes the case owner | `Update(VulnerabilityCase)` |
| The CASE_MANAGER creates or updates a participant record or a consent row | `Create` or `Update` of `CaseParticipant` or `EmbargoConsent` |

Abandonment is a meeting that cannot happen at the proposed time: the organiser tells the person who proposed it that the time does not work, and tells each colleague it invited that the meeting is off.

### Consequences

- Good, because one shape has one semantic type, so the registry's label for a ledger payload is decidable from the payload alone.
- Good, because entitlement stays in the use cases, and no pattern needs to know who holds the CASE_MANAGER role for a case.
- Good, because the ledger records acts and case-file changes only, so a replica's replay never depends on the clock.
- Neutral, because a replica apply step for a merged type reads the payload's `actor` to choose its effect, as the relayed-invitation step already does.
- Bad, because merged types change stored `semanticType` values, so a ledger written before the change carries values the registry no longer issues.
- Bad, because abandonment writes one entry per relayed invitation instead of one per proposal.

### Confirmation

- A test asserts that `ActivityPattern` has no field for the sender's identity or role.
- The ledger-equality test of #4724 asserts every committed entry's `semanticType` equals the registry's match for its payload.
- Tests assert that no entry is committed for an invitation expiry act, an `Offer` expiry, a closure marker or a no-op late `Accept`.

## Pros and Cons of the Options

### One semantic type per shape, with the sender's standing decided after routing

- Good, because it needs no new pattern machinery and no new AS2 vocabulary.
- Good, because it matches how the inbox already separates routing from the sender-entitlement gate.
- Bad, because a receiver that must act differently by sender does so in its apply step, not in its routing.

### Patterns that see the sender's identity or role

- Good, because routing alone would tell a CASE_MANAGER act from a participant's.
- Bad, because it folds whether a sender may send an activity into what the activity is.
- Bad, because the matcher would need to know who holds the CASE_MANAGER role for each case, which a shape-only matcher does not.

### A distinct AS2 shape or marker field for each CASE_MANAGER act

- Good, because every act would be distinguishable by shape.
- Bad, because it subclasses or extends standard AS2 verbs before the standard ones have run out.
- Bad, because a shape invented per act is a parallel naming scheme, which ADR-0140 set out to remove.

## More Information

- Decided in the 2026-10-21 planning session for #4723.
- ADR-0140's revision 2 (#3743) records an honoured late `Accept` as the CASE_MANAGER's `Update(EmbargoConsent)` and an `Offer` expiry as its `Undo(Offer)`; this record replaces those two rulings with the ones in the table above.
- Glossary: **Semantic Type**, **Pocket Veto** and **RSVP Deadline** in [the glossary](../reference/glossary.md).
