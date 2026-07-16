---
source: ISSUE-1086
timestamp: '2026-06-23T17:03:49.336933+00:00'
title: Implement CaseProposal received-side use cases
type: implementation
---

## Issue #1086 — Implement CaseProposal received-side use cases

Replaced three `NotImplementedError` stubs in
`vultron/core/use_cases/received/case_proposal.py` with real
BT-delegating implementations.

**Implementations delivered:**

- `CreateCaseProposalReceivedUseCase` — delegates to new
  `CreateCaseProposalReceivedBT` (3-node Sequence): creates
  `VulnerabilityCase`, emits `Accept(as_CaseProposal)` with inline
  proposal object (CP-05-003, MV-09-001), emits
  `Create(VulnerabilityCase)` with `context=Accept URI` for causal
  traceability (CP-05-003).
- `AcceptCaseProposalReceivedUseCase` — delegates to new
  `AcceptCaseProposalReceivedBT` which updates
  `VultronReportCaseLink.trusted_case_actor_id` (CP-06-001, CP-06-003).
- `RejectCaseProposalReceivedUseCase` — surfaces rejection via WARNING
  log (CP-06-002); CP-06-004 state mutation deferred to #1135.

**Supporting changes:**

- Added `context` field to `VultronCreateCaseActivity` (CP-05-003).
- Added `as_CaseProposal` to `_STUB_OBJECT_MODEL_MAP` in
  `outbox_delivery.py` so `Accept.object_` survives the dict-recovery
  pipeline (MV-09-001).
- Added `accept_case_proposal_activity()` and
  `reject_case_proposal_activity()` factory functions.
- New unit tests: `test/core/use_cases/received/test_case_proposal.py`.

**Deferred follow-ups opened:**

- #1135 — CP-06-004 rejection state mutation
- #1136 — CP-05-005 retry `Create(VulnerabilityCase)` after partial failure

**Verification:** 4310 unit tests pass; all four linters clean;
architecture ratchets (`test_no_dl_mutations_in_execute`,
`test_single_bt_execution_received_side`) continue to pass.

PR: [#1137](https://github.com/CERTCC/Vultron/pull/1137)
