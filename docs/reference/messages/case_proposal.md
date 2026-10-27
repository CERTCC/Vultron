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

When the report receiver still holds the `Offer(VulnerabilityReport)` that brought it the report, the proposal carries that Offer whole as `inReplyTo`, alongside the bare `offerId` and `offerActorId` provenance.
That is how a Reporter's proposed embargo terms reach the case-actor (EP-04-004).

- **Triggering transition:** none — initiates the proposal sub-protocol.
- **Actor:** the `Create` goes to the service's inbox.
  Its `actor` is the proposing actor's full profile inline, not a URI, and its `id` is the proposal's `attributedTo`.
  The profile carries the proposer's `embargoPolicy` when it has published one, which is the Case Owner's actor default (EP-04-003); the case-actor reads the default from that profile alone, and refuses an `actor` that is a bare URI, a Link, an untyped or non-actor object, or a profile naming another actor, at the parse edge (CP-01-010).
- **Case roles:** the proposal's `proposerCaseRoles` lists the Coordinated Vulnerability Disclosure (CVD) roles the proposer holds in a case it owns, taken from its own configuration (CP-01-011, CP-01-013).
  The case-actor seats the proposer with those roles plus `CASE_OWNER`, and refuses a proposal that claims `CASE_MANAGER` (CP-01-012, [ADR-0133](../../adr/0133-the-report-receiver-states-its-case-roles-on-the-case-proposal.md)).
- **Spec:** CP-01-010, CP-01-011, CP-01-012, CP-01-013, CP-03-001, CP-04-001.
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
