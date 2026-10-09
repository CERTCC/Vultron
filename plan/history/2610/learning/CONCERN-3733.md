---
source: CONCERN-3733
timestamp: '2026-10-01T20:23:28.232547+00:00'
title: Received handlers apply roster, ownership, and proposal assertions without
  checking the sender's authority
type: learning
---

## Concern

Several received-side handlers apply an inbound assertion without checking that the
sender is entitled to make it. Found during #2255, while classifying every received
handler exit as applied, skipped, deferred, or refused: these sites have no
authorization failure to classify, because no check exists.

| Handler | Missing check | Effect today |
|---|---|---|
| `AcceptCaseOwnershipTransferReceivedUseCase` (`received/actor/ownership.py`) | a pending ownership-transfer Offer names this sender as transferee | any actor can claim case ownership |
| `AcceptInviteActorToCaseReceivedUseCase` (`received/actor/invite.py`) | an Invite exists and the sender is its invitee | an uninvited actor can add itself |
| `AddCaseParticipantToCaseReceivedUseCase` / `RemoveCaseParticipantFromCaseReceivedUseCase` (`received/case_participant.py`) | the sender holds the authority to change the roster | any actor can add or remove participants |
| `AcceptCaseProposalReceivedUseCase` / `RejectCaseProposalReceivedUseCase` (`received/case_proposal.py`) | the sender is the proposal's addressee | `trusted_case_actor_id` can be overwritten by any sender |
| `AcceptOfferCaseParticipantReceivedUseCase` (`received/actor/offer_case_participant.py`) | the sender is the Case Owner | a non-owner can accept a recommendation |
| `RemoveNoteFromCaseReceivedUseCase`, `AddReportToCaseReceivedUseCase` | sender authorization of any kind | unrestricted |
| `RejectLedgerEntryReceivedUseCase` (`received/sync.py`) | the rejecting peer is a participant | any actor can drive replication-state changes |

## Why it matters

Each is a place a non-participant or wrong participant can change another actor's
replica. Once #2255 lands, a check added at these sites has a typed channel to report
through: `HandlerResult.refused("<reason>")` reaches `InboxOutcome` as `rejected`.

## Open questions

- Which of these does the protocol specify an authority for (CM-21, CM-11, CP-06,
  PCR-08), and which need a spec entry first?
- Is a per-handler check right, or does this belong in one pre-dispatch authorization
  seam?

**Resolved**: 2026-10-01 — implementation tracked in #4069 (shared sender-entitlement module, per-use-case declaration and ratchet), #4070 (ownership-transfer Accept), #4071 (stub-Invite reply), #4072 (case-proposal reply), #4073 (recommendation reply), #4074 (Remove(Note) and Add(Report, Case)), #4075 (Reject(CaseLedgerEntry)). The Add/Remove(CaseParticipant) row is owned by #2257, which also records whether acting on a case needs an active participant or only a roster record.

Decisions: a guard in each handler, not one check before dispatch; the guard is declared once per received use case and composed by the receive-tree factory from one shared module; seven existing near-duplicate sender checks merge into it; a ratchet over `SEMANTIC_REGISTRY` makes the remaining gap an exemption list. Re-verification found the Invite row worse than described: the CASE_MANAGER takes roles from the Invite copy embedded in the Accept and needs no recorded Invite. The note claiming that row was covered by #4048 and #4049 was wrong.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4068>.
Spec: `specs/handler-protocol.yaml` (HP-01-006, HP-01-007), `specs/case-management.yaml` (CM-11-017, CM-16-019, CM-21-011, CM-30), `specs/case-proposal.yaml` (CP-06-005), `specs/sync-ledger-replication.yaml` (SYNC-03-005). ADR-0115.
Notes: `notes/case-communication-model.md`.
