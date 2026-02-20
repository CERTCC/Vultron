# Handler Protocol Specification

## Overview

Handler functions process DispatchActivity objects and implement protocol business logic. All handlers follow a common contract defined by the HandlerProtocol and enforced by the verify_semantics decorator.

**Source**: Protocol design, dispatcher architecture

---

## Protocol Semantics (MUST)

- `HP-00-001` Handlers MUST interpret received activities as assertions about the
  sender's state, not as commands to perform work
- `HP-00-002` Handlers MUST update local RM/EM/CS state to reflect the state
  transition asserted by the received activity

## Handler Signature (MUST)

- `HP-01-001` All handler functions MUST accept a single DispatchActivity parameter
- `HP-01-002` Handler functions MAY return None or HandlerResult

## Semantic Verification (MUST)

- `HP-02-001` All handlers MUST have semantic type verification before execution
  - **Implementation**: Uses `@verify_semantics` decorator with MessageSemantics enum value
- `HP-02-002` The verification mechanism MUST check that the activity's semantic type matches the handler's expected type
  - **Rationale**: Prevents routing errors where wrong handler processes an activity

## Handler Registration (MUST)

- `HP-03-001` All handlers MUST be discoverable via a handler registry mechanism
  - **Implementation**: Registry map (e.g., `SEMANTIC_HANDLER_MAP`) maps MessageSemantics → handler functions
- `HP-03-002` Registry keys MUST match handler semantic verification types

## Payload Access (MUST)

- `HP-04-001` Handlers MUST access activity data via `dispatchable.payload`
  - **Rationale**: Encapsulation; payload may be validated/transformed by dispatcher
- `HP-04-002` Handlers MUST use schema validation for type-safe payload access
  - **Implementation**: Pydantic models provide validation and type safety

## Error Handling (MUST)

- `HP-05-001` Handlers MUST raise exceptions for unrecoverable errors
- `HP-05-002` Handlers MUST log expected errors without raising exceptions

## Logging (MUST)

- `HP-06-001` Handlers MUST log entry at DEBUG level with handler name
- `HP-06-002` Handlers MUST log state transitions at INFO level with before/after states
- `HP-06-003` Handlers MUST log errors at ERROR level with full context
  - **Cross-reference**: `structured-logging.md` SL-03-001 for log level semantics
  - **Cross-reference**: `structured-logging.md` SL-04-001 for state transition format

## Idempotency (SHOULD)

- `HP-07-001` Handlers SHOULD be idempotent to support retries
  - State-changing handlers (those that transition RM/EM/CS state) MUST be
    idempotent to prevent data corruption
  - **Cross-reference**: See `idempotency.md` ID-04-001 for complete
    requirements

## Execution Timeout (MUST)

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

## Data Model Persistence (MUST)

- `HP-08-001` Handlers MUST use helper functions when persisting Pydantic models to the data layer
  - **Verification**: Pydantic models round-trip through database without data loss
- `HP-08-002` Handlers MUST call `DataLayer.update()` with all required parameters
  - **Verification**: Updates succeed with correct signature; TypeError raised for incorrect signatures
- `HP-08-003` Pydantic validators MUST NOT overwrite existing field values during deserialization
  - **Verification**: Objects with populated fields retain data after `model_validate()` from database records
  - **Impact**: Prevents data loss when round-tripping through persistence layer

### Implementation Notes

**HP-08-001 - Helper Function Pattern**:

```python
# Use object_to_record() to convert Pydantic models for storage
record = object_to_record(pydantic_model)
dl.create("collection", record)
```

**HP-08-002 - Data Layer Update Signature**:

```python
# Anti-pattern: dl.update(object)  # Missing record parameter
# Correct: Two-argument signature
dl.update(object.as_id, object_to_record(object))
```

**HP-08-003 - Defensive Pydantic Validators**:

```python
@model_validator(mode="after")
def initialize_collections(self) -> Self:
    # Anti-pattern: Unconditional assignment
    # self.inbox = OrderedCollection()  # Overwrites database values!
    
    # Correct: Check before initializing
    if self.inbox is None:
        self.inbox = OrderedCollection()
    return self
```

**Rationale**: Pydantic validators with `mode="after"` execute during both object creation AND database reconstruction (`model_validate()`). Validators that create default values must check if the field is already populated to avoid overwriting data loaded from persistence. This particularly affects collection fields (lists, OrderedCollections) that handlers populate and persist.

## Verification

### HP-00-001, HP-00-002 Verification

- Integration test: Handler receiving RM state-transition activity updates local RM state
- Code review: Handlers do not issue work requests back to activity sender

### HP-01-001, HP-01-002 Verification

- Unit test: Handler accepts DispatchActivity parameter
- Unit test: Handler returns None or HandlerResult
- Type check: Handler signature matches HandlerProtocol

### HP-02-001, HP-02-002 Verification

- Unit test: Verify decorator present on all handlers
- Unit test: Decorator validates correct semantic type
- Unit test: Decorator raises error for mismatched semantic type

### HP-03-001, HP-03-002 Verification

- Unit test: All handlers in SEMANTIC_HANDLER_MAP
- Unit test: Registry keys match decorator values
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

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/api/v2/backend/behavior_dispatcher.py`
- Implementation: `vultron/api/v2/backend/semantic_handler_map.py`
- Tests: `test/api/v2/backend/test_handlers.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
