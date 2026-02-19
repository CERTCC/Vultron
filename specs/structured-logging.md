# Structured Logging Requirements

**Version:** 1.0  
**Status:** ACTIVE  
**Last Updated:** 2026-02-13

## Purpose

Consolidated logging requirements for Vultron API v2: log format, correlation IDs, log levels, audit trail.

**Source:** Observability best practices, RFC 5424 Syslog severity  
**Consolidates:** `observability.md` (OB-01, OB-03, OB-04, OB-06), `error-handling.md` (EH-04, EH-06), `inbox-endpoint.md` (IE-09)

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

```python
# Verify log entry structure
with caplog.at_level(logging.INFO):
    process_activity(activity)
    log_entry = json.loads(caplog.records[0].message)
    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert "component" in log_entry
    assert "message" in log_entry
```

### SL-02-001, SL-02-002

```python
# Verify correlation IDs present
with caplog.at_level(logging.INFO):
    process_activity(activity)
    assert any("activity_id" in record.message for record in caplog.records)
    assert any("actor_id" in record.message for record in caplog.records)
```

### SL-03-001

```python
# Test log level usage
# Validation errors → WARNING
# Handler exceptions → ERROR with stack trace
```

### SL-04-001, SL-04-002, SL-04-003, SL-04-004

```python
# Verify state transition logging
with caplog.at_level(logging.INFO):
    validate_report(activity)
    assert "RECEIVED -> VALID" in caplog.text
    assert "ValidateReport" in caplog.text
```

## Implementation Example

### JSON Format (Production)

```json
{"timestamp": "2026-02-13T18:00:00.000Z", "level": "INFO", "component": "inbox", "activity_id": "urn:uuid:123", "message": "Activity received"}
```

### Key-Value Format (Development)

```
2026-02-13T18:00:00.000Z [INFO] component=inbox activity_id=urn:uuid:123 message="Activity received"
```

### Python Implementation

```python
import logging
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "activity_id"):
            log_entry["activity_id"] = record.activity_id
        if hasattr(record, "actor_id"):
            log_entry["actor_id"] = record.actor_id
        return json.dumps(log_entry)
```

## Related

- Implementation: `vultron/api/v2/logging_config.py` (future)
- Tests: `test/api/v2/test_logging.py` (use caplog fixture)
