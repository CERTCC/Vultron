# Vultron API v2 Implementation Notes

**Last Updated**: 2026-02-13

## Recent Changes (2026-02-13 PM)

###submit_report Handler Implementation

**Status**: COMPLETE (Phase 0.1)

**What was implemented**:
- Full business logic for `submit_report` handler in `vultron/api/v2/backend/handlers.py`
- Extracts VulnerabilityReport from as_Offer activity
- Stores both report and offer using data layer `create()` method
- Proper INFO-level logging with actor ID, report name, and IDs
- Graceful handling of duplicate submissions (logs WARNING, doesn't fail)
- Type checking: verifies object is VulnerabilityReport before processing

**Supporting Fixes**:
- Uncommented `initialize_examples()` function in `vultron/scripts/vocab_examples.py` (needed for demo initialization)
- Fixed `get_actors()` endpoint in `vultron/api/v2/routers/actors.py` to validate `rec["data_"]` instead of `rec` (was returning Record wrapper instead of actor objects)

**Test Results**:
- Main test suite: 362 tests passed (no regressions)
- 4 tests failing in `test_reporting_workflow.py` - these use `_old_handlers` which are being deprecated, unrelated to new handler
- Demo test (`test_receive_report_demo.py`) still marked xfail - infrastructure issues remain (actor lookup by short ID, etc.)

**Remaining Infrastructure Issues** (blocking demo, but beyond scope of handler implementation):
1. Inbox endpoint requires full actor ID (e.g., "https://vultron.example/organizations/vendorco")
2. Demo passes short ID (e.g., "vendorco") extracted via `parse_id()`
3. Need to either:
   - Update inbox endpoint to handle short IDs and look up full ID
   - Update demo to pass full IDs
   - Create actor ID resolver utility
4. `init_actor_ios()` call in demo may need to happen earlier or differently

**Next Steps** (for next iteration):
- Task 0.2: Implement validate_report handler
- Task 0.3: Implement status tracking system
- Or: Fix actor ID resolution infrastructure issue first

## Purpose

This document captures insights, observations, and technical notes discovered during implementation planning and gap analysis. These notes supplement the formal implementation plan and provide context for future developers.

---

## Gap Analysis Summary (2026-02-13)

**Updated after comprehensive code review on 2026-02-13**

### Key Finding: Infrastructure is Solid, Business Logic Needed

The architecture review reveals that the core infrastructure (semantic extraction, dispatch routing, data layer abstraction, handler protocol) is **well-implemented and functional**. The primary gap is **handler business logic** - the stub implementations need to be filled in with actual state persistence and workflow logic.

**Priority Adjustment**: While the original plan deferred all handler logic to Phase 4, `plan/PRIORITIES.md` identifies getting `scripts/receive_report_demo.py` working as the **top priority**. This requires implementing business logic for a small subset of handlers:
- `submit_report` (store offer and report)
- `validate_report` (update status, create case, populate outbox)
- `close_report`, `invalidate_report` (status updates)

Once these core handlers are implemented, the demo will work and validate the entire pipeline end-to-end.

### Critical Gaps Identified

#### 1. Request Validation (HIGH PRIORITY)
**Status**: Partially implemented

**What exists**:
- ActivityStreams type validation via Pydantic models
- HTTP 422 for validation failures
- Basic activity parsing

**Missing**:
- Content-Type header validation (`application/activity+json`, `application/ld+json`)
- 1MB payload size limit enforcement
- HTTP 413 for oversized payloads
- HTTP 415 for unsupported Content-Type
- URI format validation for `as_id` fields

**Impact**: Inbox accepts invalid requests that should be rejected early

**Reference**: specs/inbox-endpoint.md, specs/message-validation.md

#### 2. Standardized Error Responses (HIGH PRIORITY)
**Status**: Not implemented

**What exists**:
- Error hierarchy base classes (`VultronError`, `VultronApiError`)
- Basic HTTP exceptions via FastAPI
- Some error logging

**Missing**:
- Structured JSON error response format:
  ```json
  {
    "status": 400,
    "error": "ValidationError",
    "message": "Activity missing required field: object",
    "activity_id": "urn:uuid:..."
  }
  ```
- Exception context attributes (`activity_id`, `actor_id`, `original_exception`)
- Custom exception handlers registered in FastAPI app
- Consistent mapping of error types to HTTP status codes
- Log level correlation with HTTP status (4xx → WARNING, 5xx → ERROR)

**Impact**: Error responses lack context for debugging; inconsistent error format

**Reference**: specs/error-handling.md

#### 3. Health Check Endpoints (HIGH PRIORITY)
**Status**: Not implemented

**Missing**:
- `/health/live` endpoint (liveness probe)
- `/health/ready` endpoint (readiness probe with data layer check)
- Health router registration in main app

**Impact**: Cannot monitor service health in deployment environments

**Reference**: specs/observability.md (OB-05-001, OB-05-002)

#### 4. Structured Logging (HIGH PRIORITY)
**Status**: Basic logging exists but not structured

**What exists**:
- Python logging module usage
- DEBUG, INFO, WARNING, ERROR levels used
- Some lifecycle logging (activity received, processing, errors)
- State transition logging

**Missing**:
- Structured log format (JSON or consistent key-value pairs)
- Correlation ID tracking (using activity `as_id`)
- Required fields in all log entries: timestamp (ISO 8601), level, component, activity_id, actor_id, message
- INFO-level lifecycle events: activity received, validated, queued, handler invoked, state transitions, completed
- Audit trail logging for state changes
- CRITICAL level usage (never used currently)

**Impact**: Logs difficult to parse, no request tracing, missing audit trail

**Reference**: specs/observability.md

#### 5. Idempotency/Duplicate Detection (MEDIUM PRIORITY)
**Status**: Not implemented

**Missing**:
- Activity ID tracking mechanism (in-memory or persistent)
- Duplicate detection before processing
- HTTP 202 response for duplicates without reprocessing
- TTL-based cleanup for old activity IDs

**Impact**: Same activity submitted twice will be processed twice

**Reference**: specs/inbox-endpoint.md (IE-10-001/002), specs/message-validation.md (MV-08-001)

### Handler Business Logic Gap (HIGH PRIORITY - Updated)

**Status**: Stub implementations exist, need business logic

**Current State**:
- All 47 handler functions defined in `vultron/api/v2/backend/handlers.py`
- All handlers use `@verify_semantics` decorator correctly
- All handlers registered in `SEMANTIC_HANDLER_MAP`
- All handlers accept `DispatchActivity` parameter
- All handlers currently just log at DEBUG level and return None

**What's Missing**:
1. **State Persistence**: Handlers don't persist objects to data layer
2. **Status Tracking**: No OfferStatus, ReportStatus, or other state tracking
3. **Outbox Population**: Handlers don't create response activities or populate outboxes
4. **Business Logic**: No validation of state transitions or workflow rules
5. **Error Handling**: No domain-specific error conditions handled

**Priority Update**: Originally planned for Phase 4 (deferred), now **Phase 0 (top priority)** for core handlers needed by receive_report_demo.py:
- `submit_report`: Store VulnerabilityReport and SubmitReport (as_Offer) in data layer
- `validate_report`: Update status, create VulnerabilityCase, populate outbox
- `close_report`: Update report status to CLOSED
- `invalidate_report`: Update report status to INVALID
- `ack_report`: Acknowledge receipt

**Impact**: Demo script `receive_report_demo.py` fails because handlers don't persist state or create expected side effects (cases, outbox items)

**Reference Implementation**: Old handlers in `vultron/api/v2/backend/_old_handlers/` show expected logic:
- `offer.py::rm_submit_report`: Store report and offer using `datalayer.create(object_to_record(obj))`
- `accept.py::rm_validate_report`: Update statuses, create case, populate outbox

**Implementation Notes**:
- Data layer API has changed from `receive_offer()`, `receive_case()` to unified `create(record)`
- Use `object_to_record()` helper from `db_record.py` to convert Pydantic models to Record format
- Status tracking needs reimplementation (old code used separate status storage)
- Outbox handling exists in `actor_io.py` but needs integration with handlers
**Status**: Tests exist but no coverage thresholds

**What exists**:
- ~170+ test functions across codebase
- pytest configured
- Tests for dispatcher, semantic extraction, handlers
- Integration tests for API endpoints

**Missing**:
- pytest-cov configuration in `pyproject.toml`
- Coverage thresholds (80%+ overall, 100% critical paths)
- Coverage reports in CI
- pytest markers for unit vs integration tests
- Test data factories
- Centralized fixtures in root conftest

**Impact**: Unknown actual coverage; may have untested critical paths

**Reference**: specs/testability.md

---

## Architectural Observations

### Strengths of Current Implementation

1. **Clean Separation of Concerns**
   - Routers handle HTTP layer only
   - Backend contains business logic
   - Data layer abstracted via Protocol interface
   - Clear pipeline: validation → semantic extraction → dispatch → handler

2. **Semantic-Driven Architecture**
   - Pattern-based activity classification is elegant and extensible
   - 47 semantic types cover CVD workflow comprehensively
   - `@verify_semantics` decorator provides safety net

3. **Protocol-Based Design**
   - Using Protocol classes instead of ABC enables flexible testing
   - Duck typing allows easy mocking
   - TinyDB backend demonstrates pluggability

4. **Async Processing Foundation**
   - FastAPI BackgroundTasks already provides async processing
   - No blocking operations in HTTP request path
   - 202 response returned within 100ms

### Areas for Improvement

1. **Validation Too Late**
   - Content-Type and size checks should happen before activity parsing
   - Consider FastAPI middleware or dependencies for early validation
   - Avoids processing invalid requests

2. **Error Context Lost**
   - Exceptions raised deep in call stack lose activity/actor context
   - Need context propagation mechanism (contextvar or explicit passing)
   - Error responses can't include activity_id without this

3. **Logging Not Request-Scoped**
   - No correlation ID linking log entries for same activity
   - Difficult to trace request through pipeline
   - Consider contextvars for correlation ID storage

4. **Test Organization Mixed**
   - Mix of unittest.TestCase and pytest styles
   - No clear unit vs integration separation
   - Fixtures scattered across multiple conftest files

---

## Technical Decisions & Rationale

### Why Implement Core Handler Logic First?

**Updated Decision**: Implement core handler business logic to get receive_report_demo.py working, then complete remaining handlers

**Original Rationale** (to defer all handlers):
- 47 handlers represent significant implementation effort (10-15 days)
- Core infrastructure (validation, dispatch, logging) provides more value immediately
- Can verify correct handler invocation without implementing business logic

**Why This Changed**:
- Per `plan/PRIORITIES.md`, getting the demo working is the **top priority**
- The demo provides end-to-end validation of the architecture
- Only a small subset of handlers (~5-6) are needed for the demo
- Infrastructure is already solid; blocked on business logic, not architecture
- The old handler implementations in `_old_handlers/` provide clear reference implementation

**New Approach** (Phase 0):
1. Implement submit_report handler (store offer and report)
2. Implement validate_report handler (create case, populate outbox)
3. Implement status tracking system for state management
4. Implement close_report and invalidate_report for workflow completeness
5. Verify receive_report_demo.py test passes
6. **Then** proceed with infrastructure hardening (validation, logging, etc.) in Phase 1-3
7. Complete remaining 42 handlers systematically in Phase 4

### Why In-Memory Duplicate Detection Initially?

**Decision**: Start with in-memory cache, upgrade to persistent storage if needed

**Rationale**:
- Simpler implementation (Python dict with timestamps or cachetools)
- Faster than database queries
- Research prototype doesn't require high availability
- Can upgrade to TinyDB table if persistence proves necessary
- Avoids premature optimization

**Implementation Notes**:
- Use TTL-based expiration (e.g., 24 hours)
- Log duplicate detections at INFO level
- Consider LRU cache to limit memory usage
- Document that duplicate detection lost on restart

### Why JSON Logging Format?

**Decision**: Use JSON-formatted structured logs

**Rationale**:
- Machine-parseable for log aggregation systems
- Standard format supported by observability tools
- Easy to add fields without breaking parsers
- Can add console-friendly formatter for development

**Implementation Notes**:
- Include required fields: timestamp, level, component, activity_id, actor_id, message
- Use ISO 8601 for timestamps
- Consider python-json-logger library
- Add optional fields: request_id, duration_ms, error_type

### Why Pytest Markers Instead of Directory Separation?

**Decision**: Use `@pytest.mark.unit` and `@pytest.mark.integration` markers

**Rationale**:
- Simpler to implement (no directory restructuring)
- Can run specific test types: `pytest -m unit`, `pytest -m integration`
- Tests stay colocated with code they test
- Can reorganize later if directory separation becomes beneficial

**Implementation Notes**:
- Register markers in `pyproject.toml`
- Mark all existing tests appropriately
- Use in CI to run unit tests first, integration tests second

---

## Specification Compliance Matrix

This matrix tracks implementation status against specifications. Updated during gap analysis.

| Spec File | Total Requirements | Implemented | Partial | Missing | Priority |
|-----------|-------------------|-------------|---------|---------|----------|
| inbox-endpoint.md | ~15 | 4 | 4 | 7 | HIGH |
| message-validation.md | ~10 | 2 | 2 | 6 | HIGH |
| semantic-extraction.md | ~8 | 8 | 0 | 0 | ✅ COMPLETE |
| dispatch-routing.md | ~6 | 6 | 0 | 0 | ✅ COMPLETE |
| handler-protocol.md | ~8 | 6 | 2 | 0 | MEDIUM |
| response-format.md | ~10 | 0 | 0 | 10 | DEFERRED |
| error-handling.md | ~12 | 2 | 4 | 6 | HIGH |
| observability.md | ~15 | 3 | 5 | 7 | HIGH |
| testability.md | ~20 | 10 | 5 | 5 | HIGH |
| code-style.md | ~5 | 3 | 2 | 0 | MEDIUM |

**Legend**:
- Implemented: Requirement fully met
- Partial: Requirement partially met or incomplete
- Missing: Requirement not implemented
- ✅ COMPLETE: All requirements implemented

---

## Testing Insights

### Current Test Coverage Observations

From codebase analysis (exact coverage TBD - needs pytest-cov run):

**Well-Tested Areas**:
- Behavior tree infrastructure (22 test files)
- Case state models (11 test files)
- Dispatcher protocol (unit tests exist)
- Semantic extraction (pattern matching tested)
- Basic API endpoints (integration tests exist)

**Under-Tested Areas**:
- Error handling paths (missing edge cases)
- Validation failures (limited error scenarios)
- Async processing (no async test functions found)
- Full request-to-handler flow (limited integration coverage)

**Missing Test Infrastructure**:
- No test data factories (hard-coded test data)
- No centralized fixtures (scattered across conftest files)
- No coverage thresholds (can't track regression)
- No markers for test categorization

### Recommended Testing Approach

1. **Measure Baseline**
   - Run `pytest --cov=vultron --cov-report=html --cov-report=term-missing`
   - Identify current coverage percentages
   - Document gaps in coverage report

2. **Prioritize Critical Paths**
   - Get to 100% coverage on: validation, semantic extraction, dispatch, error handling
   - These are the "spine" of the system

3. **Build Test Infrastructure**
   - Create `test/factories.py` with Pydantic model factories
   - Centralize fixtures in `test/conftest.py`
   - Add markers to existing tests

4. **Add Integration Tests**
   - Full inbox flow: POST → validation → dispatch → handler → response
   - Error scenarios: invalid Content-Type, oversized payload, malformed activity
   - Idempotency: submit same activity twice

5. **Automate in CI**
   - Fail build if coverage drops below 80%
   - Fail build if critical paths below 100%
   - Generate and archive coverage reports

---

## Code Patterns & Conventions

### Naming Conventions (Established)

- ActivityStreams types: `as_` prefix (e.g., `as_Activity`, `as_Actor`)
- Vulnerability: Abbreviated as `vul` (not `vuln`)
- Handler functions: Named after semantic action (e.g., `create_report`, `accept_invite_actor_to_case`)
- Pattern objects: CamelCase descriptive (e.g., `CreateReport`, `AcceptInviteToEmbargoOnCase`)

### Error Handling Pattern (To Be Established)

Proposed pattern for consistent error handling:

```python
# At entry point (router)
try:
    # Validate and process
    result = await process_activity(activity)
except VultronApiValidationError as e:
    # Log at WARNING level (client error)
    logger.warning(f"Validation failed: {e.message}", extra={
        "activity_id": e.activity_id,
        "actor_id": e.actor_id
    })
    # Return structured error response
    return JSONResponse(
        status_code=e.status_code,
        content={
            "status": e.status_code,
            "error": e.__class__.__name__,
            "message": e.message,
            "activity_id": e.activity_id
        }
    )
except VultronApiError as e:
    # Log at ERROR level (server error)
    logger.error(f"Processing failed: {e.message}", exc_info=True, extra={
        "activity_id": e.activity_id,
        "actor_id": e.actor_id
    })
    # Return structured error response
    return JSONResponse(
        status_code=e.status_code,
        content={
            "status": e.status_code,
            "error": e.__class__.__name__,
            "message": e.message,
            "activity_id": e.activity_id
        }
    )
```

### Logging Pattern (To Be Established)

Proposed pattern for structured logging:

```python
import logging
from contextvars import ContextVar

# Correlation ID context
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Structured logging helper
def log_with_context(level: str, message: str, **kwargs):
    extra = {
        "activity_id": correlation_id.get(),
        "component": __name__,
        **kwargs
    }
    logger.log(level, message, extra=extra)

# Usage in handler
def inbox_handler(actor_id: str, activity: dict):
    # Set correlation ID
    correlation_id.set(activity.get("id"))
    
    # Log with context
    log_with_context("INFO", "Activity received", actor_id=actor_id)
    
    # Process...
    
    log_with_context("INFO", "Processing complete")
```

---

## Open Technical Questions

### Question: Content-Type Validation Implementation

**Context**: Spec requires accepting both `application/activity+json` and `application/ld+json; profile="https://www.w3.org/ns/activitystreams"`

**Options**:
1. FastAPI dependency that checks `request.headers["Content-Type"]`
2. Middleware that validates before request reaches router
3. Pydantic validator on activity model

**Considerations**:
- Dependencies are cleaner but add overhead to every endpoint
- Middleware applies globally but may need endpoint-specific logic
- Pydantic validator too late (body already parsed)

**Recommendation**: FastAPI dependency for reusability and testability

### Question: Activity ID Uniqueness Scope

**Context**: Spec requires duplicate detection based on activity ID

**Considerations**:
- Should activity IDs be unique globally or per-actor?
- ActivityStreams spec says IDs should be globally unique URIs
- But duplicate detection might be per-actor (same ID from different actors OK?)

**Current Assumption**: Activity IDs are globally unique; duplicates detected regardless of submitting actor

**Need to Confirm**: Check ActivityStreams spec and CVD protocol requirements

### Question: Handler Idempotency Guarantees

**Context**: Handlers may be invoked multiple times (retry logic, duplicate submissions)

**Considerations**:
- Should handlers be idempotent (same input → same result)?
- How to handle state transitions that can only occur once?
- What should handlers return for duplicate invocations?

**Current Assumption**: Handlers should be idempotent; check current state before transitions

**Need to Design**: Idempotency patterns for stateful operations

---

## Performance Considerations (Future)

### Bottlenecks Identified (Theoretical)

1. **Semantic Extraction Pattern Matching**
   - Current: Linear search through 47 patterns
   - Impact: O(n) where n=47 for each activity
   - Mitigation: Pattern ordering (specific before general) helps; could add caching

2. **TinyDB Performance**
   - Current: JSON file-based storage
   - Impact: Not suitable for high-throughput production
   - Mitigation: Already abstracted behind Protocol; can swap implementation

3. **Synchronous Handler Execution**
   - Current: Handlers execute synchronously in background task
   - Impact: Long-running handlers block processing
   - Mitigation: Async queue-based dispatch (Phase 7 consideration)

**Note**: These are theoretical concerns. Research prototype performance is adequate. Only optimize if/when real-world usage demands it.

---

## Future Work Ideas

### Behavior Tree Integration

**Context**: ADR-0002 and ADR-0007 specify behavior tree modeling for CVD processes

**Current State**: Behavior tree infrastructure exists (`vultron/bt/`) but not integrated with API v2 handlers

**Integration Points**:
- Handlers could invoke behavior trees for workflow logic
- State transitions could be modeled as BT nodes
- BT success/failure could determine handler responses

**Consideration**: Defer until handler business logic phase (Phase 4)

### Federation & Activity Delivery

**Context**: Vultron aims to be federated CVD protocol

**Current State**: Inbox receives activities; outbox exists but delivery not implemented

**Missing Pieces**:
- Actor discovery (WebFinger, actor endpoints)
- HTTP Signatures for authentication
- Activity delivery to remote inboxes
- Retry logic with exponential backoff
- Delivery failure handling

**Consideration**: Future phase beyond current research scope

### Real-Time Notifications

**Context**: Actors may want real-time updates for case changes

**Options**:
- WebSockets for persistent connections
- Server-Sent Events (SSE) for unidirectional updates
- Webhooks for push notifications
- Polling (current implicit approach)

**Consideration**: Future enhancement; polling sufficient for research prototype

---

## Lessons Learned

### What Went Well

1. **Specification-First Approach**
   - Having detailed specs makes gap analysis systematic
   - Clear requirements prevent scope creep
   - Testable verification criteria guide implementation

2. **Behavior Tree Modeling**
   - BT infrastructure demonstrates feasibility
   - Composable nodes enable complex workflows
   - State machine modeling is clean

3. **ActivityStreams Vocabulary Adoption**
   - Rich vocabulary covers CVD domain well
   - Pydantic models provide validation and type safety
   - Standard format enables future interoperability

### What Could Be Improved

1. **Earlier Validation**
   - Should validate Content-Type and size before parsing
   - Middleware or dependencies better than endpoint-level checks
   - Saves processing invalid requests

2. **Error Context Propagation**
   - Need better mechanism to carry activity_id through call stack
   - Consider contextvar or explicit context object
   - Exceptions need context attributes

3. **Test Infrastructure First**
   - Should have built test factories and fixtures earlier
   - Coverage enforcement from start prevents gaps
   - Integration tests validate architecture

4. **Documentation Alongside Code**
   - Specs written first was good
   - Inline documentation should happen during implementation
   - Readme and examples should evolve with code

---

## Quick Reference

### Key Files by Function

**Inbox Processing**:
- `vultron/api/v2/routers/actors.py` - HTTP endpoint
- `vultron/api/v2/backend/inbox_handler.py` - Activity processing
- `vultron/api/v2/backend/helpers.py` - Validation utilities

**Semantic Extraction**:
- `vultron/semantic_map.py` - Pattern matching
- `vultron/activity_patterns.py` - Pattern definitions
- `vultron/enums.py` - MessageSemantics enum

**Dispatch & Handlers**:
- `vultron/behavior_dispatcher.py` - Dispatcher implementation
- `vultron/semantic_handler_map.py` - Semantic → handler mapping
- `vultron/api/v2/backend/handlers.py` - Handler implementations

**Data Layer**:
- `vultron/api/v2/datalayer/abc.py` - Protocol interface
- `vultron/api/v2/datalayer/tinydb_backend.py` - TinyDB implementation
- `vultron/api/v2/data/actor_io.py` - Actor inbox/outbox

**Error Handling**:
- `vultron/errors.py` - Base error hierarchy
- `vultron/api/v2/errors.py` - API-specific errors

### Common Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=vultron --cov-report=html --cov-report=term-missing

# Run only unit tests (once markers added)
pytest -m unit

# Run only integration tests (once markers added)
pytest -m integration

# Type checking
mypy vultron/

# Code formatting
black vultron/ test/

# Start development server
uvicorn vultron.api.v2.app:app --reload
```

### Useful Grep Patterns

```bash
# Find all handler functions
grep -r "@verify_semantics" vultron/

# Find all error classes
grep -r "class.*Error.*VultronError" vultron/

# Find all semantic patterns
grep -r "MessageSemantics\." vultron/

# Find TODO comments
grep -r "TODO\|FIXME\|XXX" vultron/
```
---

## Architecture Migration Analysis (2026-02-13)

### What Changed from Old to New Architecture

The codebase underwent a significant refactor to move from the old handler system to the new dispatcher-based architecture. Understanding this migration is key to implementing Phase 0.

#### Old Architecture (`_old_handlers/`)
- **Handler Registration**: Decorator-based registry using `ActivityHandler` partial functions
- **Routing**: Activity type + Object type pattern matching
- **Handler Signature**: `handler(actor_id: str, activity: ActivityType, datalayer: DataStore)`
- **Data Layer Methods**: Specialized methods like `receive_offer()`, `receive_case()`, `receive_report()`
- **Status Tracking**: Separate status objects (OfferStatus, ReportStatus) with `set_status()` function

Example old handler:
```python
@offer_handler(object_type=VulnerabilityReport)
def rm_submit_report(actor_id: str, activity: as_Offer, datalayer: DataStore):
    datalayer.create(object_to_record(activity.as_object))  # report
    datalayer.create(object_to_record(activity))  # offer
```

#### New Architecture (Current)
- **Handler Registration**: Explicit mapping in `semantic_handler_map.py`
- **Routing**: MessageSemantics-based (47 semantic types extracted via pattern matching)
- **Handler Signature**: `handler(dispatchable: DispatchActivity) -> None`
- **Data Layer Methods**: Unified CRUD interface (`create()`, `read()`, `update()`, `delete()`)
- **Status Tracking**: **Needs reimplementation** (not migrated from old system)

Example new handler stub:
```python
@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchActivity) -> None:
    logger.debug("submit_report handler called: %s", dispatchable)
    # TODO: Implement business logic
    return None
```

### Migration Path for Handlers

To implement Phase 0 handlers, adapt the old handler logic to the new architecture:

1. **Extract Data from DispatchActivity**:
   ```python
   activity = dispatchable.payload  # The as_Activity object
   actor_id = activity.actor  # Extract actor from activity
   offered_object = activity.as_object  # For transitive activities
   ```

2. **Get Data Layer Instance**:
   ```python
   from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
   dl = get_datalayer()
   ```

3. **Store Objects Using Unified API**:
   ```python
   from vultron.api.v2.datalayer.db_record import object_to_record
   dl.create(object_to_record(offered_object))  # Still use object_to_record
   dl.create(object_to_record(activity))
   ```

4. **Access Actor IO**:
   ```python
   from vultron.api.v2.data.actor_io import get_actor_io
   actor_io = get_actor_io(actor_id, raise_on_missing=True)
   # Add to outbox
   actor_io.outbox.items.append(create_activity)
   ```

5. **Implement Status Tracking** (design decision needed):
   - Option A: Store status as separate objects in data layer
   - Option B: Add status fields to existing objects (reports, offers, cases)
   - Option C: Use data layer tables for status tracking
   
   Recommendation: Start with Option A (separate status objects) to match old behavior

### Key Differences to Handle

1. **No Direct actor_id Parameter**: Extract from `dispatchable.payload.actor`
2. **No Injected datalayer**: Call `get_datalayer()` within handler
3. **Status System Missing**: Need to reimplement status tracking (OfferStatus, ReportStatus)
4. **Outbox Handling**: Use `actor_io.outbox.items.append()` instead of specialized methods

### Status Tracking Reimplementation

The old system used these status types:
- `OfferStatus`: Tracks offer lifecycle (PENDING, ACCEPTED, REJECTED)
- `ReportStatus`: Tracks report state per RM state machine (RECEIVED, VALID, INVALID, CLOSED)
- `set_status(status_obj)`: Persisted status to storage
- `get_status(object_id, actor_id)`: Retrieved current status

**Migration Approach**:
1. Create new status models in `vultron/api/v2/data/status.py` (file exists, needs expansion)
2. Store status objects in data layer using `create()` or `update()`
3. Query status using `dl.read()` or specialized status query functions
4. Ensure status updates are atomic and support concurrent access

### Testing Strategy for Migration

1. **Unit Tests**: Test each handler in isolation with mock data layer
2. **Integration Tests**: Test handler within full inbox processing flow
3. **Demo Validation**: Use `receive_report_demo.py` as end-to-end test
4. **Comparison Testing**: Compare old vs new handler behavior with same inputs
