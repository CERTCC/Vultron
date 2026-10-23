---
source: ISSUE-1138
timestamp: '2026-06-26T16:13:38.314795+00:00'
title: CP-05-006 idempotent duplicate Create(CaseProposal) handling
type: implementation
---

## Issue #1138 — CP-05-006: CreateCaseProposalReceivedUseCase should handle duplicate Create(CaseProposal) idempotently

Implemented CP-05-006 by restructuring `CreateCaseProposalReceivedBT` from a
flat Sequence into a Selector+Sequence with two new guard nodes:

- `_CheckMarkerExistsNode` (AC-3): if a `PendingCreateCaseActivity` marker
  already exists for the proposal_id, Accept was already sent and Create
  delivery is still pending — return SUCCESS immediately (no-op).
- `_LoadExistingCaseNode` (AC-1/AC-2): if `find_case_by_report_id()` returns
  an existing VulnerabilityCase, write its id_ to the blackboard so the
  subsequent Accept + Create reference the existing case instead of creating
  a duplicate.

Added `TestCreateCaseProposalIdempotency` with 3 new tests covering AC-1
(no duplicate case), AC-2 (Accept references existing case), AC-3 (in-flight
marker → no-op). Full suite: 4374 passed, 38 skipped, 2 xfailed. All linters
clean.

PR: <https://github.com/CERTCC/Vultron/pull/1196>
