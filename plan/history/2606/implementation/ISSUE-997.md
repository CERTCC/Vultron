---
source: ISSUE-997
timestamp: '2026-06-16T21:21:55.145369+00:00'
title: Core BT inbox orchestration module
type: implementation
---

## Issue #997 — Implement core BT inbox orchestration module with process_payload -> InboxOutcome seam

Implemented the `process_payload() -> InboxOutcome` seam specified in ADR-0020
and `specs/inbox-orchestration.yaml` IO-01 through IO-04.

### What was done

- Added `vultron/core/behaviors/inbox/` package with:
  - `models.py` — `InboxOutcome` Pydantic model + 3 `@runtime_checkable`
    Protocol interfaces (`IngressPayloadAdapter`, `DispatchAdapter`,
    `PendingCaseQueuePort`); no wire imports per ARCH-01-001
  - `nodes/pipeline.py` — 6 BT leaf nodes enforcing fixed pipeline ordering:
    `ParsePayloadNode → RehydrateActivityNode → ExtractSemanticsNode →
    DeferCheckNode → DispatchNode → BuildOutcomeNode`
  - `inbox_tree.py` — `create_inbox_bt()` factory
  - `_process_payload.py` — `process_payload()` with extracted helpers;
    acquires `_BT_GLOBAL_LOCK` (RLock shared with BTBridge) and saves/restores
    blackboard state
- Added `vultron/adapters/driving/fastapi/inbox_orchestration.py` with
  `FastAPIIngressAdapter`, `StoredActivityIngressAdapter`,
  `FastAPIDispatchAdapter`, `FastAPIQueuePort`, `run_inbox_pipeline()`
- Updated `routers/actors/_routes.py` `post_actor_inbox` to call
  `run_inbox_pipeline`; restored `_record_inbox_receipt` (dedup fix) and
  threaded raw body dict through to adapter (nested object re-parsing fix)
- Added 14 tests in `test/core/behaviors/inbox/test_process_payload.py`
  asserting on `InboxOutcome` fields only (no internal BT node patching per
  IO-04-002)

### Key design notes

- `ExtractSemanticsNode` extracts `context_id` from `event.object_.id_` for
  bootstrap (`ANNOUNCE_VULNERABILITY_CASE`) activities where `context_` is not
  set on the activity
- `DeferCheckNode` skips defer for bootstrap and when `queue_port is None`
- `DispatchNode` triggers `queue.replay()` after successful bootstrap dispatch
- Pre-existing bug fixed: `_activity_context_id` used `getattr(activity,
  "context", None)` (wrong attribute name); corrected to `context_` with
  AS2 default namespace filtered out

### Outcome

All linters pass. 3492 unit tests pass, 34 skipped, 2 xfailed.

PR: [#1019](https://github.com/CERTCC/Vultron/pull/1019)
