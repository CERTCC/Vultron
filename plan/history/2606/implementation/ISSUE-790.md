---
source: ISSUE-790
timestamp: '2026-06-15T19:35:10.302001+00:00'
title: Add actor-local pending_assertions with configurable timeout
type: implementation
---

## Issue #790 — Add actor-local pending_assertions with configurable timeout and no auto-retry

Implemented a pure in-memory per-actor suppression store (`PendingAssertionStore`)
that prevents duplicate near-term re-emits of `CaseLedgerEntry` commits while
an actor awaits canonical log round-trip confirmation.

**Design constraints honored:**

- Purely in-memory; no DataLayer interaction; intentionally lost on restart
  (#791 catch-up gate handles post-restart replay)
- Actor-scoped: module-level `_STORES` dict keyed by actor URI string — not a
  DL operation, not cross-actor
- Configurable timeout (default 180 s); zero disables suppression entirely
- No auto-retry on timeout; cleared by Announce/Reject receipt or operator action

**Files added:**

- `vultron/core/models/pending_assertion.py`: `PendingAssertion` dataclass,
  `PendingAssertionStore`, and module-level per-actor registry
- `test/core/models/test_pending_assertion.py`: comprehensive unit tests

**Files modified:**

- `vultron/core/use_cases/triggers/sync.py`: suppression gate in
  `commit_log_entry_trigger`
- `vultron/core/behaviors/case/nodes/lifecycle.py`: suppression gate in
  `CommitCaseLedgerEntryNode.update()`, `pending_assertions` registered as
  READ blackboard key, helpers extracted to keep complexity in budget
- `vultron/core/use_cases/received/sync.py`: `store.clear()` in
  `AnnounceLedgerEntryReceivedUseCase` and `RejectLedgerEntryReceivedUseCase`
- `vultron/core/use_cases/triggers/service.py`: param wired through
- `vultron/adapters/driving/fastapi/inbox_handler.py`: store resolved via
  per-actor registry in `_sync_port_factory`

**Test results:** 3346 unit tests pass (6 new). All linters clean.

PR: [#975](https://github.com/CERTCC/Vultron/pull/975)
