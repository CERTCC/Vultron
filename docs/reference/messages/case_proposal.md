---
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: reference
subject: protocol
description: >
  The pre-case bootstrap exchange (ADR-0023).
---

# Case Proposal Messages

A *case proposal* is a pre-case bootstrap message flow described in [ADR-0023](../../adr/0023-case-proposal-protocol.md).
It allows the **report receiver** — the actor that received the `Offer(VulnerabilityReport)`, whether a Vendor, a Coordinator, or any other role — to request case initialization from a case-actor service **before a case exists**.
The report receiver is the proposer, and if the case-actor service accepts the proposal, it becomes the case's Case Owner (CP-01-003, CP-09-001).
No case URI is in scope; the proposal itself is the shared object.

The flow is: `Create(CaseProposal)` → service accepts or rejects (`Accept(CaseProposal)` / `Reject(CaseProposal)`).
On acceptance the service proceeds to `Create(VulnerabilityCase)` separately (CP-05-003).

These messages have no formal-protocol shorthand (see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

## Occasions

{% include-markdown "./_occasions/lookup-case_proposal.md" %}

{% include-markdown "./_occasions/sections/create-case-proposal.md" %}

The proposal names the `Offer(VulnerabilityReport)` that brought the report in its `inReplyTo`, and nowhere else (CP-01-007).
When the report receiver still holds that Offer, `inReplyTo` carries it whole; otherwise it carries the Offer's id.
The Offer's sender is the inline Offer's `actor`, or the report's `attributedTo`.
That is how a Reporter's proposed embargo terms reach the case-actor (EP-04-004).

- **Triggering transition:** none — initiates the proposal sub-protocol.
- **Actor:** the `Create` goes to the service's inbox.
  Its `actor` is the proposing actor's full profile inline, and its `id` is the proposal's `attributedTo`.
  The profile carries the proposer's `embargoPolicy` when it has published one, which is the Case Owner's actor default (EP-04-003); the case-actor reads the default from that profile alone (CP-01-016).
  An `actor` that is the proposer's bare URI is accepted too: the case-actor fetches the profile from the proposer before it processes the proposal (CP-01-009, AKM-05-007).
  It uses that profile for that proposal alone, and refuses the proposal if the fetch fails.
  The case-actor refuses an `actor` that is a Link, an untyped or non-actor object, or one naming another actor, at the parse edge (CP-01-015).
- **Case roles:** the proposal's `proposerCaseRoles` lists the Coordinated Vulnerability Disclosure (CVD) roles the proposer holds in a case it owns, taken from its own configuration (CP-01-011, CP-01-013).
  The case-actor seats the proposer with those roles plus `CASE_OWNER`, and refuses a proposal that claims `CASE_MANAGER` (CP-01-012, [ADR-0133](../../adr/0133-the-report-receiver-states-its-case-roles-on-the-case-proposal.md)).
- **Case inputs:** the proposal may carry `caseInputs`, the starting content the proposer states for the case (CP-01-022).
  Its fields are `name`, `summary`, `exploitPublic` (X), `attacksObserved` (A), `proposedItems`, `referenceLinks` and `disclosureDate`.
  Each entry in `proposedItems` is a vulnerability item with no `id` of its own: its `ids`, `name`, `vulNotes` and `referenceLinks`.
  Each entry in `referenceLinks` is an AS2 `Link` to the referenced resource, and the Link's `name` becomes the case reference's name.
  `disclosureDate` is the earliest CSAF `vulnerabilities[].disclosure_date`, as the document states it.
  No field states whether the vulnerability is public (CP-01-023).
- **When the case-actor reads the CSAF document:** `caseInputs` is all or nothing.
  When the proposal carries it, the case-actor builds a new case from it and reads no CSAF document on the carried Offer (CP-01-024).
  An empty `proposedItems` list, or a false `exploitPublic` or `attacksObserved`, stays so, even when the document states otherwise.
  When the proposal carries no `caseInputs`, the case-actor fills the case inputs from the CSAF document on the carried Offer's report (CP-01-025, CSAF-02-001).
- **The disclosure date:** the case-actor judges the date when it creates the case.
  A date no later than that instant makes the case public, and the case starts with no embargo (CSAF-03-003, EP-04-020).
  A later date is the Reporter's proposed embargo end, unless the Offer carries a `proposedEmbargo`, which wins.
  That proposed end is then weighed against the Case Owner's actor default, and the shorter one is used (CSAF-03-001, EP-04-003).
- **Spec:** CP-01-010, CP-01-011, CP-01-012, CP-01-013, CP-01-022, CP-01-023, CP-01-024, CP-01-025, CP-03-001, CP-04-001.
- **Example artifact:** [create_case_proposal.json](../examples/create_case_proposal.json).

{% include-markdown "./_occasions/sections/accept-case-proposal.md" %}

- **Triggering transition:** none — response to a proposal, not a state machine event.
- **What follows:** `Create(VulnerabilityCase)` follows separately (CP-05-003).
  The service, as CASE_MANAGER, is that `Create`'s `actor`.
  The case's `attributedTo` is the proposing actor, who becomes the Case Owner — not the service (CP-09-001).
- **Spec:** CP-03-002, CP-05-003.
- **Example artifact:** [accept_case_proposal.json](../examples/accept_case_proposal.json).

{% include-markdown "./_occasions/sections/reject-case-proposal.md" %}

- **Triggering transition:** none — response to a proposal.
- **What follows:** the proposing actor may revise and resubmit (CP-05-004).
- **Spec:** CP-03-003, CP-05-004.
- **Example artifact:** [reject_case_proposal.json](../examples/reject_case_proposal.json).
