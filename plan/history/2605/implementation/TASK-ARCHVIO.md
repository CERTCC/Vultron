---
source: TASK-ARCHVIO
timestamp: '2026-05-04T20:53:50.039910+00:00'
title: Remove deferred SyncActivityAdapter imports from core sync use cases
type: implementation
---

## TASK-ARCHVIO — Remove Remaining Core→Adapter Import Violations (sync cleanup)

Removed three deferred `SyncActivityAdapter` import fallbacks that violated
ARCH-01-001 (core MUST NOT import from adapters):

1. `vultron/core/use_cases/received/sync.py` —
   `AnnounceLogEntryReceivedUseCase._send_rejection`: replaced lazy fallback
   with `VultronError` raise when `sync_port is None`.
2. `vultron/core/use_cases/triggers/sync.py` —
   `_fan_out_log_entry`: replaced lazy fallback with a graceful DEBUG-level
   skip (fan-out is optional when sync_port is absent, e.g. single-actor tests).
3. `vultron/core/use_cases/triggers/sync.py` —
   `replay_missing_entries_trigger`: replaced lazy fallback with `VultronError`
   raise (replay is always in a SYNC context where sync_port must be present).

Updated tests to inject `SyncActivityAdapter(dl)` or `MagicMock(spec=SyncActivityPort)`
explicitly rather than relying on the fallback:

- `test/core/use_cases/received/test_sync.py`
- `test/core/use_cases/received/test_reject_sync.py`
- `test/adapters/driving/fastapi/routers/test_trigger_sync.py`

Added architecture ratchet test:

- `test/architecture/test_core_no_adapter_imports.py` — asserts no file in
  `vultron/core/` contains any import from `vultron.adapters` (including
  deferred/local imports), using the same ratchet pattern as the existing
  `test_activity_factory_imports.py` test.

Outcome: `vultron/core/` is now free of all `vultron.adapters` imports.
All 2286 tests pass; all linters (Black, flake8, mypy, pyright) pass clean.
