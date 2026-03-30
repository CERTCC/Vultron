# Handler Protocol Specification

## Overview

Handler use-case classes process `VultronEvent` domain objects and implement
protocol business logic. All handlers follow a common contract defined by the
`UseCase` Protocol.

**Source**: Protocol design, dispatcher architecture

---

## Protocol Semantics

- `HP-00-001` Handlers MUST interpret received activities as assertions about the
  sender's state, not as commands to perform work
- `HP-00-002` Handlers MUST update local RM/EM/CS state to reflect the state
  transition asserted by the received activity

## Handler Signature

- `HP-01-001` All handler use-case classes MUST accept `(event: VultronEvent,
  dl: DataLayer)` — either as `__init__` parameters or as `execute` parameters
- `HP-01-002` Handler use-case `execute` methods MAY return None or HandlerResult

## Semantic Verification

- `HP-02-001` All handlers MUST have semantic type verification before execution
  - **Implementation**: Semantic type is checked at dispatcher lookup time using
    the `USE_CASE_MAP` key; mismatched events raise `VultronApiHandlerNotFoundError`
- `HP-02-002` The verification mechanism MUST check that the activity's semantic type matches the handler's expected type
  - **Rationale**: Prevents routing errors where wrong handler processes an activity

## Handler Registration

- `HP-03-001` All handlers MUST be discoverable via a handler registry mechanism
  - **Implementation**: Registry map (`USE_CASE_MAP`) maps MessageSemantics → use-case classes
- `HP-03-002` Registry keys MUST match handler semantic verification types

## Payload Access

- `HP-04-001` Handlers MUST access activity data via `dispatchable.payload`
  - **Rationale**: Encapsulation; payload may be validated/transformed by dispatcher
- `HP-04-002` Handlers MUST use schema validation for type-safe payload access
  - **Implementation**: Pydantic models provide validation and type safety

## Error Handling

- `HP-05-001` Handlers MUST raise exceptions for unrecoverable errors
- `HP-05-002` Handlers MUST log expected errors without raising exceptions

## Logging

- `HP-06-001` Handlers MUST log entry at DEBUG level with handler name
- `HP-06-002` Handlers MUST log state transitions at INFO level with before/after states
- `HP-06-003` Handlers MUST log errors at ERROR level with full context
  - HP-06-003 depends-on SL-03-001
  - HP-06-003 depends-on SL-04-001

## Idempotency

- `HP-07-001` Handlers SHOULD be idempotent to support retries
  - State-changing handlers (those that transition RM/EM/CS state) MUST be
    idempotent to prevent data corruption
  - HP-07-001 depends-on ID-04-001

## Execution Timeout

- `HP-07-002` `PROD_ONLY` Handlers MUST complete execution within 30 seconds
  - **Rationale**: Prevents indefinite blocking of background task queue
  - **Enforcement**: MAY be implemented via timeout wrapper or async task
    timeout
  - **Failure behavior**: Handler timeout MUST raise `HandlerTimeoutError`
- `HP-07-003` `PROD_ONLY` Long-running operations MUST be broken into async subtasks
  - **Examples**: External API calls, bulk database operations, report
    generation
  - **Pattern**: Use FastAPI BackgroundTasks for orchestration; split work into
    multiple handler invocations

## Data Model Persistence

- `HP-08-001` Handlers MUST use helper functions when persisting Pydantic models to the data layer
  - **Verification**: Pydantic models round-trip through database without data loss
- `HP-08-002` Handlers MUST call `DataLayer.update()` with all required parameters
  - **Verification**: Updates succeed with correct signature; TypeError raised for incorrect signatures
- `HP-08-003` Pydantic validators MUST NOT overwrite existing field values during deserialization
  - **Verification**: Objects with populated fields retain data after `model_validate()` from database records
  - **Impact**: Prevents data loss when round-tripping through persistence layer
