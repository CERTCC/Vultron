---
stakeholder_type: [platform-developer, project-contributor]
level: 400
---

# Case Proposal Messages

A *case proposal* is a pre-case bootstrap message flow described in
[ADR-0023](../../adr/0023-case-proposal-protocol.md). It allows an actor
(typically a finder or coordinator) to request case initialisation from a
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

- **Protocol role:** An actor submits a `CaseProposal` to a case-actor
  service requesting that a case be opened for the attached report (CP-04-001).
- **Triggering transition:** none — initiates the proposal sub-protocol.
- **Wire activity:** `Create(CaseProposal)` sent to the service's inbox.
- **Spec:** CP-03-001, CP-04-001.
- **Example artifact:** [create_case_proposal.json](../examples/create_case_proposal.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case_proposal, json2md

print(json2md(create_case_proposal()))
```

---

## Accept Case Proposal

- **Protocol role:** The case-actor service signals acceptance of the
  proposal. `Create(VulnerabilityCase)` follows separately (CP-05-003).
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
