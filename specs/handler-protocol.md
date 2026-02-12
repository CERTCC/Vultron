# Handler Protocol Specification

## Overview

Handler functions process DispatchActivity objects and implement protocol business logic. All handlers follow a common contract defined by the HandlerProtocol and enforced by the verify_semantics decorator.

**Source**: Protocol design, dispatcher architecture

---

## Handler Signature (MUST)

- `HP-01-001` All handler functions MUST accept a single DispatchActivity parameter
- `HP-01-002` Handler functions MAY return None or HandlerResult

## Semantic Verification (MUST)

- `HP-02-001` All handlers MUST use the `@verify_semantics` decorator
- `HP-02-002` The decorator MUST specify the expected MessageSemantics value

## Handler Registration (MUST)

- `HP-03-001` All handlers MUST be registered in SEMANTIC_HANDLER_MAP
- `HP-03-002` Registry keys MUST match decorator MessageSemantics values

## Payload Access (MUST)

- `HP-04-001` Handlers MUST access activity data via `dispatchable.payload`
- `HP-04-002` Handlers MUST use Pydantic models for type-safe payload access

## Error Handling (MUST)

- `HP-05-001` Handlers MUST raise exceptions for unrecoverable errors
- `HP-05-002` Handlers MUST log expected errors without raising exceptions

## Logging (MUST)

- `HP-06-001` Handlers MUST log entry at DEBUG level
- `HP-06-002` Handlers MUST log state transitions at INFO level
- `HP-06-003` Handlers MUST log errors at ERROR level

## Idempotency (SHOULD)

- `HP-07-001` Handlers SHOULD be idempotent to support retries
- `HP-07-002` Handlers SHOULD check for existing state before mutating

## Verification

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

### HP-07-001, HP-07-002 Verification
- Unit test: Handler called twice with same input produces same result
- Unit test: Handler checks existing state before mutation
- Integration test: Retry of failed handler succeeds

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/api/v2/backend/behavior_dispatcher.py`
- Implementation: `vultron/api/v2/backend/semantic_handler_map.py`
- Tests: `test/api/v2/backend/test_handlers.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
