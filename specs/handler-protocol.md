# Handler Protocol Specification

## Context

Handler functions process DispatchActivity objects and implement protocol business logic. All handlers must follow a common contract defined by the HandlerProtocol and enforced by the verify_semantics decorator.

## Requirements

### HP-1: Handler Signature
All handler functions MUST accept single DispatchActivity parameter and MAY return None or HandlerResult.

### HP-2: Semantic Verification Decorator
All handlers MUST use the @verify_semantics decorator with expected MessageSemantics value.

### HP-3: Handler Registration
All handlers MUST be registered in SEMANTIC_HANDLER_MAP.

### HP-4: Payload Access
Handlers MUST access activity data via dispatchable.payload using Pydantic models.

### HP-5: State Access
Handlers MUST access state via dependency injection, not global variables.

### HP-6: Error Handling
Handlers MUST raise exceptions for unrecoverable errors and log expected errors.

### HP-7: Logging
Handlers MUST log entry at DEBUG level, state transitions at INFO level, and errors at ERROR level.

### HP-8: Response Generation
Handlers that generate responses MUST return HandlerResult with response activity.

### HP-9: Idempotency
Handlers SHOULD be idempotent to support retries.

## Verification

See individual requirement verifications in full specification document.

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/semantic_handler_map.py`
- Implementation: `vultron/behavior_dispatcher.py`
- Tests: `test/api/v2/backend/test_handlers.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [error-handling.md](error-handling.md)

