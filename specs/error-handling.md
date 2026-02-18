# Error Handling Specification

## Overview

The Vultron inbox handler must handle various error conditions gracefully, providing clear error messages, maintaining system stability, and enabling debugging. This specification focuses on **exception hierarchy and error categories**.

**Source**: API design requirements, operational requirements

**Note**:

- **Error logging** requirements consolidated in `specs/structured-logging.md` (SL-03-001)
- **HTTP status codes** consolidated in `specs/http-protocol.md` (HP-03-001)

---

## Exception Hierarchy (MUST)

- `EH-01-001` The system MUST define custom exceptions for application-specific errors
- `EH-01-002` Custom exceptions MUST inherit from a base VultronError exception
- `EH-01-003` Custom exceptions MUST be centralized in `vultron/errors.py`

## Submodule Errors (MUST)

- `EH-02-001` Submodule-specific errors MUST be defined in submodule `errors.py`
- `EH-02-002` Submodule errors MUST inherit from base custom exceptions in `vultron/errors.py`

## Error Categories (MUST)

- `EH-03-001` The system MUST define error categories
  - Validation errors (4xx client errors)
  - Protocol errors (semantic/routing failures)
  - System errors (5xx server errors)

## Error Context (SHOULD)

- `EH-04-001` Exceptions SHOULD include contextual information
  - Activity ID
  - Actor ID
  - Error message
  - Original exception (if wrapped)

## Error Response Format (MUST)

- `EH-05-001` HTTP error responses MUST include structured JSON body
  - **Cross-reference**: See `http-protocol.md` HP-06-001 for complete format specification

## Error Logging (MUST)

- `EH-06-001` All errors MUST be logged with appropriate level
  - Client errors (4xx) → WARNING
  - Server errors (5xx) → ERROR
  - Include full context and stack trace for server errors
  - **Cross-reference**: `structured-logging.md` SL-03-001 for complete log level semantics

## Verification

### EH-01-001, EH-01-002, EH-01-003 Verification

- Unit test: Verify VultronError base exception exists
- Unit test: All custom exceptions inherit from VultronError
- Code review: All exceptions defined in `vultron/errors.py`

### EH-02-001, EH-02-002 Verification

- Unit test: Submodule errors inherit from base exceptions
- Code review: Submodule errors in appropriate `errors.py` files

### EH-03-001 Verification

- Unit test: Each error category has representative exception
- Code review: Exception hierarchy covers all error categories

### EH-04-001 Verification

- Unit test: Exceptions include contextual attributes
- Unit test: Exception message includes context information

### EH-05-001 Verification

- See `http-protocol.md` HP-06-001 verification criteria

### EH-06-001 Verification

- Integration test: Client errors logged at WARNING level
- Integration test: Server errors logged at ERROR level
- Integration test: Stack traces included for server errors

## Related

- Implementation: `vultron/errors.py`
- Implementation: `vultron/api/v2/backend/errors.py`
- Tests: `test/test_errors.py`
- Tests: `test/api/v2/backend/test_error_handling.py`
- Related Spec: [inbox-endpoint.md](inbox-endpoint.md)
- Related Spec: [message-validation.md](message-validation.md)
