---
status: accepted-provisional
date: 2026-11-19
created: 2026-11-19
updated: 2026-11-20
revision: 1
deciders: Allen D. Householder
consulted: Claude Opus 5.5
informed: []
stakeholder_type: [project-contributor]
---

# Whether a Case Records Public Credit

## Context and Problem Statement

A CSAF document can name the people and organizations that receive public credit, in `document.acknowledgments` and `vulnerabilities[].acknowledgments`.
In the CSAF Vulnerability Report profile, a document with no acknowledgments has a meaning of its own: the discoverer does not want public credit.
A CSAF acknowledgments list cannot be empty, so the only way to give no credit is to leave the list out.
Vultron has no counterpart to either list.

The CSAF 2.1 crosswalk marked this gap as undecided (#5135).
Should a Vultron case record who wants public credit, so that a CSAF document projected from the case (#5134) can fill its acknowledgments?

Three facts frame the question.
A receiver already reads the acknowledgments of a CSAF document attached to a report, but keeps them for display only and sends them to no one ([ADR-0184](0184-a-csaf-document-travels-as-a-report-attachment-and-speaks-for-the-sender-only-at-the-first-report.md)).
The Finder role is retired, and the report content or a case note names the finder ([ADR-0078](0078-retire-finder-role.md)).
`CaseParticipant` has no field for credit.

## Decision Drivers

- Vultron is a coordination protocol.
  A case is a coordination record, and a CSAF document is a publication projected from it.
- Who receives public credit is decided when a document is published, not during coordination.
- Credit may belong to the case or to each vulnerability in it, and neither choice is clearly right.
- A free-text credit field that each participant writes about itself invites abuse.
  Every participant could put any string in it, and the case would carry it to every projection.
- Vultron does not write advisories.
  An advisory is made at the advisory Composer call-out point, by whatever plug-in fills it.
- In the CSAF Vulnerability Report profile, a document with no acknowledgments makes a statement.
  A projection cannot leave acknowledgments out without saying that someone refused credit.

## Considered Options

1. **The case records no credit.**
   Credit is chosen by whoever publishes a document from the case.
2. **Each participant states its own credit preference.**
   A participant says whether it wants public credit and the name to credit, and the case carries that statement to every participant.
3. **The case records the Reporter's wish only, from the first report.**
   The receiver takes the Reporter's credit wish from the report, for example from an attached CSAF document's acknowledgments, and no new message carries it.

## Decision Outcome

Chosen option: "The case records no credit", because public credit is a publication choice and Vultron coordinates; it does not publish.
The case may still name a finder in its report content or a case note, as ADR-0078 allows.
Those are text, and the protocol gives them no credit meaning.

### Consequences

- Good, because the protocol gains no field that a participant can fill with any string and push to every other participant.
- Good, because the decision does not have to choose between case-level and vulnerability-level credit.
- Good, because it keeps the line between a coordination record and a publication drawn from it.
- Bad, because a CSAF projection cannot fill acknowledgments from case data alone.
  It needs an input from outside the case, as the next section requires.

### What a projection does with acknowledgments

A CSAF projection takes its acknowledgments from its caller: a human, or the plug-in at a Composer call-out point.
It does not derive them from case data.
A projection of the Vulnerability Report profile leaves acknowledgments out only when its caller says no one is to be credited, because a document with no acknowledgments there means the discoverer does not want credit.

When a Composer plug-in writes a document that credits someone, Vultron handles that credit as part of the document.
It does not read the credit back into the case.

An implementation may default the caller's input to the participants that hold the `REPORTER` role.
That default is an implementation choice, not a protocol requirement.

## Validation

There is no code to check until the CSAF projection exists.
When it is planned (#5134), its requirements carry the rule of "What a projection does with acknowledgments", and its tests check that a projection with no credit input does not emit a Vulnerability Report profile document with no acknowledgments.

## Pros and Cons of the Options

### The case records no credit

- Good, because it adds no protocol surface.
- Good, because the publisher, who answers for the document, decides who it credits.
- Bad, because each publisher must find the credit decision outside the case.

### Each participant states its own credit preference

- Good, because only a participant can say whether it wants credit and under what name.
- Good, because every projection of the case would credit the same parties.
- Bad, because it adds a participant-written free-text field that the protocol carries to every participant, with no way to judge what it says.
- Bad, because it must decide whether credit is per case or per vulnerability.
- Bad, because a non-participant finder still needs another place to be named.

### The case records the Reporter's wish only, from the first report

- Good, because it adds no new message.
- Bad, because the receiver's reading of a CSAF attachment is its own judgment and is never sent to another actor (ADR-0184), so other participants would not share it.
- Bad, because it covers the Reporter only, and a Reporter that sends the report of another party is not the discoverer.

## More Information

Source: #5135.
The CSAF 2.1 crosswalk pages under `docs/reference/csaf_crosswalk/` record this decision for the acknowledgments row.
The CSAF projection is tracked by #5134.