- `HP-08-004` The DataLayer and handlers MUST treat object IDs as opaque URI
  strings
  - Handlers MUST persist full URI IDs (e.g., `urn:uuid:...` / `https://...`) rather than bare UUID fragments.
  - Persistence helpers (`object_to_record()` / `record_to_object()`) MUST preserve ID strings exactly and MUST NOT rely on extracting parts of the ID.
  - Comparison and duplicate-detection MUST use full-ID string equality.
  - If any legacy storage contains bare-UUIDs, a migration plan MUST be documented and executed (see project documentation).
- `HP-08-005` Handlers that add status updates MUST append full status objects
  (not bare ID strings) to the case/participant status history lists
  - Handlers MUST rehydrate and persist the full `CaseStatus` object and then
    append it to `VulnerabilityCase.case_statuses` before persisting the case
  - If the storage layer contains validators that enforce `context` or other
    fields, the handler MUST provide full objects so validators can operate
    correctly
  - HP-08-005 depends-on CM-03-006
- `HP-08-006` The `AddNoteToCase` handler MUST persist a Note object and append its ID as a `as_NoteRef` to `VulnerabilityCase.notes`.
  - **Rationale**: Ensures notes are fully persisted and linked to cases, consistent with the case management data model
  - (VulnerabilityCase.notes is conceptually a "join table" linking cases to
    notes)

## Verification

### HP-00-001, HP-00-002 Verification

- Integration test: Handler receiving RM state-transition activity updates local RM state
- Code review: Handlers do not issue work requests back to activity sender

### HP-01-001, HP-01-002 Verification

- Unit test: Handler use-case class accepts `VultronEvent` and `DataLayer`
- Unit test: Handler returns None or HandlerResult
- Type check: Handler signature matches `UseCase` Protocol

### HP-02-001, HP-02-002 Verification

- Unit test: Verify dispatcher uses `USE_CASE_MAP` for lookups
- Unit test: Verify `VultronApiHandlerNotFoundError` raised for unrecognised
  semantic types

### HP-03-001, HP-03-002 Verification

- Unit test: All use-case classes in USE_CASE_MAP
- Unit test: Registry keys match use-case semantic types
- Unit test: No handlers missing from registry

### HP-04-001, HP-04-002 Verification

- Unit test: Handler accesses payload via dispatchable.payload
- Unit test: Pydantic validation occurs on payload access
- Code review: No direct dictionary access to activity data

### HP-05-001, HP-05-002 Verification

- Unit test: Handler raises exception for unrecoverable error
- Unit test: Handler logs and continues for expected error
- Integration test: Exception propagates to dispatcher

### HP-06-001, HP-06-002, HP-06-003 Verification

- Unit test: Verify DEBUG log entry on handler invocation
- Unit test: Verify INFO log for state transitions
- Unit test: Verify ERROR log for errors

### HP-07-001 Verification

- See `idempotency.md` ID-04-001 verification criteria

### HP-07-002, HP-07-003 Verification

- Integration test: Handler completes within 30 seconds
- Unit test: Simulated long-running handler raises HandlerTimeoutError after 30s
- Code review: Long-running operations use async subtask pattern

### HP-08-001, HP-08-002 Verification

- Code review: All `DataLayer.update()` calls include both ID and record parameters
- Code review: All Pydantic model persistence uses `object_to_record()` helper
- Unit test: Update with single argument raises TypeError
- Unit test: Update with ID and record succeeds

### HP-08-003 Verification

- Unit test: Pydantic model with after validator round-trips through database without data loss
- Unit test: Validator checks field is None before initializing default value
- Integration test: Actor inbox/outbox collections persist correctly after handler updates
- Regression test: Objects with populated collections retain data after `model_validate()`

## Related

- Implementation: `vultron/core/use_cases/` (use-case modules)
- Implementation: `vultron/core/dispatcher.py`
- Implementation: `vultron/core/use_cases/use_case_map.py` (`USE_CASE_MAP` registry)
- Tests: `test/core/use_cases/received/`, `test/test_semantic_handler_map.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
