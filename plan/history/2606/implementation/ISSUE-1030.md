---
source: ISSUE-1030
timestamp: '2026-06-17T23:59:10.163662+00:00'
title: Fix CaseActor ledger routing gaps (ack_report, close_case, note, embargo)
type: implementation
---

## Issue #1030 — Fix remaining CaseActor ledger routing gaps

Completed all 6 acceptance criteria for ADR-0021 CaseActor ledger routing
across five event types that were previously missing guarded commits.

**AC-0 — Generalize emit pattern**: Added `_EmitCaseActorReportActivityBase`
base class in `vultron/core/behaviors/report/nodes/emit.py`. Refactored
`EmitValidateReportActivity`, `EmitInvalidateReportActivity`, and
`EmitCloseReportActivity` to inherit from it. Added `EmitAckReportActivity`.

**AC-1 — ack_report routing**:

- Added `ack_report(offer_id, actor, to)` to `TriggerActivityPort` and
  `_ReportsMixin` adapter (creates `Read(Offer(Report))` matching the
  `AckReportPattern` in the extractor).
- Added `EmitAckReportActivity` to `create_ack_report_received_tree`
  (Selector, graceful no-op when no CaseActor).
- Updated `AckReportReceivedUseCase` with `sync_port`/`trigger_activity`
  params and the pre-flight guard + guarded commit pattern.
- Added `ACK_REPORT` to `_SYNC_AND_TRIGGER_PORT_SEMANTICS`.

**AC-2 — close_case routing**:

- Added `close_case(case_id, actor, to)` to `TriggerActivityPort` and
  `_CasesMixin` adapter (creates `Leave(VulnerabilityCase)`).
- Updated `AutoCloseBranchNode.update()` to emit `Leave(VulnerabilityCase)`
  to the CaseActor when all participants are `RM.CLOSED`.
- Rewrote `CloseCaseReceivedUseCase` with pre-flight guard + guarded commit
  (removed the old unaddressed Leave activity creation).
- Added `CLOSE_CASE` to `_SYNC_PORT_SEMANTICS`.
- Added `("Leave", "VulnerabilityCase")` to `_CANONICAL_PAYLOAD_SIGNATURES`
  in the sync adapter.

**AC-3 — note.py strict guard**: Replaced the broken Option B fallback
(`if actor_id is None: actor_id = _find_case_actor_id(...)`) in
`AddNoteToCaseReceivedUseCase.execute()` with a strict pre-flight guard —
commit only when `receiving_actor_id == case_actor_id`.

**AC-4 — embargo pre-flight guards**: Added pre-flight guard + guarded commit
to both `InviteToEmbargoOnCaseReceivedUseCase` and
`AcceptInviteToEmbargoOnCaseReceivedUseCase` after their BT executions.

**AC-5 — xfail removal**: Removed `pytest.mark.xfail` decorators from 5
entries in `test/ci/test_case_ledger_invariants.py`: `ack_report`,
`invite_to_embargo_on_case`, `accept_invite_to_embargo_on_case`, `close_case`,
`add_note_to_case`.

**AC-6 — Unit tests**: Added 12 routing guard tests across 4 new files in
`test/core/use_cases/received/`:

- `test_ack_report_routing.py`
- `test_close_case_routing.py`
- `test_note_routing_guard.py`
- `test_embargo_routing_guard.py`

Each test verifies: commit fires when `receiving_actor_id == case_actor_id`;
commit is skipped when not the CaseActor or `receiving_actor_id` is None.

**Results**: 3502 tests passed, mypy clean, flake8 clean.

PR: <https://github.com/CERTCC/Vultron/pull/1032>
