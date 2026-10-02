---
stakeholder_type: [platform-developer, project-contributor]
level: 300
description: >
  Why the CASE_MANAGER, not the report receiver, creates the case.
---

# Case Initialization

This page explains why the [CASE_MANAGER](case_manager_and_ledger.md) creates every `VulnerabilityCase`, rather than the actor that received the report.
That report receiver — a Vendor, a Coordinator, or any other role — becomes the case's Case Owner, but it does not create the case.
How the proposal exchange works, step by step, is described in [Propose Case](../behavior_logic/use-cases/propose-case.md).

---

## Why the report receiver does not create the case

When an actor receives a vulnerability report, the simple approach is to send `Create(VulnerabilityCase)` to the case actor service's inbox.
That approach is wrong.

In ActivityStreams 2.0, `Create(X)` means "I created X."
A report receiver that sends `Create(VulnerabilityCase)` is claiming to be the authoritative creator of the case.
The report receiver is not.
The CASE_MANAGER is — it is the single-writer authority for the canonical ledger, the only peer that appends to the case history.
Putting the report receiver as the `actor` on a `Create(VulnerabilityCase)` violates that meaning.
It assigns the wrong creator in every downstream replica.

The `CaseProposal` object solves this.
The report receiver *proposes* that the case actor service create the case.
The service decides whether to take the case.
If it does, it creates the case and sends `Create(VulnerabilityCase)` with itself as `actor`, so the creator every replica records is the participant that really does hold the case's history ([ADR-0041](../../adr/0041-caseactor-authoritative-case-initialization.md)).

---

## Where to go next

- [Propose Case](../behavior_logic/use-cases/propose-case.md) — the proposal exchange: what the proposal carries and where it is addressed, the admission decision, what the service does on acceptance, and how a lost reply is recovered
- [Case Proposal Messages](../../reference/messages/case_proposal.md) — the `Create`, `Accept`, and `Reject` activities on the wire
- [The Case Model](case_model.md) — `VulnerabilityCase`, participants, and roles
- [Ownership Transfer](ownership_transfer.md) — how the `CASE_OWNER` role moves between participants
- [ADR-0023](../../adr/0023-case-proposal-protocol.md) — decision record for the `CaseProposal` mechanism
- [ADR-0041](../../adr/0041-caseactor-authoritative-case-initialization.md) — CaseActor-authoritative case initialization
- [ADR-0045](../../adr/0045-create-vulnerability-case-field-assignment.md) — `context` vs `in_reply_to` field assignment
