# Observability Specification

## Overview

Observability enables operators to understand system behavior, diagnose issues, and monitor health. The Vultron inbox handler provides logging, health checks, and audit capabilities.

**Source**: Operational requirements, monitoring best practices

**Note**: Metrics and distributed tracing are deferred to future implementation.

---

## Log Levels (MUST)

- `OB-01-001` The system MUST use appropriate log levels
  - DEBUG: Detailed diagnostic information for development
  - INFO: General informational messages about system operation
  - WARNING: Recoverable errors or unexpected conditions
  - ERROR: Unrecoverable errors requiring attention
  - CRITICAL: System-level failures requiring immediate action

## Activity Lifecycle Logging (MUST)

- `OB-02-001` The system MUST log activity lifecycle events at INFO level
  - Activity received
  - Activity validated
  - Activity queued for processing
  - Handler invoked
  - State transitions
  - Processing completed

## Log Format (MUST)

- `OB-03-001` Log entries MUST include structured information
  - Timestamp (ISO 8601 format)
  - Log level
  - Component/module name
  - Activity ID (when available)
  - Actor ID (when available)
  - Message

## Log Correlation (SHOULD)

- `OB-04-001` Log entries for a single activity SHOULD share common correlation ID
  - Use activity ID as correlation key
  - Include in all log entries related to the activity

## Health Checks (MUST)

- `OB-05-001` The system MUST provide liveness endpoint at `/health/live`
  - Return HTTP 200 if process is running
  - Return HTTP 503 if process is unhealthy
- `OB-05-002` The system MUST provide readiness endpoint at `/health/ready`
  - Return HTTP 200 if ready to accept requests
  - Return HTTP 503 if dependencies unavailable

## Audit Trail (MUST)

- `OB-06-001` The system MUST log all state transitions at INFO level
  - Include before and after states
  - Include triggering activity
  - Include timestamp
- `OB-06-002` The system MUST log authorization decisions at INFO level
  - Include actor, action, resource, decision
- `OB-06-003` The system MUST log data access operations at DEBUG level
  - Include accessed resource, operation type

## Metrics (MAY)

- `OB-07-001` The system MAY expose metrics endpoint at `/metrics`
  - Request count by endpoint
  - Request duration percentiles
  - Error count by type
  - Queue depth
  - Handler execution time

## Verification

### OB-01-001, OB-02-001 Verification
- Integration test: Verify log entries at each lifecycle stage
- Integration test: Verify appropriate log levels used
- Code review: No print statements or console logging

### OB-03-001, OB-04-001 Verification
- Unit test: Log entries contain required fields
- Integration test: All logs for an activity share activity_id
- Integration test: Logs parseable as JSON or structured format

### OB-05-001, OB-05-002 Verification
- Integration test: GET /health/live returns 200
- Integration test: GET /health/ready returns 200 when ready
- Integration test: GET /health/ready returns 503 when not ready

### OB-06-001, OB-06-002, OB-06-003 Verification
- Integration test: State transitions logged with before/after states
- Integration test: Authorization decisions logged
- Integration test: Data access logged at DEBUG level

### OB-07-001 Verification
- Integration test: Metrics endpoint returns valid Prometheus format
- Integration test: Metrics updated after requests

## Related

- Implementation: `vultron/api/v2/routers/health.py`
- Implementation: Python logging configuration
- Tests: `test/api/v2/routers/test_health.py`
- Related Spec: [error-handling.md](error-handling.md)
- Related Spec: [testability.md](testability.md)
