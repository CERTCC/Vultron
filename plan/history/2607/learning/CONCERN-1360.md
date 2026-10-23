---
source: CONCERN-1360
timestamp: '2026-07-13T19:06:32.996145+00:00'
title: Core domain helpers return None silently instead of raising
type: learning
---

## Summary

Several core domain helper functions return `None` on failure rather than
raising an exception. This creates silent failures: the program continues
executing with a `None` result, and the error surfaces far from its origin
— if at all.

## Most significant sites

### `_as_id()` — two copies, both silent

- `core/use_cases/_helpers.py:58-59`
- `core/services/embargo_lifecycle.py:77` (duplicate; consolidation tracked in #538)

When an AS2 object has no resolvable `id_`, both return `None`. Every
downstream lookup (`_resolve_case_manager_id`, `resolve_case_participant_id_for_actor`,
embargo loops) then silently skips or propagates `None` further.

### `_find_case_manager_from_participants()` — three copies, all silent

- `core/use_cases/_helpers.py:361-366`
- `core/behaviors/status/nodes/broadcast.py:43-49`
- `core/use_cases/received/case/_helpers.py:50-57`

All return `None` when no case manager is found; callers silently drop
broadcasts or skip routing.

### `_extract_case_id()` in dispatcher

- `core/dispatcher.py:207`

Returns `None` when an inbound activity cannot be routed to a case; the
activity is silently never ledger-indexed.

### `AppendCaseLedgerEntryNode` returns `Status.SUCCESS` on missing `case_id`

- `core/behaviors/case/nodes/lifecycle.py:157-161`

When `case_id` resolves to `None` at runtime, the ledger append is silently
skipped but the node returns `Status.SUCCESS`, misleading the BT sequence.

### `_read_case_obj()` swallows `KeyError` with no log

- `core/behaviors/case/nodes/communication.py:135-138`

Returns `None` on `KeyError` with no `feedback_message` set, leaving the
BT caller with zero diagnostic information.

## Impact

- Ledger entries silently not written
- Case-update broadcasts silently dropped
- Embargo routing silently mis-routed
- Debug traces point to the point of *use* of `None`, not the point of *failure*

**Resolved**: 2026-07-13 — implementation tracked in #1377 (fail-fast fixes)
and #1378 (helper consolidation).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1376>.
Spec: `specs/architecture.yaml` ARCH-15-001 through ARCH-15-004.
Notes: `notes/domain-validation.md`.
