---
status: accepted-provisional
date: 2026-11-19
created: 2026-11-19
updated: 2026-11-19
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# A Case Preview Is Cut From the Case Field by Field, Inside an Envelope the Protocol Sets

## Context and Problem Statement

An actor invited to a case decides whether to join from the case's preview alone, the limited view a stub Invite carries.
The rules for that preview list its exact contents: an identity, a summary and, while an embargo is in force, the embargo terms.
A `Redacted` marker stands in a preview's field for a value withheld from the recipient (ADR-0193), so it needs fields to stand in, and the fixed list leaves none.
The list also leaves out facts an invitee needs to decide: who runs the case, and which vulnerability it is about.

**What does a case preview show, withhold or leave out, and who decides it: the protocol, or the sender?**

## Decision Drivers

- An invitee joins a case only if it can tell who runs it, which vulnerability it concerns, how urgent it is, and what embargo it would be bound by.
- Beyond what an invitee needs to decide, what a case reveals before the invitee has agreed to its embargo is the sender's judgment, not the protocol's.
- A redaction tells the recipient that a value exists, and that existence can itself be the sensitive fact.
- This implementation makes the same cut for every invitation, without a judgment per invite.
- A field added to the case later reaches no preview until someone decides how a preview treats it.
- A preview is never read as the case (ADR-0205).

## Considered Options

- A fixed list of what a preview carries.
- A fixed list of contents, plus a list per preview type of the fields that may carry the marker.
- A per-field profile of operations, where the protocol sets what is permitted and the implementation chooses within it.

## Decision Outcome

Chosen option: "A per-field profile of operations, where the protocol sets what is permitted and the implementation chooses within it", because it covers every combination of show and withhold for every field, leaves the sender's judgment with the sender, and still makes this implementation's cut mechanical.

### A preview is a loose form of the case

A case preview has the case's fields, under the case's names, and every one of them is optional.
Any field may hold a `Redacted` marker, and a nested object takes its own loose form: a vulnerability item with only its identifiers is a loose vulnerability item.
A value the case derives from its fields is not a field: the preview carries the field it derives from, reduced.
The embargo in force travels as the case's embargo register cut to its in-force entry, as the case's status history is cut to its current status.
A preview keeps its own identity; the case reference that carries it names the case.

### Each field is cut by one of four operations

A sender cuts a preview from the full case, applying one operation to each field:

- **include**: the case's value, as held;
- **substitute**: a value the sender chooses for the preview, either a replacement, such as a less revealing summary, or a reduction of the held value, such as only the latest status;
- **redact**: the `Redacted` marker;
- **omit**: no value.

A held value the sender does not show is redacted, so the recipient can tell a withheld value from a missing one.
Where the value's existence is itself the sensitive fact, the sender may omit it instead.
A field the case holds no value for is omitted or substituted, and is not redacted: a marker would claim a value that does not exist.

### The protocol sets the envelope

The protocol permits every operation on every field unless a stated reason forbids it.
For a preview carried by a stub Invite, the reasons are these:

- The invitee needs readable context, the Case Owner, and, while an embargo is in force, the terms and state of the embargo it would be bound by, so these are shown: included or substituted, not redacted or omitted.
  An owner shown under an alias is a substitution.
- An open embargo revision reaches the invitee only after it joins, so it is omitted.
- The case's bookkeeping, such as its ledger position and indexes, means nothing outside the case, so it is omitted.

Everything else in a preview is the sender's choice.
A receiver refuses a preview that lacks a shown item, or marks one, and a marker outside a preview.

### The implementation chooses within the envelope

This implementation fixes one operation for each field in a profile, so a preview is a mechanical transformation of the case.
The profile names a permitted operation for every case field, so a field added to the case cannot reach a preview unclassified.

### The sender keeps a withheld value out of its marker

A marker that carries the value it stands for is the sender's fault.
A receiver handles a marker's extra keys as it handles any unrecognized key.

### Consequences

- Good, because an invitee can see who runs the case, which vulnerability it concerns, and its public and embargo state, while the case's details stay withheld.
- Good, because the protocol constrains senders only where a reason is stated, so another conforming sender can show more or less than this implementation does.
- Good, because the marker needs no list of fields per preview type: any field of a preview may carry it.
- Good, because this implementation's cut needs no judgment per invitation, and a new case field fails a check until the profile classifies it.
- Bad, because a receiver must accept a preview that shows more than this implementation would, up to a whole report.
- Bad, because every nested type a preview carries needs a loose form, and the loose and full forms of a type must be kept in step.

## Validation

A test confirms that the profile names a permitted operation for every case field, and that every preview field is a field of the case.
A test confirms that the preview cut from each valid case is a valid preview.
A receiver test confirms that a stub Invite whose preview lacks or marks a shown item is refused, and that a marker in any other field of a preview parses as the marker.

## Pros and Cons of the Options

### A fixed list of what a preview carries

- Good, because a receiver checks one shape.
- Bad, because it leaves no field for a marker, so a recipient cannot tell a withheld value from a missing one.
- Bad, because it leaves out the Case Owner and the vulnerability's identifiers, which an invitee needs to decide.
- Bad, because the protocol, not the sender, decides everything a sender may reveal.

### A fixed list of contents, plus a per-type list of fields that may carry the marker

- Good, because each preview type states exactly where a marker may stand.
- Bad, because each list is a judgment made again for every preview type, with nothing to say what a field not on it means.
- Bad, because it still fixes the shown contents for every sender.

### A per-field profile of operations, inside a protocol envelope

- Good, because four operations on each field cover every combination of show and withhold.
- Good, because each constraint the protocol places on a sender cites its reason.
- Neutral, because it separates two layers, the envelope and an implementation's choices, that a reader must keep apart.

## More Information

Planned in #6641; the marker is ADR-0193, the preview's place in the stub Invite is ADR-0205, and anonymity by alias is #2562.
The field-by-field profile, and the requirement changes this decision implies, are in `notes/selective-disclosure.md`.
