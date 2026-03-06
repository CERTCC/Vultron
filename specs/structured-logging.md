# Structured Logging Requirements

## Overview

Consolidated logging requirements for Vultron API v2: log format, correlation IDs, log levels, audit trail.

**Source**: Observability best practices, RFC 5424 Syslog severity  
**Consolidates**: `observability.md` (OB-01, OB-03, OB-04, OB-06), `error-handling.md` (EH-04, EH-06), `inbox-endpoint.md` (IE-09)

---

## Log Format (MUST)

- `SL-01-001` `PROD_ONLY` All log entries MUST include `timestamp` field in ISO 8601 format
- `SL-01-002` `PROD_ONLY` All log entries MUST include `level` field (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `SL-01-003` `PROD_ONLY` All log entries MUST include `component` field (module or function name)
- `SL-01-004` `PROD_ONLY` All log entries MUST include `message` field (human-readable text)

## Correlation IDs (MUST)

- `SL-02-001` `PROD_ONLY` Log entries MUST include `activity_id` field when activity is available
- `SL-02-002` `PROD_ONLY` Log entries MUST include `actor_id` field when actor is available

## Log Level Semantics (MUST)

- `SL-03-001` Log levels MUST follow standard severity semantics per table below

| Level | Usage | Examples |
|-------|-------|----------|
| DEBUG | Diagnostic details, payload contents | "Payload: {...}", "Extracted object type: VulnerabilityReport" |
| INFO | Lifecycle events, state transitions | "Activity received", "Report validated", "Case created" |
| WARNING | Recoverable issues, HTTP 4xx errors | "Duplicate activity", "Missing optional field", "Invalid Content-Type" |
| ERROR | Unrecoverable failures, HTTP 5xx errors | "Failed to store activity", "Handler crashed" |
| CRITICAL | System-level failures | Reserved for catastrophic failures |

## State Transition Logging (MUST)

- `SL-04-001` All state transitions MUST be logged at INFO level
- `SL-04-002` State transition logs MUST include before state
- `SL-04-003` State transition logs MUST include after state
- `SL-04-004` State transition logs MUST include triggering event (activity type + semantic)
- `SL-04-005` Demo scripts and stepwise workflows SHOULD use structured,
  consistent lifecycle logs
  - Example convention (used in demos): wrap workflow steps in context-managers that log:
    - INFO on step start with a clear "step description"
    - INFO (or INFO + semantic token) on successful completion
    - ERROR with exception context on failure
  - Demo-specific shorthand/emojis (e.g., 🚥/🟢/🔴 for start/success/failure) are allowed for developer-facing logs but MUST NOT be relied upon by production log parsers; production logs should preserve structured fields (`component`, `activity_id`, `message`, `level`) regardless of visual decorations.

Example:

```json
{
  "timestamp": "2026-02-13T18:00:00.000Z",
  "level": "INFO",
  "component": "validate_report",
  "activity_id": "urn:uuid:123",
  "message": "Report state transition: RECEIVED -> VALID (ValidateReport)"
}
```

## Error Context (SHOULD)

- `SL-05-001` ERROR level logs SHOULD include exception type and message
- `SL-05-002` ERROR level logs SHOULD include stack trace for unexpected exceptions
- `SL-05-003` ERROR level logs SHOULD include original activity ID if available

## Authorization Logging (SHOULD)

- `SL-06-001` `PROD_ONLY` Authorization decisions SHOULD be logged with decision (allowed/denied)
- `SL-06-002` `PROD_ONLY` Authorization logs SHOULD include actor performing action
- `SL-06-003` `PROD_ONLY` Authorization logs SHOULD include resource being accessed
- `SL-06-004` `PROD_ONLY` Authorization logs SHOULD include denial reason if denied

## Data Access Logging (SHOULD)

- `SL-07-001` `PROD_ONLY` Sensitive data operations SHOULD log operation type (CREATE, READ, UPDATE, DELETE)
- `SL-07-002` `PROD_ONLY` Data access logs SHOULD include resource type and ID
- `SL-07-003` `PROD_ONLY` Data access logs SHOULD include actor performing operation

## Performance Metrics (MAY)

- `SL-08-001` `PROD_ONLY` System MAY log performance metrics at DEBUG level
  - Request processing duration
  - Database query time
  - Handler execution time

## Verification

### SL-01-001, SL-01-002, SL-01-003, SL-01-004

- Unit test: Log entries include `timestamp`, `level`, `component`, `message`
  fields (use `caplog` fixture)

### SL-02-001, SL-02-002

- Unit test: Log entries for activity processing include `activity_id` and
  `actor_id` fields

### SL-03-001

- Unit test: Validation errors logged at WARNING level
- Unit test: Handler exceptions logged at ERROR level with stack trace

### SL-04-001, SL-04-002, SL-04-003, SL-04-004

- Unit test: State transition log includes before state, after state, and
  triggering event

## Related

- Implementation: `vultron/api/v2/logging_config.py` (future)
- Tests: `test/api/v2/test_logging.py` (use caplog fixture)
