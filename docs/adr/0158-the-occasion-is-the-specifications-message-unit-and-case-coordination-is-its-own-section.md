---
status: proposed
date: 2026-10-23
created: 2026-10-23
updated: 2026-10-23
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0083, ADR-0128, ADR-0147; design interview of 2026-10-23
  on the Protocol Layers page of the Protocol Specification; issues #5146, #5147,
  #5148, #4901
informed: []
stakeholder_type: [project-contributor]
---

# The Occasion Is the Specification's Message Unit, and Case Coordination Is Its Own Normative Section

## Context and Problem Statement

The Protocol Specification's Protocol Layers page carries two kinds of material that do not belong together.

Its §4 Semantic Layer — Message Meanings is organized around the formal message set: the two-letter protocol shorthands (`RS`, `EP`, `CV`, …) grouped by state machine.
[ADR-0083](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) recorded that the formal set and the ActivityStreams 2.0 (AS2) wire vocabulary are deliberately different shapes, many-to-many, reconciled by a mapping.
[ADR-0128](0128-message-vocabulary-docs-are-projections-of-the-semantic-registry.md) then made the **occasion** — a situation in a case that a sender conveys with a particular wire activity — the unit the message reference documents, projected from the semantic registry.
The specification never said which of the two is the unit its normative message text is about.

The same page also holds the rules for how a case is coordinated: single-writer authority, the routing topology, the case-creation trust root, ledger replication and case delivery, and the split between a participant's claim and the case's canonical status.
Those rules are about the CASE_MANAGER role, not about message meanings or wire syntax, so they sat as subsections of §4 and §5 where a reader looking for the Case Manager's duties would not find them in one place.
Placing them there also invited the reading that Case Manager coordination is a property of one deployment shape (the reference implementation's dedicated Case Actor) rather than of the protocol.

Which unit does the specification's message text describe, and where do the Case Manager's coordination rules live?

## Decision Drivers

- Every case has a CASE_MANAGER from creation onward, whoever holds the role (CM-24-006). A rule about the role is protocol, whatever actor holds it.
- The reference implementation's dedicated Case Actor is one way to hold the role, not the only one; the specification must not read as if it were the only one.
- The message reference already documents occasions (ADR-0128). Two message units in two documents would drift.
- The formal message set is still the vocabulary of the state machine transition tables, so the shorthands cannot simply be deleted.
- Section numbers are cited across the documentation; a renumbering must be mechanical and checkable, not hand-edited.

## Considered Options

- Make the occasion the normative message unit, keep shorthands as cross-reference tags, and give Case Manager coordination its own normative section, renumbering the sections after it
- Keep the formal message set as the normative unit, and leave the coordination rules spread across §4 and §5
- Move the coordination rules into a separate informative "coordination profile" that describes the reference implementation's deployment

## Decision Outcome

Chosen option: "Make the occasion the normative message unit, keep shorthands as cross-reference tags, and give Case Manager coordination its own normative section, renumbering the sections after it", because it is the only option that matches what the protocol actually requires of every case and what the message reference already documents.

Three decisions follow.

**1. The occasion is the specification's normative message unit.**
A normative statement about a message is about an occasion: the sender's situation and the wire activity that conveys it.
A two-letter protocol shorthand is a cross-reference tag.
It names a message of the formal message set, which was a design model that the protocol realizes as occasions, and it remains the vocabulary of the transition tables of §6 Report Management (RM) State Machine through §9 Participant Embargo Consent (PEC) State Machine.
This refines ADR-0083's mapping: the mapping still reconciles the two vocabularies, and the occasion is the side the specification states rules on.

**2. Case Manager coordination is its own normative section.**
The CASE_MANAGER is a protocol role that every case has.
Its coordination rules form §10 Case Coordination, a plain normative section, not a coordination profile.
The dedicated Case Actor is an implementation choice of the reference implementation and appears in the specification only in an informative note.
Decentralized realizations, such as a ledger shared among peers, stay deliberately open, also in an informative note.

**3. The sections after it are renumbered.**
§10 Case Coordination is placed before Model Interactions and Cascade Rules, so the sections numbered §10 to §15 before this decision become §11 to §16, and the informative annexes heading moves from §16 to §17.
The renumbering is scripted: headings, heading anchors and section citations change together across `docs/`, `specs/`, `notes/`, `vultron/` and `test/`, and the section-citation test checks that each citation names the section its anchor lands on.
ADR bodies keep the numbers they were written with (ADR-0127).

### Consequences

- Good, because a reader finds every Case Manager duty in one section, stated about the role rather than about a deployment.
- Good, because the specification and the message reference describe the same message unit.
- Good, because the shorthands keep working as the transition tables' vocabulary and as stable tags for cross-references.
- Bad, because every outside citation of §10 to §16 by number now points one section early; citations by link anchor are updated, but a printed citation is not.
- Neutral, because §4 and §5 keep pointers to the moved material until the rewrite of those sections (#5148) recasts §4 around occasions.

## More Information

The plan for a Requirements Catalog body section after Conformance (ADR-0147, #4901) shifts with this renumbering: Conformance is now §13, so the catalog would be §14.
