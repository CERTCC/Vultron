---
source: NOTES-case-proposal--received-side-use-cases
timestamp: '2026-10-12T19:33:10.790469+00:00'
title: BT Integration and Received-Side Use Cases
type: note
---

**Archived:** 2026-10-12
**Reason:** inventory of live code; use_case_map() and SEMANTIC_REGISTRY enforce it
**Superseded by:** vultron/core/use_cases/received/; vultron/wire/as2/extractor/

---

## BT Integration: `ProposeReportCaseToActorNode`

`ProposeReportCaseToActorNode` sends `Create(as_CaseProposal)` to the CaseActor
service. The CaseActor service URI comes from
`ActorConfig.case_actor_service_url` (CP-08-001 through CP-08-003).

---

## Received-Side Use Cases

Three received-side use cases are required:

| Use Case | Actor | Handles |
|----------|-------|---------|
| `CreateCaseProposalReceivedUseCase` | Case-actor service | `Create(as_CaseProposal)` arriving at case-actor inbox |
| `AcceptCaseProposalReceivedUseCase` | Report receiver | `Accept(as_CaseProposal)` arriving at receiver inbox |
| `RejectCaseProposalReceivedUseCase` | Report receiver | `Reject(as_CaseProposal)` arriving at receiver inbox |

All three must be registered as the `use_case_class` of their `SEMANTIC_REGISTRY`
entry, keyed by the corresponding `MessageSemantics` value, so that they appear
in the mapping returned by `use_case_map()`.
