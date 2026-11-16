---
status: proposed
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0116, ADR-0122, ADR-0199, ADR-0202;
  specs/em-behavior.yaml EMB-13, EMB-19; specs/case-management.yaml CM-31;
  notes/as2-vocabulary-alignment.md; issue #6246
informed: []
stakeholder_type: [project-contributor]
---

# An Embargo's End Is an Update of the Embargo, Announced to Every Signatory

## Context and Problem Statement

An embargo ends as `Remove(EmbargoEvent)[origin=<case>]`, with what ended it in `content` (`END_TIME_REACHED` or `EARLY`) and why in a Vultron `terminationCause`.
`Remove` says the embargo left the case, but it stays on the case, terminated.
`content` is natural-language text in ActivityStreams 2.0, not a machine field.
When the Case Owner ends an embargo early, it sends that `Remove` to the CASE_MANAGER, which records the Owner's message as the act, though the CASE_MANAGER is the one that changes the embargo.

After an embargo ends, the CASE_MANAGER also sends a teardown `Announce(EmbargoEvent)` to every active participant, so that everyone the embargo may have bound learns that it ended.
Signatories the ledger does not reach, such as a removed participant, get a separate direct copy of the termination instead (ADR-0116).

How does an embargo's end go on the wire, and how does every participant it may have bound learn of it?

## Decision Drivers

- A verb describes what was done: the embargo stays on the case, and its status changes.
- An activity states what its sender did; a request for another actor to act is an `Offer` of the act (ADR-0199).
- Everyone an embargo may have bound is told, explicitly, that it ended.
- A notice of a change announces the act that made it, so a receiver can tell the notice and the ledger entry are the same change.

## Considered Options

- An `Update` of the embargo, announced as an `Announce` of that `Update`
- An `Update` of the embargo, announced as an `Announce` of the embargo
- `Remove(EmbargoEvent)`, as today

## Decision Outcome

Chosen option: "An `Update` of the embargo, announced as an `Announce` of that `Update`", because the verb is true, the notice carries who ended the embargo and why, and a receiver matches the notice to its ledger entry by the act's id.

### The end is an Update of the embargo

An embargo ends with `Update(EmbargoEvent)` setting its `status` to terminated and its termination: the cause kind, the act that caused it when known, and a human reason in `summary` (ADR-0202).
End time reached is a cause like the others, so the separate `END_TIME_REACHED`/`EARLY` field goes.
The CASE_MANAGER makes and ledgers every such `Update`, including an end-time termination.

When the CASE_MANAGER ends an embargo itself, at its end time or on a threat signal, it sends the `Update` with no request.
When the Case Owner ends an embargo early, it sends `Offer(Update(EmbargoEvent))`.
The CASE_MANAGER refuses it, for instance when it names a threat signal, which only the CASE_MANAGER may name, or it accepts it and makes the `Update` itself, as ADR-0199 describes.

`Remove(EmbargoEvent)` is retired.

### Every signatory is told, by an Announce of the Update

After the `Update` commits, the CASE_MANAGER sends `Announce(<the Update>)` to every active participant and to every signatory the ledger fan-out does not reach.
That one notice replaces the separate direct copy to an unreached signatory.
A signatory whose stream is paused applies the end from the notice, and a later replay of the ledger entry carrying the same act changes nothing.
The notice of a shorter revision follows the same rule: it announces the act that made the revision active.

### Consequences

- Good, because every message about an embargo's end is true of its sender, and a generic reader reads it as an event's status change.
- Good, because one notice reaches everyone the embargo may have bound, and it carries the act's id, cause, author and request.
- Bad, because the termination messages, their patterns, the teardown, the examples and the message reference all change. Pre-1.0, the old forms are replaced outright.

## Validation

- A test ends an embargo at its end time and asserts one ledgered `Update` with status terminated and an end-time cause.
- A test sends the Owner's `Offer(Update(EmbargoEvent))` and asserts the Accept, the CASE_MANAGER's `Update` with `inReplyTo` the Offer, and the refusal of a threat-signal cause from the Owner.
- A test asserts that the `Announce` reaches every active participant and every signatory the fan-out skips, and that replaying the entry after applying the notice changes nothing.

## Pros and Cons of the Options

### An `Update` of the embargo, announced as an `Announce` of that `Update`

- Good, because the notice is the change, with its id, cause and author.
- Bad, because a receiver must read the embargo's new status from inside the announced act.

### An `Update` of the embargo, announced as an `Announce` of the embargo

- Good, because the notice carries the embargo as it now stands.
- Bad, because the receiver must infer the end from the status, and needs a separate rule to match the notice to the ledger entry.

### `Remove(EmbargoEvent)`, as today

- Good, because nothing changes.
- Bad, because it says the embargo left the case, and its reason travels in a natural-language field.

## More Information

The embargo's stored status and termination are ADR-0202.
The Owner's request as an Offer of the act is ADR-0199.
