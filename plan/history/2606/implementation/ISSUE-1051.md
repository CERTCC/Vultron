---
source: ISSUE-1051
timestamp: '2026-06-18T23:32:59.876579+00:00'
title: Single-BT execution for report.py and status.py received use cases
type: implementation
---

## Issue #1051 — Single-BT execution for report.py and status.py received use cases

Migrated three received-side use cases to the ADR-0022 single-BT-execution
pattern: one `execute_with_setup()` call per inbox delivery under
`actor_id=receiving_actor_id`, with the guarded-commit subtree embedded in
the tree factory rather than called as a separate BT execution.

### Use cases migrated

- `ValidateReportReceivedUseCase` — replaced `ValidateCaseUseCase` +
  separate guarded-commit BT with a single `create_validate_report_received_tree()`
  call embedding both the validate subtree and the guarded commit. Introduced
  `sender_actor_id` threading into `CheckRMStateValid`,
  `CheckRMStateReceivedOrInvalid`, and `TransitionRMtoValid` so the tree runs
  under `receiving_actor_id` while transitioning the message sender's RM state.
- `AckReportReceivedUseCase` — replaced two `execute_with_setup()` calls with
  one call using the updated `create_ack_report_received_tree(case_id=case_id)`.
- `AddParticipantStatusToParticipantReceivedUseCase` — removed
  `_commit_log_cascade_bt()` helper method; `add_participant_status_tree()` now
  accepts `case_id` and appends the guarded-commit subtree as its final child.

### Architecture ratchet updated

Removed `vultron/core/use_cases/received/report.py` and
`vultron/core/use_cases/received/status.py` from `KNOWN_VIOLATIONS` in
`test/architecture/test_single_bt_execution_received_side.py`.

### Notable design decisions

- The `ValidationOrShortcut` subtree in `create_validate_report_received_tree()`
  is wrapped in a `ValidationOrSkip` Selector with a `Success` fallback,
  preserving the old behavior where the guarded commit runs regardless of
  whether the validation BT succeeded (e.g., when `EnsureEmbargoExists` blocks
  due to no active embargo in the CaseActor's DataLayer context).
- Added `test_sender_rm_state_transitions_to_valid` to verify the
  `sender_actor_id` threading mechanism correctness end-to-end.

PR: [#1065](https://github.com/CERTCC/Vultron/pull/1065)
