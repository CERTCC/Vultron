---
status: proposed
date: 2026-11-19
created: 2026-11-19
updated: 2026-11-19
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# A CSAF Projection Is a Case Preview Cut by Its Call Site's Profile, Then Rendered to CSAF

## Context and Problem Statement

A participant can produce a CSAF 2.1 document from its copy of a case.
This record calls such a document a **projection**.
A projection can occur at publication, as the output of the draft step of the publication pipeline ([ADR-0030](0030-publish-leaf-draft-review-submit-pipeline.md)).
A projection can also occur during coordination, as a bridge to a party that does not use Vultron.
A projection takes case information out of the protocol, so it must not contain information that its recipient is not entitled to see.
A projection also states the ledger position that it shows, because the case continues to change after the projection.

[ADR-0217](0217-a-case-preview-is-cut-from-the-case-field-by-field-inside-an-envelope-the-protocol-sets.md) cuts a case preview from the case field by field, with four operations: include, substitute, redact and omit.
A profile fixes one operation for each field, so the cut is mechanical.

**How does a participant produce a CSAF document from its case, and what decides what the document contains?**

## Decision Drivers

- A projection must not contain information that its recipient is not entitled to see.
- CSAF is one output format; other formats, such as a CVE record or a text advisory, can follow.
- The rule that withholds a value must not depend on the output format.
- A projection is a deliberate act of publication: it selects what it says.
- A reader must be able to tell which case snapshot a projection shows.
- A projection must pass the CSAF 2.1 schema that this codebase pins, and the CSAF mandatory test on its revision history.
- The same inputs must give the same document.
- A case records no public credit, so a projection takes its acknowledgments from its caller ([ADR-0218](0218-whether-a-case-records-public-credit.md)).
- The case holds no product data ([ADR-0187](0187-a-cases-vulnerabilities-are-csaf-shaped-items-that-participants-offer-and-the-case-manager-admits.md)).

## Considered Options

- A CSAF renderer that reads the case and decides what to leave out.
- A profile cut of the case, then a CSAF renderer that reads only the cut.
- A projection that copies a CSAF document that a reporter attached.

## Decision Outcome

Chosen option: "A profile cut of the case, then a CSAF renderer that reads only the cut", because the profile decides what may leave the case for every format, and the renderer decides only what CSAF can express.

### A projection is two transformations

A projection first cuts the case into a preview, with a profile in the form of ADR-0217.
The renderer then translates the preview into a CSAF document.
The renderer reads only the preview, and it does not read the case.

The profile decides what may leave the case.
The renderer selects what CSAF can express, and it can leave out more.
The renderer is never the only step that withholds a value: a value that the profile shows can appear in any format.

### The call site selects the profile

Each place that produces a projection uses one fixed profile.
The participant does not select a profile for each document.

| Call site | Profile | Shows |
|---|---|---|
| The draft step of the publication pipeline | Public | The facts of a public advisory |
| A request by the participant's operator for a document to give to a party outside Vultron | Joined | What a joined participant sees, without case bookkeeping |

A preview for a stub Invite uses the invitation profile of ADR-0217.
The joined profile is a different profile, because a recipient of a coordination projection needs the case details that an invitee does not get.

### The cut includes the ledger

A preview that is cut for rendering can carry case ledger entries.
This extends the preview of ADR-0217, which holds only case fields: the ledger list is the one preview field that is not a case field.
The profile applies the four operations to the ledger list as it applies them to other lists: it can keep only some entries.
A preview can therefore hold an incomplete ledger.
The profile also cuts the payload of each entry that it keeps, so an entry cannot carry a value that the profile withholds elsewhere.
The invitation profile omits the ledger.

The CSAF renderer makes `document.involvement` actions only from the ledger entries that have a CSAF meaning, one action for each act.
It derives each status value from the state at the ledger position of the preview.

### A redaction becomes an absence

CSAF has no redaction marker.
The renderer leaves a redacted field out of the document, as it leaves out an omitted field.
The document does not list what it leaves out, because a publication is not expected to state what it does not say.

### A projection is a pure function of its identity

A projection keeps no revision counter.
`document.tracking.id` comes from the case ID, a versioned profile name, the log index of the preview's ledger position, and a short digest of the acknowledgments when the caller supplies them.
The profile version changes when a change to a profile or to the renderer changes the output.
Every projection uses CSAF integer versioning with `document.tracking.version` `1`, and its revision history has one entry, numbered `1`.
Every date in the document is the commit time of the ledger entry at the preview's position, and no date comes from a clock.
One identifier therefore always gives the same document, and to make it again is to issue the same version again, not to make a revision.
A `document.references` entry of category `self` names the case and the hash of the entry at that position.

These versioning rules were rejected:

- A version from the log index fails the CSAF mandatory test on the revision history, because the history must start at 0 or 1 with no gap.
- A fixed identifier with version `1` gives one identifier and version to documents with different content.
- A full revision history from the ledger works only for a profile that carries the ledger.

### Acknowledgments come from the caller

A projection takes its acknowledgments from its caller, as ADR-0218 requires.
When the caller supplies none, the call site supplies the participants that hold the `REPORTER` role, from the case, as ADR-0218 permits.

### The document is CSAF Base until the case holds products

The CSAF Vulnerability Report and Security Advisory profiles require a product tree and product status.
The case has neither, so every call site produces a document of category `csaf_base`.
A projection does not copy a product tree from a document that a reporter attached.

### Consequences

- Good, because the profile alone decides what leaves the case, so a new output format cannot show a value that the profile withholds.
- Good, because each call site produces the same cut every time, without a judgment for each document.
- Good, because a reader can find the case snapshot from the identifier and the reference.
- Good, because the same inputs always give the same document.
- Bad, because a CSAF reader cannot tell a withheld value from a value that the case does not hold.
- Bad, because a CSAF Base document does not meet the expectations of a reader who wants a Vulnerability Report or a Security Advisory.
- Bad, because a CSAF reader does not see successive projections of a case as revisions of one document; the reader groups them by the case reference.

## Validation

A test confirms that a projection from each call site passes the pinned CSAF 2.1 schema.
A test confirms that a value that the profile withholds appears nowhere in the document.
A test confirms that the same inputs give an identical document.
A test confirms that a different log index, profile version or caller acknowledgments give a different `document.tracking.id`.

## Pros and Cons of the Options

### A CSAF renderer that reads the case and decides what to leave out

- Good, because it has one step.
- Bad, because each new output format must repeat the rules that withhold values.
- Bad, because an error in one renderer can send a withheld value out of the case.

### A profile cut of the case, then a CSAF renderer that reads only the cut

- Good, because the rule that withholds a value is in one place, for every format.
- Good, because it uses the profile model of ADR-0217 again.
- Neutral, because the preview must be able to hold ledger entries.

### A projection that copies a CSAF document that a reporter attached

- Good, because it can supply a product tree that the case does not hold.
- Bad, because it republishes a claim of the reporter as a statement of the participant that produces the projection.
- Bad, because it is available only when the report carries a CSAF document.

## More Information

Planned in [#5134](https://github.com/CERTCC/Vultron/issues/5134){:target="_blank"}.
The crosswalk overview describes projections in its section [A case can produce a CSAF document](../reference/csaf_crosswalk/overview.md#a-case-can-produce-a-csaf-document).
The rules for the profiles, the renderer and the call sites, and the requirement text that the implementation adds, are in `notes/csaf-projection.md`.
How a Traffic Light Protocol (TLP) label appears inside Vultron is a separate question ([#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"}).
