---
stakeholder_type: [platform-developer, project-contributor]
level: 300
page_type: explanation
subject: protocol
description: >
  Why the CASE_MANAGER, not the report receiver, creates the case, and the
  ledger entries case creation commits.
---

# Case Initialization

{% include-markdown "../../includes/specification_governs.md" %}

This page explains why the [CASE_MANAGER](case_manager_and_ledger.md) creates every `VulnerabilityCase`, rather than the actor that received the report.
That report receiver — a Vendor, a Coordinator, or any other role — becomes the case's Case Owner, but it does not create the case.
How the proposal exchange works, step by step, is described in [Propose Case](../behavior_logic/use-cases/propose-case.md).
The page ends with the ledger entries that record a new case.

---

## Why the report receiver does not create the case

When an actor receives a vulnerability report, the simple approach is to send `Create(VulnerabilityCase)` to the case actor service's inbox.
That approach is wrong.

In ActivityStreams 2.0, `Create(X)` means "I created X."
A report receiver that sends `Create(VulnerabilityCase)` is claiming to be the authoritative creator of the case.
The report receiver is not.
The CASE_MANAGER is.
It is the single-writer authority for the canonical ledger, the only peer that appends to the case history.

Putting the report receiver as the `actor` on a `Create(VulnerabilityCase)` violates that meaning.
It assigns the wrong creator in every downstream replica.

The `CaseProposal` object solves this.
The report receiver *proposes* that the case actor service create the case.
The service decides whether to take the case.
If it does, it creates the case and sends `Create(VulnerabilityCase)` with itself as `actor`.
So the creator that every replica records is the participant that really does hold the case's history ([ADR-0041](../../adr/0041-caseactor-authoritative-case-initialization.md)).

---

## The entries case creation commits

A case comes into existence in one of two ways.
The CASE_MANAGER accepts a proposal and creates the case, or an actor creates a case for itself and is then both its Case Owner and its CASE_MANAGER.
Either way, the CASE_MANAGER commits the same ledger entries, in the same order, from the case file it has just written.
These are the entries [CLP-07-013](../../reference/specs/protocol.md#clp-07-013) requires for a new case, in the shapes the table shows.

| Order | Entry (`semanticType`) | What it carries |
|---|---|---|
| 1 | `create_case` | The genesis entry: the `Create(VulnerabilityCase)` the CASE_MANAGER sends, with the case's participants, reports and active embargo inline; it is the root of the case's hash chain |
| 2 | `create_embargo_event`, once per embargo the case's creation writes | `Create(EmbargoEvent)` with the embargo in full, its start and end times included |
| 3 | `add_report_to_case`, once per linked report | `Add(VulnerabilityReport)` with the report in full, and the report's `Offer` provenance when it is known |
| 4 | `create_case_participant`, once per participant record | `Create(CaseParticipant)` with the record in full as it was created, its first status included |
| 5 | `add_participant_status_to_participant`, once per later participant status | `Add(ParticipantStatus)`, targeting the participant record in full |
| 6 | `add_case_status_to_case`, once per case status | `Add(CaseStatus)` with the status in full |

A case with no embargo has no `create_embargo_event` entry, and a case with no linked report has no `add_report_to_case` entry.
Participants are taken in roster order.
So a case created from a proposal has entries for the CASE_MANAGER, the Case Owner and the reporter.
A case that an actor creates for itself has one participant entry, for the creator.

Each commit sends its entry to the case's other participants, and a participant must hold the case before the first entry about it arrives ([CP-09-009](../../reference/specs/protocol.md#cp-09-009)).
The entries are committed after the `Create(VulnerabilityCase)` is queued, on both creation paths.
That queued `Create` is the genesis entry itself, so the activity the case's first participant receives is the one every ledger records ([CLP-07-011](../../reference/specs/protocol.md#clp-07-011)).
A ledger entry records a completed act, and a message is sent once it is in the sender's outbox ([SYNC-09-002](../../reference/specs/protocol.md#sync-09-002)).
When an actor creates a case for itself, it is the case's only participant, so the entries go to nobody.

Every entry is required ([CLP-07-013](../../reference/specs/protocol.md#clp-07-013)).
The first entry that fails to commit stops the sequence, so no later entry is committed out of order, and the creation is reported as failed.
On both paths the case, its records, the queued messages and the entries are written together, so an entry that fails removes all of them.
Delivery learns of the queued messages only after they are written, so it never sends an `Accept` or a `Create` for a case that was then removed.
A redelivered proposal then creates the case from the beginning.

---

## Where to go next

- [Propose Case](../behavior_logic/use-cases/propose-case.md) — the proposal exchange: what the proposal carries, where it is addressed, the admission decision, the steps on acceptance, and lost-reply recovery
- [Case Proposal Messages](../../reference/messages/case_proposal.md) — the `Create`, `Accept`, and `Reject` activities on the wire
- [The Case Model](case_model.md) — `VulnerabilityCase`, participants, and roles
- [Ownership Transfer](ownership_transfer.md) — how the `CASE_OWNER` role moves between participants
- [Case Authority, Trust, and Routing](case_authority_and_trust.md) — how the participants a case starts with learn to trust its CASE_MANAGER
- [ADR-0023](../../adr/0023-case-proposal-protocol.md) — decision record for the `CaseProposal` mechanism
- [ADR-0041](../../adr/0041-caseactor-authoritative-case-initialization.md) — CaseActor-authoritative case initialization
- [ADR-0045](../../adr/0045-create-vulnerability-case-field-assignment.md) — `context` vs `in_reply_to` field assignment
