---
status: proposed
date: 2026-10-20
created: 2026-10-20
updated: 2026-10-20
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0035, ADR-0107, ADR-0111;
  specs/case-ledger-processing.yaml CLP-10-017;
  specs/datalayer.yaml DL-06-001, DL-06-004, DL-06-006;
  specs/vocabulary-model.yaml VM-08-002
informed: []
partially_supersedes: 0035-core-activity-representation-and-envelope-reconstitution.md
stakeholder_type: [project-contributor]
---

# The Received Archive Is the Sealed Received Body, Read Through a Read-Only View Parsed on Load

## Context and Problem Statement

A receiver archives every activity it receives before it judges it (ADR-0111).
The archive is meant to hold the activity exactly as received, but what it holds is the core summary the semantic extractor builds from the activity.
That summary keeps only the fields core uses.
It drops `cc`, it drops `endTime` on every activity but one, and it drops any field the core model does not name.

Replies embed that summary.
An Accept of an embargo Invite, an answer to an ownership-transfer Offer, and a case proposal's inline report Offer each embed the activity they answer, whole, read from the archive.
A refusal notice embeds the same summary, taken from the event rather than the archive.
So each embeds the summary instead of what the sender sent, and the Invite a participant accepts has lost its RSVP deadline.
A field the summary drops is lost to every later reader, and nothing reports it.

The parser already seals the body that arrived, decoded and re-serialized before anything expands or validates it (VM-08-002), but nothing stores that sealed body.
It is not the request bytes: keys, key order and values are the sender's, while whitespace, number spelling and escapes are not (ADR-0107).
Once the ingress copy under the sender's id is gone (DL-06-006), the summary is the only copy the receiver holds.

Core also reads facts from received activities after they arrive.
A participant answering a full-case Invite reads the case and ledger position the Invite names.
An actor answering an ownership-transfer Offer reads the case it offers.
ADR-0035 forbids this: core learns what a message means only from core state recorded at delivery, never from a stored activity.
The code reads these facts anyway, from the archive, which that rule did not foresee.

## Decision Drivers

- A reply embeds the activity it answers as the sender sent it, every field included (Actor Knowledge Model, DL-06-004).
- What was received never changes after it arrives: the ledger hashes it and replicas copy it (ADR-0107).
- Core reads typed facts from an activity it received earlier, and those reads exist in the code today.
- A received activity is interpreted in one place, the semantic extractor (ARCH-03-001), so a later read cannot disagree with the delivery.
- An activity deferred for replay is processed the same way as on first delivery.

## Considered Options

- **A. Store the sealed body; parse it on load into a read-only core view.**
  The archive holds the received body exactly as the parser sealed it, and no summary.
  Each load runs the same parse and extraction the inbox ran at delivery.
  Core gets the read-only typed view the extractor builds, and a reply embeds the parsed activity.
- **B. Store both the sealed body and the summary.**
  Replies embed the sealed body; core keeps reading the stored summary.
- **C. Store the summary only, and name the fields it keeps.**
  Narrow "exactly as received" to the summary, and pin its fields with a test.
- **D. Store the sealed body; core reads the parsed wire activity directly.**
  One model, every field visible to core, with a read-only exception to the rule that core does not import the wire layer.

## Decision Outcome

Chosen option: **A**, because it is the only option that keeps one stored copy of what arrived, gives replies every field the sender sent, and gives core the same typed view it saw at delivery.

The archive is the received body as the parser sealed it.
Nothing derived from it is stored beside it, so no stored copy can drift from what arrived.
This replaces ADR-0111's plan to persist the sealed body beside the archived summary: the sealed body is the archive, not an addition to it.
A load parses the body fresh, through the same path the inbox used, so the view a later reader gets equals the view the delivery got.
The view is read-only: an attempt to change it, or any object nested in it, fails.
Core changes only its own records, which effect nodes already write from the event.

Core may read a received activity's facts from this view, and only from this view.
This changes four of ADR-0035's five decision details.
Its second detail forbade core reading a stored activity for its meaning, and its first forbade core reconstructing a fact by re-reading one later; both now admit reads of this view.
Its fourth detail treated the stored payload as opaque, read only to embed it in a reply; the reply seam now parses the sealed body, and core reads the view the parse yields.
Its fifth detail named the reply seam as the only sanctioned activity read; reads of this view are sanctioned too, and every other core read of a stored activity still leaves the ratchet.
Its third detail stands: a reply correlates with the message it answers through a core relationship, not by re-reading that message (DL-06-003).
Separately, core still never reads a wire row stored under a sender's id (DL-06-006).

ADR-0035 rejected copying every AS2 activity into a matching core class.
This decision does not do that: the view is the extractor's existing output, built by the one interpretation site, not a second model of the wire format.

A deferred activity is held as its sealed body too.
Its replay parses that body, so it carries the evidence of its own delivery and is processed as on first delivery.
A resend under an id the receiver already holds still carries no evidence, since its body is not the one archived (VM-08-002).

### Consequences

- Good, because a reply embeds the activity as the sender sent it, so an embargo Invite's RSVP deadline, its `cc`, and any field the core model does not name survive into the Accept.
- Good, because the archive and the ledger's received snapshot (ADR-0107) are the same sealed body, so a replica and the receiver hold one account of what arrived.
- Good, because the core readers that already read archived activities become sanctioned reads, through one path, rather than a loophole.
- Bad, because every load parses the body again, which costs more than reading a stored summary.
- Bad, because an activity that reaches the archive with no body to store is a wiring fault, so test fixtures that build events by hand must supply one.
- Bad, because a read-only view of mutable core classes must freeze nested objects too, which a class-level setting does not do.

## Validation

- A test delivers an embargo Invite carrying `endTime`, a `cc`, and a field the core model does not name, and asserts the participant's Accept embeds all three unchanged.
- A test asserts the archive holds exactly the body the parser sealed.
- A test asserts that changing the loaded view, or an object nested in it, fails, and that the next load is unchanged.
- A test replays a deferred activity and asserts it is processed with the same evidence as its first delivery.

## Pros and Cons of the Options

### A. Store the sealed body; parse it on load into a read-only core view

- Good, because one stored copy serves both replies and core reads.
- Good, because core readers see the same view they would have seen at delivery.
- Bad, because each load reparses.

### B. Store both the sealed body and the summary

- Good, because core reads stay as cheap as today.
- Bad, because two stored copies of one delivery can disagree, and a fix to the extractor leaves every stored summary stale.

### C. Store the summary only, and name the fields it keeps

- Good, because it is the smallest change.
- Bad, because replies stay unfaithful, so DL-06-004 stays unmet.
- Bad, because every field a later need discovers is already lost for every activity archived before.

### D. Store the sealed body; core reads the parsed wire activity directly

- Good, because there is one model, and core sees every field.
- Bad, because core readers are rewritten against wire classes, and the wire format becomes something core code depends on.

## More Information

Source: #4910.
Related: ADR-0107 (the ledger records the received body verbatim), ADR-0111 (intake archives what arrived first), ADR-0035 (partially superseded here).
