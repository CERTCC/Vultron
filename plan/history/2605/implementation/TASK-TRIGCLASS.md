---
source: TASK-TRIGCLASS
timestamp: '2026-05-04T21:12:23.891523+00:00'
title: 'TASK-TRIGCLASS: Trigger Classification and Demo Route Separation'
type: implementation
---

Implemented TASK-TRIGCLASS (Priority 474): separated demo-only trigger
endpoints from general-purpose ones and added a new `add-object-to-case`
general trigger endpoint.

## Changes

### New: `SvcAddObjectToCaseUseCase` (TRIGCLASS.2)

- Added `AddObjectToCaseTriggerRequest` to `requests.py`
- Added `SvcAddObjectToCaseUseCase` to `case.py` using generic `as_Add`
- Refactored `SvcAddReportToCaseUseCase` to delegate to
  `SvcAddObjectToCaseUseCase` after type-validating the report
- Added `add_object_to_case()` method to `TriggerService`
- Added `add_object_to_case` method to `TriggerServicePort` Protocol
- Added `AddObjectToCaseRequest` HTTP model to `trigger_models.py`
- Updated `trigger_case.py`: replaced `add-note-to-case` endpoint with
  new `add-object-to-case` endpoint (POST /actors/{id}/trigger/add-object-to-case)

### New: Demo router (TRIGCLASS.1)

- Created `demo_triggers.py` with `add-note-to-case` and `sync-log-entry`
  at `/actors/{actor_id}/demo/` prefix, `tags=["Demo Triggers"]`
- Demo router is only mounted in `RunMode.PROTOTYPE` via conditional import
  in `app.py` (TRIG-09-002, TRIG-09-003)
- Emptied `trigger_sync.py` to a deprecation stub; removed from `v2_router.py`
- Updated `test_trigger_sync.py` to import from `demo_triggers` and use
  `/demo/sync-log-entry` URL path

### Tests

- Added `test_demo_triggers.py` covering both demo endpoints
- Added `add-object-to-case` tests to `test_trigger_case.py`
- All 2302 unit tests pass

## Bug fix

- `app.py` conditional used `get_config().server.run_mode` (wrong);
  corrected to `get_config().mode` (the actual `AppConfig` field)
