---
status: proposed
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0114, ADR-0193, ADR-0198;
  specs/case-management.yaml CM-11, CM-17; specs/message-validation.yaml MV-10;
  notes/as2-vocabulary-alignment.md; issue #6244
informed: []
partially_supersedes:
  - 0114-joining-a-case-stub-invite-inert-participant.md
stakeholder_type: [project-contributor]
---

# Invites Use AS2's Slots, and the Stub Is the Case's Preview

## Context and Problem Statement

A case Invite is `Invite(Actor)[target=VulnerabilityCase]`, or `[target=VulnerabilityCaseStub]` for the stub Invite.
ActivityStreams 2.0 puts what one is invited to in `object` and the invitee in `target` ("Sally invited John and Lisa to a party"), so a generic reader takes the case as the invitee.
The embargo Invite names its invitee only in `to`.

The stub is its own object, with its own type and id, pointing up to the case through a Vultron `caseId` (ADR-0114).
A typed reference can now carry a `preview` of the object it names (ADR-0198), which is what the stub is: a limited view of the case for an invitee not yet entitled to it.

Once the stub becomes the case's preview, both case Invites name an object of type `VulnerabilityCase`, so the type in `target` no longer tells them apart.
The two Invites oblige different acts: an invitee answers a stub Invite from the preview alone, and is not entitled to fetch the case; the CASE_MANAGER answers an accepted stub Invite by sending the full case.

How do the Invites use AS2's slots, and how does a receiver tell the stub Invite from the full-case Invite?

## Decision Drivers

- A slot means what AS2 says it means, so a generic reader reads the Invite correctly.
- The case is named by its own id, with no stand-in object pointing up to it.
- A preview is a limited view, not the object (ADR-0193, ADR-0198).
- An invitee does not receive case content before it joins (ADR-0114).

## Considered Options

- Tell them apart by the object's form: a typed reference carrying a preview, or the whole case
- The stub keeps its own type, and only the slots change
- The stub Invite is a Vultron subtype of Invite

## Decision Outcome

Chosen option: "Tell them apart by the object's form", because it is the only option in which the stub is the case's own preview and nothing stands in for the case.

### Invites put the invitee in target

A case Invite is `Invite(<case>)[target=<invitee>]`.
An embargo Invite is `Invite(EmbargoEvent)[target=<invitee>]`, gaining the `target` it lacks.

### The stub Invite's object is a previewed reference to the case

The stub Invite's object is a typed reference to the case, `{id, type, preview}`, whose `preview` carries what the stub carries today: a summary and, while one is active, the embargo terms.
The full-case Invite's object is the whole case.
The stub's own type, its own id and its `caseId` go.

### A receiver reads the form as received

A pattern can require its object to be a typed reference that carries a preview, or a whole object, and the two case Invites, with every answer to them, are told apart that way.
The form is read as the Invite was received: a lookup of the objects a receiver holds does not expand a reference that carries a preview into the object it names, and a receiver does not fetch the object such a reference names.
A preview is not the case: no receiver seeds or updates a case replica from a reference that carries a preview.

### Consequences

- Good, because a generic reader sees who is invited to what, and the stub names the case by the case's own id.
- Good, because the stand-in stub object and its `caseId` leave the wire.
- Bad, because the pattern matcher gains a constraint on an object's form, and lookup gains a case it does not expand.
- Bad, because every join-flow message and every embargo Invite changes form, with their patterns, examples and message reference. Pre-1.0, the old forms are replaced outright.

## Validation

- A test asserts that a stub Invite and a full-case Invite for the same case match different patterns, as do the Accept, Reject, TentativeReject and Undo of each.
- A test asserts that a CASE_MANAGER holding the case classifies an `Accept` of the stub Invite as the stub answer, and that an invitee answering a stub Invite fetches nothing.
- A test asserts that a reference carrying a preview does not seed or update a case replica.
- A test asserts that an embargo Invite names its invitee in `target`.

## Pros and Cons of the Options

### Tell them apart by the object's form

- Good, because the stub is what ADR-0198 anticipated, a preview of a typed case reference, with no second shape rule.
- Bad, because it adds a form constraint to patterns and a no-expansion case to lookup.

### The stub keeps its own type, and only the slots change

- Good, because patterns keep discriminating by type, and lookup and fetch do not change.
- Bad, because the stub stays a Vultron stand-in that names the case through `caseId`, and a generic reader does not see it as the case.

### The stub Invite is a Vultron subtype of Invite

- Good, because patterns discriminate on the activity's type, as for `Refuse`.
- Bad, because it adds a verb for what is an Invite to a case.
- Bad, because it still needs the no-expansion and no-fetch rule for the previewed reference.

## More Information

This record partially supersedes ADR-0114 in "the stub is its own type and its own object"; the inert participant the Invite creates, the stub's contents and the rest of ADR-0114 stand.
It defines the case's preview, which ADR-0198 leaves to the work that defines each type's preview.
