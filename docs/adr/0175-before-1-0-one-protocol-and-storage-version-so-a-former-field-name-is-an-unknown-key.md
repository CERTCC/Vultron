---
status: accepted-provisional
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-03
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0099; ADR-0122; ADR-0140; specs/message-validation.yaml
  MV-11; issues #4872, #5573
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0099-one-object-model-as2-is-a-serialization.md
  - 0122-per-embargo-participant-consent.md
---

# Before 1.0, Vultron Supports One Protocol and Storage Version, So a Former Field Name Is an Unknown Key

## Context and Problem Statement

When a field is renamed or removed, a peer or a store can still hold data under the old name.
Vultron answered that with two lists of former names.
On the wire, the parse edge refused a whole activity when a key matched a list of retired names, with a message naming the replacement.
In storage, a shared model base refused a stored row that still held a former field, with a message naming the rename and saying the store must be reset.

Both lists exist only to keep an old version of the protocol or the store legible.
Vultron has not reached 1.0, it has one implementation, and its stores are reset when the shape changes.
Each rename added an entry to a list that nobody reads after the reset, and the wire list made one kind of unknown key behave unlike every other.

The question this record settles: before 1.0, does Vultron track the names that a field once had?

## Decision Drivers

- An unknown inbound key must be decided by one rule, whatever its history (ADR-0099).
- A stored row with a key the model does not declare must still be refused, never read through an alias.
- Each rename must not add upkeep that has no reader.
- A peer that sends an old name must not be silently corrupted.

## Considered Options

- Keep both lists, on the wire and in storage.
- Keep the storage list only.
- Keep no list: a former name is an unknown key on the wire and in storage.

## Decision Outcome

Chosen option: **keep no list: a former name is an unknown key on the wire and in storage**, because before 1.0 there is only one version of the protocol and of the store to support.

Before 1.0, Vultron supports exactly one protocol version and one storage version: the current ones.
A name that the protocol or a store once used, and no longer uses, has no special standing.

On the wire, such a key follows the ordinary unknown-key rule.
If it is a near miss of a declared spelling, the activity is refused as before.
Otherwise it is set aside and reported once at `INFO`, and the activity proceeds on its declared fields.
This changes what another implementation sees: a key that was refused by name is now set aside.

In storage, such a key is refused by the same rule that refuses any unknown key on a core type.
The refusal is the generic one; it does not say that a rename happened.
No old name is ever read through an alias.

This partly supersedes the retired-name clause of ADR-0099's inbound unknown-key detail, and ADR-0122's statement that the retired scalar consent keys are refused inbound by name.
The rest of both records stands.

Backward compatibility of the wire format is to be decided again at 1.0, when a second protocol version first becomes possible.

### Consequences

- Good, because one rule decides every unknown key, with no list to consult or keep current.
- Good, because a rename adds no entry anywhere: the model drops the field and the store is reset.
- Bad, because a peer that still sends a former name gets no refusal: its key is set aside, and the activity proceeds without it.
  The `INFO` report is the only signal.
- Bad, because an operator who reads a stored row written before a rename sees only the generic unknown-key error, not the rename that caused it.
- Neutral, because the near-miss refusal is unchanged, so a misspelling of a current field is still refused.

## Validation

The requirements in MV-11 of `specs/message-validation.yaml` carry the rule, each with a `verification:` clause.
MV-11-002 and MV-11-003 cite this record; MV-11-012 forbids a guard that refuses a former name by name.

## Pros and Cons of the Options

### Keep both lists, on the wire and in storage

- Good, because a sender and an operator each learn which field replaced the old one.
- Bad, because every rename adds entries to two lists that are read only between the rename and the next reset.
- Bad, because one kind of unknown key is refused while every other is set aside, which a peer cannot predict from the current schema.

### Keep the storage list only

- Good, because an operator still learns that a reset is needed.
- Neutral, because the wire side becomes uniform.
- Bad, because the storage list keeps the same upkeep for a store that is reset on every shape change before 1.0.

### Keep no list

- Good, because the wire and the store each follow one rule for every unknown key.
- Good, because a rename costs nothing beyond the change itself.
- Bad, because the refusals and reports no longer name the replacement.

## More Information

Issue #5573 carries the removal.
The maintainer made the decision on 2026-10-30, during the work on #4872.

Generated spec requirements: MV-11-002, MV-11-003, MV-11-012.
