---
title: 'ARCH-CLEANUP-3 complete: isinstance AS2 checks replaced (V-11, V-12)'
type: implementation
timestamp: '2026-03-10T00:00:00+00:00'
source: ARCH-CLEANUP-3
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 625
legacy_heading: "2026-03-10 \u2014 ARCH-CLEANUP-3 complete: isinstance AS2\
  \ checks replaced (V-11, V-12)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-10'
---

## ARCH-CLEANUP-3 complete: isinstance AS2 checks replaced (V-11, V-12)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:625`
**Canonical date**: 2026-03-10 (git blame)
**Legacy heading**

```text
2026-03-10 — ARCH-CLEANUP-3 complete: isinstance AS2 checks replaced (V-11, V-12)
```

**Legacy heading dates**: 2026-03-10

> ✅ Captured in `notes/architecture-review.md` (V-11, V-12 marked remediated
> by ARCH-CLEANUP-3) and `docs/adr/0009-hexagonal-architecture.md` (2026-03-10).

### What changed

- **`handlers/report.py`**: `create_report` and `submit_report` now check
  `dispatchable.payload.object_type != "VulnerabilityReport"` instead of
  `isinstance`. `validate_report` uses `getattr(accepted_report, "as_type", None)`.
  Local `VulnerabilityReport` imports removed from all three handlers.
- **`handlers/case.py`**: `update_case` uses `getattr(incoming, "as_type", None) ==
  "VulnerabilityCase"`. Local `VulnerabilityCase` import removed.
- **`trigger_services/report.py`**: `_resolve_offer_and_report` uses `getattr`
  as_type check. `VulnerabilityReport` module-level import removed.
- **`trigger_services/_helpers.py`**: `resolve_case` and
  `update_participant_rm_state` use `getattr` as_type checks. `VulnerabilityCase`
  import retained for the `-> VulnerabilityCase` return type annotation.
- **`test/test_behavior_dispatcher.py`**: Removed `as_TransitiveActivityType` and
  `VulnerabilityReport` imports. `as_type` assertion uses string `"Create"`.
  Dispatch test uses `MagicMock` for `raw_activity` instead of full AS2 construction.
- **`test/api/test_reporting_workflow.py`**: `_call_handler` now populates
  `InboundPayload.object_type` from `activity.as_object.as_type` (mirrors
  `prepare_for_dispatch`), so handler type guards work correctly in tests.

822 tests pass.

### Shim modules deleted

- Deleted `vultron/activity_patterns.py`, `vultron/semantic_map.py`, and
  `vultron/semantic_handler_map.py` (all were pure re-export shims).
- Updated all callers to import from canonical locations:
  - `test/test_semantic_activity_patterns.py`: `ActivityPattern` and
    `SEMANTICS_ACTIVITY_PATTERNS` now imported from `vultron.wire.as2.extractor`.
  - `test/api/test_reporting_workflow.py`: `find_matching_semantics` now imported
    from `vultron.wire.as2.extractor`.
  - `test/test_semantic_handler_map.py`: Shim-specific tests removed; test now
    uses `SEMANTICS_HANDLERS` from `vultron.api.v2.backend.handler_map` directly.
- 822 tests pass.

---

### Handler registry added

- **`vultron/api/v2/backend/handler_map.py`** (new): Module-level handler registry in
  the adapter layer. `SEMANTICS_HANDLERS` dict maps `MessageSemantics` → handler
  functions with plain module-level imports (no lazy imports needed since this file
  is already in the adapter layer). This addresses V-09.

- **`vultron/semantic_handler_map.py`**: Converted to a backward-compat shim that
  re-exports `SEMANTICS_HANDLERS` and a `get_semantics_handlers()` wrapper from
  the new location. Can be deleted once all callers are updated.

- **`vultron/behavior_dispatcher.py`**: `DispatcherBase` now accepts `dl: DataLayer`
  and `handler_map: dict[MessageSemantics, BehaviorHandler]` in its constructor.
  `_handle()` passes `dl=self.dl` to each handler. `_get_handler_for_semantics()`
  uses `self._handler_map` directly (no lazy import). `get_dispatcher()` updated to
  accept `dl` and `handler_map` parameters.

- **`vultron/api/v2/backend/inbox_handler.py`**: Module-level `DISPATCHER` now
  constructed with `get_datalayer()` + `SEMANTICS_HANDLERS` injected. The lazy
  import in `_get_handler_for_semantics` is gone; the coupling to the handler map
  now lives in the adapter layer only.

- **All handler files** (`report.py`, `case.py`, `embargo.py`, `actor.py`, `note.py`,
  `participant.py`, `status.py`, `unknown.py`): Each handler function signature
  updated to `(dispatchable: DispatchActivity, dl: DataLayer) -> None`. All
  `from vultron.api.v2.datalayer.tinydb_backend import get_datalayer` lazy imports
  and `dl = get_datalayer()` calls removed. `DataLayer` imported at module level from
  `vultron.api.v2.datalayer.abc`. This addresses V-10.

- **`vultron/types.py`**: `BehaviorHandler` Protocol updated to
  `__call__(self, dispatchable: DispatchActivity, dl: DataLayer) -> None`.

- **`vultron/api/v2/backend/handlers/_base.py`**: `verify_semantics` wrapper updated
  to accept and forward `dl: DataLayer`.

- **Tests**: All `@patch("vultron.api.v2.datalayer.tinydb_backend.get_datalayer")`
  patches in `test_handlers.py` replaced with direct `mock_dl` argument passing.
  `test_behavior_dispatcher.py` updated to construct dispatcher with injected DL
  and handler map. 824 tests pass (up from 822).

### Phase PRIORITY-50 is now complete (ARCH-1.1 through ARCH-1.4)

All four ARCH-1.x tasks are done. The hexagonal architecture violations V-01 through
V-10 have been remediated. The remaining violations in the inventory (V-11, V-12)
are lower severity and can be addressed as part of subsequent work.
