---
stakeholder_type: [platform-developer, project-contributor]
level: 400
description: >
  The pre-case bootstrap exchange (ADR-0023).
---

# Case Proposal Messages

A *case proposal* is a pre-case bootstrap message flow described in
[ADR-0023](../../adr/0023-case-proposal-protocol.md). It allows an actor
(typically a finder or coordinator) to request case initialization from a
case-actor service **before a case exists**. No case URI is in scope; the
proposal itself is the shared object.

The flow is: `Create(CaseProposal)` → service accepts or rejects
(`Accept(CaseProposal)` / `Reject(CaseProposal)`). On acceptance the service
proceeds to `Create(VulnerabilityCase)` separately (CP-05-003).

These messages have no formal-protocol shorthand (see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

print(render_page("case_proposal", heading=False))
```

---

## Create Case Proposal

When the vendor still holds the `Offer(VulnerabilityReport)` that brought it the report, the proposal carries that Offer whole as `inReplyTo`, alongside the bare `offerId` and `offerActorId` provenance.
That is how a Reporter's proposed embargo terms reach the case-actor (EP-04-004).

- **Protocol role:** An actor submits a `CaseProposal` to a case-actor
  service requesting that a case be opened for the attached report (CP-04-001).
- **Triggering transition:** none — initiates the proposal sub-protocol.
- **Wire activity:** `Create(CaseProposal)` sent to the service's inbox.
  Its `actor` is the proposing actor's full profile inline, not a URI, and its `id` is the proposal's `attributedTo`.
  The profile carries the proposer's `embargoPolicy` when it has published one, which is the Case Owner's actor default (EP-04-003); the case-actor reads the default from that profile alone, and refuses a bare-URI `actor` or a profile naming another actor at the parse edge (CP-01-010).
- **Spec:** CP-01-010, CP-03-001, CP-04-001.
- **Example artifact:** [create_case_proposal.json](../examples/create_case_proposal.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case_proposal, json2md

print(json2md(create_case_proposal()))
```

---

## Accept Case Proposal

- **Protocol role:** The case-actor service signals acceptance of the
  proposal. `Create(VulnerabilityCase)` follows separately (CP-05-003).
  The service, as CASE_MANAGER, is that `Create`'s `actor`.
  The case's `attributedTo` is the proposing actor, who becomes the Case Owner — not the service (CP-09-001).
- **Triggering transition:** none — response to a proposal, not a state
  machine event.
- **Wire activity:** `Accept(CaseProposal)` sent to the proposing actor's
  inbox.
- **Spec:** CP-03-002, CP-05-003.
- **Example artifact:** [accept_case_proposal.json](../examples/accept_case_proposal.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_case_proposal, json2md

print(json2md(accept_case_proposal()))
```

---

## Reject Case Proposal

- **Protocol role:** The case-actor service declines the proposal (CP-05-004).
  The proposing actor may revise and resubmit.
- **Triggering transition:** none — response to a proposal.
- **Wire activity:** `Reject(CaseProposal)` sent to the proposing actor's
  inbox.
- **Spec:** CP-03-003, CP-05-004.
- **Example artifact:** [reject_case_proposal.json](../examples/reject_case_proposal.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_proposal, json2md

print(json2md(reject_case_proposal()))
```
