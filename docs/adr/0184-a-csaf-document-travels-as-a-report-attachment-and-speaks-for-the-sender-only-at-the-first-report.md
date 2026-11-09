---
status: accepted-provisional
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Idea #5131, Epic #5911; the CSAF 2.1 crosswalk pages; the CSAF 2.1
  draft (CSD04) and its Vulnerability Report profile
informed: []
stakeholder_type: [project-contributor]
---

# A CSAF Document Travels as a Report Attachment and Speaks for the Sender Only at the First Report

## Context and Problem Statement

The Common Security Advisory Framework (CSAF) 2.1 draft adds a Vulnerability Report profile, `csaf_vulnerability_report`, made for private exchange during Coordinated Vulnerability Disclosure (CVD).
CVD tools will send such documents to Vultron participants, and the [CSAF crosswalk](../reference/csaf_crosswalk/overview.md) expects them to travel inside a case.
Participants will also produce CSAF documents from their copies of a case and pass draft advisories around in CSAF, so CSAF documents will appear in a case for reasons other than reporting.

Four questions are open (Idea #5131):

1. Where in a Vultron message does a CSAF document go, and what tells a receiver that it is CSAF?
2. When may a receiver read the content of a CSAF document as the sender's statement about the case?
3. When a Vultron field and the CSAF document state a value for the same thing, which one counts?
4. What does a receiver do with a CSAF document it cannot read, or one that fails the CSAF schema?

## Decision Drivers

- A report stays usable by a receiver that does not read CSAF, and a report can carry other files.
- The message keeps the ActivityStreams 2.0 (AS2) shapes, in which `content` is a string.
- A document that describes a case must not change the case it describes.
- The case changes only through Vultron's own activities and fields.
- A broken attachment must not stop a real vulnerability report from being received.
- CSAF 2.1 is a draft that its Technical Committee can still change.

## Considered Options

For the carriage:

- The CSAF document as the report's own `content`, serialized to a string.
- The CSAF document as a JSON object in the report's `content`.
- The CSAF document as an attached `Document` object of the report, with the report's `content` kept as text.

For the identification:

- The media type `application/json`, with the document identifying itself.
- `application/json` with a `profile` parameter that names the CSAF schema.
- An unregistered media type, such as `application/csaf+json`.

For the occasion of reading:

- Read any CSAF document that arrives in a case.
- Read only a CSAF Vulnerability Report attached to the first offer of a report, before a case exists for it.

## Decision Outcome

Chosen options: **the attached `Document`**, **`application/json` with self-identification**, and **only at the first offer of a report**, because together they keep AS2 shapes, keep the report readable without CSAF, and keep every other CSAF document from rewriting a case.

The decision has five parts:

1. **Carriage.** A CSAF document travels as a `Document` in the `attachment` of a `VulnerabilityReport`, with the JSON text of the document as the `content` of that `Document`.
   The report's own `content` is human-readable text, and the report can carry other attachments beside the CSAF document.
2. **Identification.** The `Document` has the media type `application/json`, which the distribution feeds of the CSAF draft also use.
   A receiver recognizes CSAF 2.1 from the document itself, by its `$schema` and `document.csaf_version` values, and reads the profile from `document.category`.
3. **One occasion for reading.** A receiver may treat a CSAF document as the sender's statement only when the document has the category `csaf_vulnerability_report` and is attached to an `Offer(VulnerabilityReport)` whose report belongs to no case at the receiver.
   Then the document can fill the inputs of the case that the receiver creates.
   A CSAF document anywhere else, such as on a note, on a later report, or in a vulnerability record, is a result of the case and changes no case data.
4. **Explicit fields win.** A sender may fill the Vultron fields of the report and the offer as it chooses, and it should make them agree with the document it attaches.
   A receiver starts from those fields and may fill only what they leave unstated from the document.
   A field that the document omits states nothing, and neither does a default that the CSAF schema declares.
5. **Strict sender, lenient receiver.** A sender should not attach a document that fails the CSAF 2.1 schema.
   A receiver never refuses a report because of its CSAF attachment, and it reads what it can.

The mapping from CSAF fields to case inputs, the receiver's local record of what it read, and how the codebase follows the changing draft are current policy, and they live in the specification that cites this decision.

### Consequences

- Good, because a report with no CSAF attachment, one with only a CSAF attachment, and one with several files all have the same shape.
- Good, because a receiver that does not read CSAF still has the report's text.
- Good, because the attachment sits inside the signed activity and inside the copy that the case ledger records.
- Good, because a projection or a draft advisory that circulates in a case cannot change the case.
- Good, because a Vultron field and a CSAF value never compete: the Vultron field always counts.
- Bad, because a sender that has only a CSAF document must still write at least a line of report text.
- Bad, because `application/json` alone does not tell a receiver that an attachment is CSAF until it reads the document.
- Bad, because a CSAF document that arrives after the case exists can only be read by a human, even when it carries news, such as a later exploitation report.
  Such news reaches the case through the Vultron activity that reports it.

## Validation

A requirement for each part of the decision carries a test marker.
Each marker is a strict expected failure until its behavior is built.

## Pros and Cons of the Options

### The CSAF document as the report's own `content`

- Good, because it needs no new object.
- Bad, because the report then has no text for a reader that does not read CSAF.
- Bad, because the report cannot carry other files in the same way.

### The CSAF document as a JSON object in `content`

- Good, because the message is easier for a person to read.
- Bad, because AS2 defines `content` as a string, so the shape is not AS2.

### The CSAF document as an attached `Document`

- Good, because it is the way ActivityPub servers attach files to a note: each attachment names its own format.
- Good, because the report keeps its text and can carry other files.
- Neutral, because a receiver must look in the attachments to find the document.

### A `profile` parameter or an unregistered media type

- Good, because the format is visible without reading the document.
- Bad, because `application/json` defines no parameters, and no other tool knows an invented type.
- Bad, because neither one helps a receiver that must read the document to identify it in any case.

### Read any CSAF document that arrives in a case

- Good, because news in a later document could update the case automatically.
- Bad, because projections and draft advisories describe the case, so reading them back lets a description rewrite what it describes.

## More Information

The crosswalk [proposals](../reference/csaf_crosswalk/proposals.md) include a request to the CSAF Technical Committee to register a media type for CSAF documents.
If the committee registers one, the identification part of this decision can change without changing the others.

Producing a CSAF document from a case is planned separately (Idea #5134).

Generated spec requirements: `csaf-report-content.yaml` CSAF-01 through CSAF-03.
