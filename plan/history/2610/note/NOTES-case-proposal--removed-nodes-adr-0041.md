---
source: NOTES-case-proposal--removed-nodes-adr-0041
timestamp: '2026-10-12T19:33:10.154010+00:00'
title: Removed nodes and corrected receiver tree shape (ADR-0041)
type: note
---

**Archived:** 2026-10-12
**Reason:** change history; receive_report_case_tree.py is built in its ADR-0041 shape
**Superseded by:** ADR-0041; vultron/core/behaviors/report/

---

## Removed nodes (ADR-0041)

The following nodes are **removed** from the receiver's
`receive_report_case_tree.py` and must not be re-added:

| Removed node | Reason |
|---|---|
| `CreateCaseNode` | CaseActor creates the case |
| `CreateCaseOwnerParticipant` | CaseActor adds receiver as participant |
| `InitializeDefaultEmbargoNode` | CaseActor initializes embargo |
| `CreateCaseActivity` / `UpdateActorOutbox` | CaseActor emits `Create(VulnerabilityCase)` |
| `CreateCaseActorNode` | CaseActor is a pre-existing service, not spawned by the receiver |
| `SendOfferCaseManagerRoleNode` *(deleted, issue #2429)* | CaseActor adds itself as `CASE_MANAGER` natively — replaced by `OFFER_CASE_PARTICIPANT_ROLE` (ADR-0039) |
| `WritePrologueLedgerEntriesNode` | Back-fill replaced by native CaseActor init |

## Corrected receiver tree shape (ADR-0041)

`receive_report_case_tree.py` becomes:

```text
ReceiveReportCaseBT (Sequence)
├─ CheckAutoCaseCreationEnabledNode
└─ ReceiveReportCaseSelector (Selector)
   ├─ CheckProposalAlreadySentForReport    # idempotency
   └─ ReceiveReportProposalFlow (Sequence)
      ├─ WritePendingReportCaseLinkNode      # VultronReportCaseLink(status=PENDING_PROPOSAL)
      └─ ProposeReportCaseToActorNode              # Create(as_CaseProposal) → CaseActor
```

No `VulnerabilityCase`, no participants, no embargo created by the report receiver.
