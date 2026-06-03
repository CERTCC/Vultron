---
source: ISSUE-655
timestamp: '2026-06-03T20:28:43.495913+00:00'
title: Introduce ActorScopedDataLayer protocol
type: implementation
---

## Issue #655 — Introduce ActorScopedDataLayer protocol to enforce DataLayer scope at type level

Split the monolithic `DataLayer` protocol into two protocols:

- `DataLayer` — shared storage operations (no queue ops); `clone_for_actor()` returns `ActorScopedDataLayer`
- `ActorScopedDataLayer(DataLayer)` — actor-scoped inbox/outbox queue methods (6 methods moved from `DataLayer`)

The 6 methods moved to `ActorScopedDataLayer` are those with no explicit `actor_id` parameter (they implicitly operate on the bound actor's scope). `record_outbox_item(actor_id, activity_id)` stays on `DataLayer` because it takes an explicit `actor_id`.

### Key design decisions

- `SqliteDataLayer.clone_for_actor()` returns `"SqliteDataLayer"` (concrete covariant override) rather than `"ActorScopedDataLayer"`, keeping `_actor_instances: dict[str, SqliteDataLayer]` type-consistent.
- `TriggerService.__init__` now takes `CaseOutboxPersistence` (the narrow port that includes `outbox_append`), not `DataLayer`.
- `cast(CaseOutboxPersistence, dl)` used in `deps.py` and `inbox_handler.py` port factory functions — safe because the concrete runtime type is always `SqliteDataLayer` which satisfies both protocols structurally.
- Port factory function signatures stay `Callable[[DataLayer], dict]` to match the dispatcher's `Mapping[MessageSemantics, Callable[["DataLayer"], dict]]` type — `cast()` inside the function body handles the narrowing.

### Files changed

- `vultron/core/ports/datalayer.py` — added `ActorScopedDataLayer` protocol; updated `clone_for_actor()` return type
- `vultron/adapters/driven/datalayer_sqlite.py` — concrete covariant return type on `clone_for_actor()`
- `vultron/adapters/driving/fastapi/deps.py` — `get_canonical_actor_dl()` returns `ActorScopedDataLayer`; cast in `get_trigger_service()`
- `vultron/adapters/driving/fastapi/inbox_handler.py` — 5 queue-using functions now typed `ActorScopedDataLayer`; casts in port factories
- `vultron/adapters/driving/fastapi/outbox_handler.py` — `dl: ActorScopedDataLayer`
- 5 trigger router files — `actor_dl: ActorScopedDataLayer`
- `vultron/core/use_cases/triggers/service.py` — `TriggerService.__init__` takes `CaseOutboxPersistence`
- `test/core/ports/test_datalayer_protocol.py` — new conformance tests (4 tests)

All 2618 tests pass; mypy 0 errors; pyright 0 errors; flake8 clean.

PR: [#723](https://github.com/CERTCC/Vultron/pull/723)
