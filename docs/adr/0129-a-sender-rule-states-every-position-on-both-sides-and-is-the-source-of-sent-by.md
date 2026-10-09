---
status: proposed
date: 2026-10-09
created: 2026-10-09
updated: 2026-10-09
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; IDEA-4433; ADR-0113, ADR-0115, ADR-0128;
  specs/handler-protocol.yaml HP-01;
  specs/message-semantics-mapping.yaml MSM-08;
  specs/case-management.yaml CM-30;
  specs/participant-case-replica.yaml PCR-03, PCR-08;
  notes/message-type-reference.md
informed: []
stakeholder_type: [project-contributor]
---

# A Sender Rule States Every Position on Both Sides, and Is the Source of "Sent By"

## Context and Problem Statement

The occasion lookup table (ADR-0128) tells an emitter what to send in a given situation, and its "Sent by" column says who sends it.
That column is meant to be derived from the sender rule each received use case declares (ADR-0115), so that it cannot drift from what receivers enforce.
The goal is that every "Sent by" cell names an identified CVD role or an identified position within one exchange, such as the invitee or the addressee of a case proposal.

Three things stand in the way.

- **Positions have no home in the docs model.**
  The "usually" note an occasion may add is typed as CVD roles, and a CVD role is a durable fact stored on a participant record.
  A position is held only relative to one exchange: the same coordinator receives one report and sends the next, and a report precedes any case.
  Some positions already exist as entitlement kinds (the invitee, the actor a request was addressed to); others, such as the author of a note, exist only inside one tree's guard.
- **A declared rule can be a floor, not the rule.**
  `Remove(Note)` declares "an active participant", but CM-30-001 entitles only the note's author or the Case Owner; the narrower check lives in the tree.
  A cell derived from the declaration would understate who may send.
- **One wire activity can carry two occasions with different senders.**
  A participant proposing an embargo sends `Invite(Event)` to the CASE_MANAGER; the CASE_MANAGER, asking a participant about a proposal on the Case Owner's behalf (ADR-0113), sends `Invite(Event)` to that participant.
  Both match one registry entry and one use case, whose check is two-sided: an active participant when addressed to the CASE_MANAGER, the CASE_MANAGER when addressed to a participant.
  A rule declared as one kind cannot give the two rows different senders.

Where do positions live, and what shape must a declared sender rule have so that "Sent by" is derived for every occasion without hand maintenance?

## Decision Drivers

- "Sent by" is derived, never typed: a hand-written cell drifts from the rule the receiver applies.
- The declaration is the whole rule: a guard narrower than the declaration is a second sender predicate in disguise.
- A position named in the docs is one the receiver enforces.
- `CVDRole` stays a set of durable participant facts.
- An emitter looks up its own situation, so each occasion needs its own sender and its own addressee.

## Considered Options

- Positions are entitlement kinds; a sender rule composes kinds, per addressee side, and is the source of "Sent by"
- A separate exchange-position vocabulary beside the entitlement kinds, used by the docs
- Positions added to `CVDRole`
- Positions as glossary terms only, used in occasion prose

## Decision Outcome

Chosen option: "Positions are entitlement kinds; a sender rule composes kinds, per addressee side, and is the source of 'Sent by'", because it keeps one vocabulary that is both enforced and rendered, and it is the only option under which every cell is derived.

1. **The entitlement kinds are the closed vocabulary of sender standings.**
   A kind is either a role a participant holds (Case Owner, CASE_MANAGER, active participant) or a position within one exchange (the invitee, the addressee, the author).
   No separate position vocabulary exists, and no position becomes a `CVDRole`.
   A position a new rule needs is added as a kind.
2. **One addressee kind, worded from the exchange.**
   The actor a request was addressed to is one kind, whatever the request, other than an Invite.
   The invitee stays a kind of its own, because it is checked against the Invite the receiver recorded rather than against an addressee the receiver wrote on its own record, and "invitee" is already the protocol's term.
   A position that is the addressee of a request, such as the transferee of a case ownership offer, is this kind and not a new one.
   Its rendered wording names the request from the answered activity's object type ("the addressee of the case proposal"), so it is identified without a kind per request type.
3. **A declared sender rule is the full rule.**
   It is composed of kinds and may require any one of several ("the note's author or the Case Owner").
   It is stated per addressee side: the standing a sender needs when the activity is addressed to the CASE_MANAGER, when it is addressed to a participant, and, for an activity sent before a case exists, when it is addressed to an actor outside any case.
   The receive-tree factory composes the guard from the declaration alone, and no tree adds a narrower sender check of its own.
4. **Each kind carries its own wording and glossary term.**
   The words a "Sent by" cell uses for a kind are declared with the kind, not in a table elsewhere, and each kind's term is defined in the glossary.
5. **Each occasion declares its addressee, and its sender is derived.**
   An occasion names whom it is sent to, from the sides a rule can have.
   "Sent by" is the matching side of its use case's rule, and the addressee also renders as "Send to".
   An occasion naming a side its rule does not have is an error.
6. **The "usually" note stays CVD roles.**
   It records the CVD convention ("an active participant (usually: vendor)") and is never the rule.
   An exempt use case still reads "not yet checked" until its exemption closes in the new shape.

### Consequences

- Good, because every "Sent by" and "Send to" cell is a rendering of declared data, and the docs cannot name a sender the receiver does not check.
- Good, because the two `Invite(Event)` occasions get their own rows, senders and addressees from one declared rule.
- Good, because the guards that live inside individual trees today (the two-sided embargo check, the note-author check) move into the one declaration, finishing what ADR-0115 started.
- Bad, because every non-exempt declaration is rewritten into the new shape, and the factory gains composition logic for "any of" and for sides.
- Bad, because a two-sided rule restates, on each declaration, the CASE_MANAGER side that most case-scoped messages share.

## Validation

- A test asserts that every kind has non-empty wording and that its glossary term exists in the glossary.
- The sender-entitlement ratchet (HP-01-007) also fails on a sender check composed inside a tree rather than from the declaration.
- Each rewritten declaration keeps its marked sender-clause tests (an entitled and an unentitled sender, per side).
- A test over every occasion asserts that its addressee is a side of its use case's rule, and that the rendered "Sent by" equals the wording of that side's kinds.

## Pros and Cons of the Options

### Positions are entitlement kinds; a sender rule composes kinds, per addressee side, and is the source of "Sent by" (chosen)

- Good, because one vocabulary is both enforced and rendered.
- Good, because the rule's sides are exactly what tells two occasions of one wire activity apart.
- Bad, because it changes the declaration shape ADR-0115 set up, so every declaration is touched.

### A separate exchange-position vocabulary beside the entitlement kinds, used by the docs

- Good, because the "usually" note could name positions without touching sender rules.
- Bad, because two lists name the same positions and must be kept in step.
- Bad, because no occasion was found whose rule is broad but whose usual sender is a position; the case it serves does not occur.

### Positions added to `CVDRole`

- Bad, because a position is relative to one exchange and a report precedes any case, so there is no participant record to store it on.

### Positions as glossary terms only, used in occasion prose

- Good, because it needs no code.
- Bad, because nothing checks that a position named in prose is one any receiver enforces, and the cells stay hand-written.

## More Information

This decision refines ADR-0115: the declaration it set up is kept, but a declaration is now a composed, two-sided rule rather than one kind.
It supplies the derivation ADR-0128 relies on for its "Sent by" column.
Source: #4433, raised while planning #4418.
