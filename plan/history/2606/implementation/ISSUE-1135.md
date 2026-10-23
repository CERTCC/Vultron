---
source: ISSUE-1135
timestamp: '2026-06-24T20:57:58.088821+00:00'
title: 'CP-06-004: RejectCaseProposalReceivedUseCase updates vendor local state'
type: implementation
---

## Issue #1135 — CP-06-004: RejectCaseProposalReceivedUseCase must update vendor local state

Implemented CP-06-004: `RejectCaseProposalReceivedUseCase` now updates the
vendor's `VultronReportCaseLink` with rejection state via a BT tree, instead
of only emitting a WARNING log.

**Changes:**

- Added `proposal_rejected: bool` and `rejection_reason: NonEmptyString | None`
  fields to `VultronReportCaseLink` (CP-06-004, CS-08-002).
- Created `reject_case_proposal_received_tree.py` with
  `_RecordCaseProposalRejectionNode` BT leaf and factory function
  (BT-15-001 compliant).
- Updated `RejectCaseProposalReceivedUseCase` to extract `report_id` and
  `rejection_reason`, then delegate to BT tree via `BTBridge.execute_with_setup()`.
- Fixed `_build_activity_snapshot` in the extractor to propagate the outer
  AS2 activity's `summary` field into the `VultronActivity` snapshot
  (normalised with `or None` to guard empty strings per CS-08-002).
- Added 4 new unit tests (rejection state, rejection reason, missing-link
  tolerance, log message).

All 4323 unit tests pass. Black, flake8, mypy, pyright clean.

PR: [#1153](https://github.com/CERTCC/Vultron/pull/1153)
