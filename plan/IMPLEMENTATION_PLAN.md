# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-13

## Overview

This implementation plan tracks the development of the Vultron API v2 inbox handler system against the detailed specifications in `specs/*`. The system has a solid foundation with semantic pattern matching, message dispatching, and handler stubs, but requires substantial work to meet all specification requirements for production readiness.

### Current Status

**Completed Infrastructure:**
- [x] Core dispatcher architecture (`behavior_dispatcher.py`) with `DirectActivityDispatcher`
- [x] Semantic extraction system (`semantic_map.py`, `activity_patterns.py`) with 47 patterns
- [x] All 47 MessageSemantics handlers registered in `semantic_handler_map.py`
- [x] Basic inbox endpoint at `POST /actors/{actor_id}/inbox/` with 202 response
- [x] Background task processing infrastructure via FastAPI BackgroundTasks
- [x] Unit tests for dispatcher and semantic matching (~170+ test functions)
- [x] Error hierarchy base (`VultronError` → `VultronApiError`)
- [x] TinyDB data layer implementation with Protocol abstraction
- [x] Handler protocol with `@verify_semantics` decorator
- [x] ActivityStreams 2.0 Pydantic models (vocabulary implementation)

**Critical Gaps (High Priority):**
- [ ] Request validation (Content-Type, 1MB size limit, URI validation)
- [ ] Standardized HTTP error responses (status, error, message, activity_id)
- [ ] Health check endpoints (`/health/live`, `/health/ready`)
- [ ] Structured logging with correlation IDs
- [ ] Idempotency/duplicate detection
- [ ] Test coverage enforcement (80%+ overall, 100% critical paths)

**Deferred (Lower Priority):**
- [ ] Handler business logic (47 stub implementations)
- [ ] Response generation (Accept/Reject/TentativeReject)
- [ ] Outbox processing
- [ ] Async dispatcher (FastAPI async processing already in place)



## Prioritized Task List

### BUGFIXES & IMMEDIATE NEEDS

- [x] Test runs are leaving behind a `mydb.json` file that should never be committed. Ensure that any TinyDB files created during testing are automatically deleted after tests complete, and add `mydb.json` to `.gitignore` to prevent accidental commits.

### Phase 0: Get receive_report_demo.py Working (TOP PRIORITY)

This is the immediate priority per `plan/PRIORITIES.md`. The demo script showcases the core workflow and validates that the new architecture can handle real-world scenarios.

#### 0.1 Implement submit_report Handler Business Logic
- [x] Extract VulnerabilityReport from SubmitReport activity (as_Offer with VulnerabilityReport object)
- [x] Store the VulnerabilityReport object in data layer via `create()`
- [x] Store the SubmitReport activity (as_Offer) in data layer via `create()`
- [x] Log INFO level: report submitted, report ID, submitter ID
- [x] Handle duplicate report submissions gracefully (check if report already exists)
- **Files**: `vultron/api/v2/backend/handlers.py` (submit_report function)
- **Reference**: `vultron/api/v2/backend/_old_handlers/offer.py` (rm_submit_report)
- **Specs**: `HP-03-001`, `HP-04-001`, `HP-06-002`
- **Tests**: Expand `test/api/v2/backend/test_handlers.py`, verify with `test/scripts/test_receive_report_demo.py`
- **Note**: Implementation complete. Demo test still fails due to infrastructure issues (actor lookup by short ID not working, init_actor_ios not being called in right place). These are separate tasks beyond handler implementation.

#### 0.2 Implement validate_report Handler Business Logic
- [x] Extract VulnerabilityReport from ValidateReport activity (as_Accept of as_Offer)
- [x] Update report status to VALID in data layer
- [x] Create VulnerabilityCase containing the validated report
- [x] Store the VulnerabilityCase in data layer
- [x] Create a Create(VulnerabilityCase) activity and add to actor's outbox
- [x] Log INFO level: report validated, case created, case ID
- [x] Handle case where report doesn't exist (error condition)
- **Files**: `vultron/api/v2/backend/handlers.py` (validate_report function)
- **Reference**: `vultron/api/v2/backend/_old_handlers/accept.py` (rm_validate_report)
- **Specs**: `HP-03-001`, `HP-04-001`, `HP-06-002`
- **Tests**: Expand `test/api/v2/backend/test_handlers.py`, verify with `test/scripts/test_receive_report_demo.py`
- **Note**: Implementation complete. Uses rehydration to get full objects, sets offer and report status, creates case, generates CreateCase activity, and adds to actor outbox.

#### 0.3 Implement Status Tracking System
- [ ] Design status storage approach (using data layer or separate status table)
- [ ] Implement OfferStatus tracking (PENDING, ACCEPTED, REJECTED)
- [ ] Implement ReportStatus tracking (per RM state machine: RECEIVED, VALID, INVALID, CLOSED)
- [ ] Create status query/update helper functions
- [ ] Integrate status checks into handlers for idempotency
- **Files**: New `vultron/api/v2/data/status.py` or extend existing
- **Reference**: `vultron/api/v2/backend/_old_handlers/accept.py` (OfferStatus, ReportStatus, set_status)
- **Specs**: `HP-07-001`, `HP-07-002` (idempotency requirements)
- **Tests**: `test/api/v2/data/test_status.py`

#### 0.4 Implement Outbox Processing
- [ ] Ensure Create activities are added to actor's outbox collection
- [ ] Implement outbox retrieval via data layer
- [ ] Add logging for outbox operations at INFO level
- [ ] Verify outbox items are persisted correctly
- **Files**: `vultron/api/v2/data/actor_io.py`, `vultron/api/v2/backend/handlers.py`
- **Reference**: Existing `actor_io.py` structure
- **Specs**: Related to response generation (deferred details)
- **Tests**: `test/api/v2/data/test_actor_io.py`

#### 0.5 Implement Remaining Report Handlers
- [x] close_report: Update report status to CLOSED
- [x] invalidate_report: Update report status to INVALID, update offer status
- [x] ack_report: Acknowledge report receipt (log and possibly update status)
- [x] create_report: Store new report in data layer
- **Files**: `vultron/api/v2/backend/handlers.py`
- **Reference**: `_old_handlers/reject.py` (rm_invalidate_report), `_old_handlers/create.py`
- **Specs**: `HP-03-001`, `HP-04-001`
- **Tests**: `test/api/v2/backend/test_handlers.py`
- **Status**: COMPLETE. All four handlers implemented with full business logic including rehydration, status updates, activity storage, and proper error handling.

#### 0.6 Fix receive_report_demo.py Test
- [ ] Remove `@pytest.mark.xfail` from test once handlers implemented
- [ ] Verify all demo workflow steps execute correctly
- [ ] Add assertions for expected side effects (reports stored, cases created, outbox populated)
- [ ] Document any remaining limitations or known issues
- **Files**: `test/scripts/test_receive_report_demo.py`
- **Exit Criteria**: Test passes without xfail marker

### Phase 1: Critical Infrastructure & Validation (HIGH PRIORITY)

#### 1.1 Request Validation Middleware
- [ ] Create middleware or dependency for Content-Type validation
  - [ ] Accept `application/activity+json` (MUST)
  - [ ] Accept `application/ld+json; profile="..."` (MUST)
  - [ ] Return HTTP 415 for non-conforming types
- [ ] Implement 1MB payload size limit check
  - [ ] Return HTTP 413 for oversized payloads
  - [ ] Log oversized requests at WARNING level
- [ ] Add URI validation using Pydantic validators
  - [ ] Validate `as_id` field format
  - [ ] Validate URI schemes (http, https, urn)
  - [ ] Syntax-only check (no reachability)
- **Files**: `vultron/api/v2/routers/actors.py`, new middleware
- **Specs**: `IE-03-001/002`, `MV-05-001`, `MV-06-001`, `MV-07-001/002`
- **Tests**: `test/api/v2/routers/test_actors_validation.py`

#### 1.2 Standardized HTTP Error Responses
- [ ] Create custom exception handler for `VultronError` hierarchy
- [ ] Implement JSON error response format:
  ```json
  {
    "status": <HTTP_CODE>,
    "error": "<ERROR_TYPE>",
    "message": "<HUMAN_READABLE>",
    "activity_id": "<ID_IF_AVAILABLE>"
  }
  ```
- [ ] Update all exception classes to include context attributes
  - [ ] Add `activity_id: str | None` field
  - [ ] Add `actor_id: str | None` field
  - [ ] Add `original_exception: Exception | None` for wrapping
- [ ] Map error types to HTTP status codes:
  - [ ] Validation errors → 400/422 (WARNING log)
  - [ ] Protocol errors → 400-499 (WARNING log)
  - [ ] System errors → 500-599 (ERROR log with stack trace)
- [ ] Register exception handlers in FastAPI app
- **Files**: `vultron/api/v2/errors.py`, `vultron/api/v2/app.py`
- **Specs**: `EH-04-001`, `EH-05-001`, `EH-06-001`
- **Tests**: `test/api/v2/test_error_responses.py`

#### 1.3 Health Check Endpoints
- [ ] Create `vultron/api/v2/routers/health.py`
- [ ] Implement `/health/live` (liveness probe)
  - [ ] Return 200 if process running
  - [ ] Minimal logic (just proves process alive)
- [ ] Implement `/health/ready` (readiness probe)
  - [ ] Check data layer connectivity
  - [ ] Return 200 if ready, 503 if not
  - [ ] Include status details in response body
- [ ] Register health router in main app
- [ ] Add integration tests
- **Files**: New router file, update `app.py`
- **Specs**: `OB-05-001`, `OB-05-002`
- **Tests**: `test/api/v2/routers/test_health.py`

### Phase 2: Observability & Reliability (HIGH PRIORITY)

#### 2.1 Structured Logging Implementation
- [ ] Create logging configuration module
  - [ ] Define structured log format (JSON or key-value)
  - [ ] Include fields: timestamp (ISO 8601), level, component, activity_id, actor_id, message
  - [ ] Configure formatters for console and file output
- [ ] Implement correlation ID context manager
  - [ ] Use activity `as_id` as correlation ID
  - [ ] Propagate through all processing stages
  - [ ] Include in all log entries
- [ ] Add lifecycle logging at INFO level:
  - [ ] Activity received (with activity_id, actor_id)
  - [ ] Activity validated (with semantic type)
  - [ ] Activity queued for processing
  - [ ] Handler invoked (with handler name)
  - [ ] State transitions (before → after)
  - [ ] Processing completed (with result)
- [ ] Implement proper log level usage:
  - [ ] DEBUG: Diagnostic details, payload contents
  - [ ] INFO: Lifecycle events, state changes
  - [ ] WARNING: Recoverable issues, validation warnings, 4xx errors
  - [ ] ERROR: Unrecoverable failures, handler exceptions, 5xx errors
  - [ ] CRITICAL: System-level failures (not currently used)
- [ ] Add audit trail logging:
  - [ ] State transition logs (case states, embargo states)
  - [ ] Authorization decisions (when auth implemented)
  - [ ] Data access operations
- **Files**: New `vultron/api/v2/logging_config.py`, update handlers
- **Specs**: `OB-01-001`, `OB-02-001`, `OB-03-001`, `OB-04-001`, `OB-06-001/002/003`
- **Tests**: `test/api/v2/test_logging.py` (use caplog fixture)

#### 2.2 Idempotency and Duplicate Detection
- [ ] Design activity ID tracking mechanism
  - [ ] Option A: In-memory cache with TTL (simple, testing)
  - [ ] Option B: TinyDB table with timestamp (persistent)
  - [ ] Decide based on requirements (start with Option A)
- [ ] Implement duplicate detection logic
  - [ ] Check activity ID before processing
  - [ ] Return HTTP 202 immediately for duplicates (no reprocessing)
  - [ ] Log duplicate detection at INFO level
- [ ] Add TTL-based cleanup
  - [ ] Background task to expire old activity IDs
  - [ ] Configurable retention period (e.g., 24 hours)
- [ ] Handle edge cases
  - [ ] Different activities with same ID (error scenario)
  - [ ] Concurrent submissions of same activity
- [ ] Add integration tests
  - [ ] Submit same activity twice, verify second returns 202 without reprocessing
  - [ ] Verify logs show duplicate detection
  - [ ] Test cleanup after TTL expiration
- **Files**: `vultron/api/v2/routers/actors.py`, new `deduplication.py` module
- **Specs**: `IE-10-001`, `IE-10-002`, `MV-08-001`
- **Tests**: `test/api/v2/test_idempotency.py`

### Phase 3: Testing Infrastructure & Coverage (HIGH PRIORITY)

#### 3.1 Configure Test Coverage Enforcement
- [ ] Add pytest-cov configuration to `pyproject.toml`
  - [ ] Set minimum coverage threshold: 80% overall
  - [ ] Set critical path coverage: 100% for validation, semantic extraction, dispatch, error handling
  - [ ] Configure coverage report formats (terminal, HTML, XML)
- [ ] Run baseline coverage measurement
  - [ ] Execute `pytest --cov=vultron --cov-report=term-missing`
  - [ ] Document current coverage percentages
  - [ ] Identify coverage gaps
- [ ] Add coverage checks to CI pipeline
  - [ ] Fail build if coverage drops below thresholds
  - [ ] Generate and publish coverage reports
- **Files**: `pyproject.toml`, CI configuration
- **Specs**: `TB-02-001`, `TB-02-002`
- **Tests**: Configuration only

#### 3.2 Create Integration Test Suite
- [ ] Create `test/api/v2/integration/` directory structure
- [ ] Add pytest markers for test categorization
  - [ ] `@pytest.mark.unit` for isolated tests
  - [ ] `@pytest.mark.integration` for full-stack tests
  - [ ] Update `pyproject.toml` with marker definitions
- [ ] Implement end-to-end inbox flow tests
  - [ ] Test: Valid activity → 202 → handler invoked
  - [ ] Test: Invalid Content-Type → 415
  - [ ] Test: Oversized payload → 413
  - [ ] Test: Malformed activity → 422
  - [ ] Test: Unknown actor → 404
  - [ ] Test: Duplicate activity → 202 (no reprocessing)
  - [ ] Test: Async processing with BackgroundTasks
- [ ] Implement semantic extraction integration tests
  - [ ] Test all 47 semantic patterns with real activities
  - [ ] Verify correct handler invocation for each
  - [ ] Test pattern ordering (specific before general)
- [ ] Implement error handling integration tests
  - [ ] Test all HTTP error codes (400, 404, 405, 413, 415, 422, 500)
  - [ ] Verify error response format
  - [ ] Verify error logging
- **Files**: New `test/api/v2/integration/` directory
- **Specs**: `TB-03-001`, `TB-03-002`, `TB-03-003`, `TB-04-003`
- **Tests**: Multiple new integration test files

#### 3.3 Enhance Test Infrastructure
- [ ] Create test data factories
  - [ ] Factory for `VulnerabilityReport` objects
  - [ ] Factory for `VulnerabilityCase` objects
  - [ ] Factory for ActivityStreams activities (Create, Accept, Reject, etc.)
  - [ ] Factory for Actor objects
  - [ ] Use realistic domain data in tests
- [ ] Centralize fixtures in root `conftest.py`
  - [ ] Shared `client` fixture (FastAPI TestClient)
  - [ ] Shared `datalayer` fixture with automatic cleanup
  - [ ] Shared `test_actor` fixture
  - [ ] Activity factory fixtures
- [ ] Improve test isolation
  - [ ] Ensure database cleared between tests
  - [ ] Ensure no global state leakage
  - [ ] Add markers for parallel-safe tests
- [ ] Document test patterns and conventions
  - [ ] Add testing guide to documentation
  - [ ] Include examples of good test structure
- **Files**: `test/conftest.py`, `test/factories.py`, new documentation
- **Specs**: `TB-05-001`, `TB-05-002`, `TB-05-004`, `TB-06-001`
- **Tests**: Infrastructure and fixtures

### Phase 4: Handler Business Logic (DEFERRED)

**Status**: LOWER PRIORITY - Focus on infrastructure first

**Rationale**: Handler business logic implementation is deferred until after Phase 1-3 are complete. Current stubs are sufficient to validate that:
1. Activities are correctly validated at the API layer
2. Semantic extraction correctly identifies message types
3. Dispatch routing invokes the correct handler function
4. Error handling works correctly at each stage

Once the core infrastructure is solid and well-tested, we can systematically implement business logic for each of the 47 handlers.

**Future Work**:
- [ ] Design handler business logic patterns
  - [ ] State persistence patterns
  - [ ] State transition validation
  - [ ] Response generation triggers
- [ ] Implement report management handlers (8 handlers)
  - [ ] create_report, submit_report, validate_report, invalidate_report
  - [ ] ack_report, close_report, read_report, update_report
- [ ] Implement case management handlers (10 handlers)
  - [ ] create_case, add_report_to_case, remove_report_from_case
  - [ ] update_case_status, close_case, reopen_case
  - [ ] add_case_participant, remove_case_participant
  - [ ] transfer_case_ownership, merge_cases
- [ ] Implement embargo management handlers (12 handlers)
  - [ ] create_embargo, update_embargo_status, terminate_embargo
  - [ ] add_embargo_event, remove_embargo_event, announce_embargo_event
  - [ ] invite_to_embargo, accept_embargo_invitation, reject_embargo_invitation
  - [ ] notify_embargo_status, request_embargo_extension, handle_embargo_violation
- [ ] Implement actor management handlers (9 handlers)
  - [ ] suggest_actor_to_case, accept_actor_suggestion, reject_actor_suggestion
  - [ ] invite_actor_to_case, accept_case_invitation, reject_case_invitation
  - [ ] offer_case_ownership, accept_ownership_offer, reject_ownership_offer
- [ ] Implement metadata handlers (8 handlers)
  - [ ] add_case_note, update_case_note, remove_case_note
  - [ ] add_case_participant_status, get_case_participants
  - [ ] add_status_object, update_status_object, remove_status_object
- [ ] Add comprehensive unit tests for each handler
- **Files**: `vultron/api/v2/backend/handlers.py` and supporting modules
- **Specs**: `HP-03-001`, `HP-04-001`, `HP-06-001`
- **Tests**: Expand `test/api/v2/backend/test_handlers.py`

### Phase 5: Response Generation (DEFERRED)

**Status**: LOWER PRIORITY - Requires Phase 4 completion

**Rationale**: Response generation requires understanding handler business logic outcomes. Once handlers can make decisions about accepting/rejecting activities, we can implement the response generation system.

**Dependencies**:
- Requires handler business logic (Phase 4)
- Requires outbox processing implementation
- Requires response delivery mechanism

**Future Work**:
- [ ] Design response activity patterns
  - [ ] Map handler outcomes to response types
  - [ ] Define `inReplyTo` correlation rules
  - [ ] Design error extension format
- [ ] Implement response generation
  - [ ] Accept response builder
  - [ ] Reject response builder
  - [ ] TentativeReject response builder
  - [ ] Update response builder
  - [ ] Error response builder with extensions
- [ ] Implement response correlation
  - [ ] Add `inReplyTo` field to all responses
  - [ ] Track original activity ID
  - [ ] Prevent duplicate responses
- [ ] Implement response delivery
  - [ ] Queue responses to actor outbox
  - [ ] Process outbox for delivery
  - [ ] Handle delivery failures
  - [ ] Retry logic with backoff
- [ ] Add tests
  - [ ] Unit tests for response builders
  - [ ] Integration tests for response delivery
  - [ ] Test duplicate response prevention
- **Files**: New `vultron/api/v2/backend/response_builder.py`, update handlers
- **Specs**: `RF-02-001`, `RF-03-001`, `RF-04-001`, `RF-05-001`, `RF-06-001`, `RF-08-001`
- **Tests**: `test/api/v2/backend/test_response_generation.py`

### Phase 6: Code Quality & Documentation (MEDIUM PRIORITY)

#### 6.1 Code Style Compliance
- [ ] Verify Black formatting compliance
  - [ ] Run `black --check vultron/`
  - [ ] Fix any formatting issues
- [ ] Verify import organization per spec
  - [ ] Standard library first
  - [ ] Third-party packages second
  - [ ] Local modules third
  - [ ] No wildcard imports
- [ ] Check for circular imports
  - [ ] Core modules should not import from API layer
  - [ ] Document module dependency graph
- [ ] Run static type checking
  - [ ] Execute `mypy vultron/`
  - [ ] Fix type errors
  - [ ] Add missing type hints
- **Files**: Entire codebase
- **Specs**: `CS-01-001` through `CS-05-001`
- **Tests**: Linting in CI

#### 6.2 Documentation Updates
- [ ] Update API documentation
  - [ ] Document inbox endpoint behavior
  - [ ] Document health check endpoints
  - [ ] Document error response formats
  - [ ] Add request/response examples
- [ ] Update specification compliance matrix
  - [ ] Document which specs are implemented
  - [ ] List known gaps and limitations
  - [ ] Update as implementation progresses
- [ ] Add inline documentation
  - [ ] Docstrings for all public functions
  - [ ] Docstrings for all classes
  - [ ] Complex logic explanations where needed
- [ ] Create troubleshooting guide
  - [ ] Common error scenarios
  - [ ] Debugging tips
  - [ ] Log analysis examples
- **Files**: `docs/` directory, inline docstrings
- **Specs**: General documentation requirements
- **Tests**: Documentation builds successfully

### Phase 7: Performance & Scalability (FUTURE)

**Status**: DEFERRED - Post-research phase

**Rationale**: This is a research prototype. Performance optimization is not a priority until the protocol design is validated and we have real-world usage data.

**Future Considerations**:
- [ ] Evaluate async dispatcher implementation
  - [ ] Queue-based processing (Redis, RabbitMQ)
  - [ ] Worker pool architecture
  - [ ] Horizontal scaling support
- [ ] Database optimization
  - [ ] Replace TinyDB with production database
  - [ ] Add indexes for common queries
  - [ ] Implement connection pooling
- [ ] Caching strategies
  - [ ] Actor metadata caching
  - [ ] Activity deduplication cache
  - [ ] Response template caching
- [ ] Rate limiting
  - [ ] Per-actor rate limits
  - [ ] Global rate limits
  - [ ] Backpressure mechanisms
- [ ] Monitoring and metrics
  - [ ] Prometheus metrics export
  - [ ] Request latency tracking
  - [ ] Queue depth monitoring
  - [ ] Error rate alerting
- **Files**: TBD based on performance requirements
- **Specs**: Not yet specified
- **Tests**: Performance test suite

## Implementation Priorities & Sequencing

### Immediate Focus (Current Sprint)
**Goal**: Achieve specification compliance for inbox endpoint and request handling

1. **Phase 1.1**: Request validation middleware (1-2 days)
2. **Phase 1.2**: Standardized error responses (1-2 days)
3. **Phase 1.3**: Health check endpoints (0.5 days)
4. **Phase 3.1**: Configure test coverage enforcement (0.5 days)

**Exit Criteria**: Inbox endpoint meets all IE-* and MV-* spec requirements with proper error handling

### Short Term (Next 2-3 Sprints)
**Goal**: Complete observability and reliability features; achieve test coverage targets

1. **Phase 2.1**: Structured logging with correlation IDs (2-3 days)
2. **Phase 2.2**: Idempotency and duplicate detection (1-2 days)
3. **Phase 3.2**: Integration test suite (3-4 days)
4. **Phase 3.3**: Enhanced test infrastructure and factories (2-3 days)

**Exit Criteria**: 
- All OB-* spec requirements met
- 80%+ test coverage overall
- 100% coverage on critical paths (validation, semantic extraction, dispatch, error handling)

### Medium Term (Following Sprints)
**Goal**: Code quality and documentation

1. **Phase 6.1**: Code style compliance and type checking (1-2 days)
2. **Phase 6.2**: Documentation updates (2-3 days)

**Exit Criteria**:
- All CS-* spec requirements met
- Comprehensive documentation for API consumers
- Specification compliance matrix complete

### Long Term (Post-Research Phase)
**Goal**: Production readiness (if/when needed)

1. **Phase 4**: Handler business logic implementation (10-15 days)
2. **Phase 5**: Response generation system (5-7 days)
3. **Phase 7**: Performance optimization (TBD based on requirements)

**Exit Criteria**: System ready for production deployment with full CVD workflow support

## Open Questions & Design Decisions

### Resolved Questions

#### Q1: Async Dispatcher Priority
**Question**: Specs `DR-04-001` and `DR-04-002` recommend async queue-based dispatcher for production. Should this be prioritized now or deferred?

**Decision**: DEFERRED. FastAPI BackgroundTasks already provides async processing at the endpoint level. Downstream processing can remain synchronous until we have performance data indicating need for queue-based architecture.

#### Q2: Test Organization
**Question**: Should we separate unit and integration tests into `test/unit/` and `test/integration/` directories per `TB-04-003`, or use pytest markers?

**Decision**: Use pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`). Simpler to implement and maintain. Can reorganize directory structure later if needed.

#### Q3: URI Validation Scope
**Question**: Spec `MV-05-001` requires URI validation. Should this be syntax-only or include reachability checks?

**Decision**: Syntax-only validation using Pydantic validators. Check for well-formed URIs with acceptable schemes (http, https, urn). No reachability/liveness checks required at this stage.

#### Q4: Handler Implementation Order
**Question**: With 47 handlers to implement, should we prioritize by CVD workflow criticality or by semantic grouping?

**Decision**: DEFER all handler business logic to Phase 4. Focus first on infrastructure: request validation, semantic extraction, dispatch routing, error handling. Verify correct handler invocation without implementing business logic.

#### Q5: Authorization System
**Question**: Multiple specs reference authorization (e.g., `HP-05-001`), but no auth system exists. Should this be specified and implemented?

**Decision**: OUT OF SCOPE for initial implementation. Design system to allow easy auth layer integration later. For now, assume all requests are authorized. Focus on message handling functionality.

### Open Questions

#### Q6: Duplicate Detection Storage
**Question**: Should duplicate detection use in-memory cache (simple, fast, non-persistent) or TinyDB (persistent, survives restarts)?

**Options**:
- Option A: In-memory cache with TTL (e.g., Python dict with timestamps or `cachetools`)
  - Pros: Fast, simple implementation
  - Cons: Lost on restart, not shared across processes
- Option B: TinyDB table with activity IDs and timestamps
  - Pros: Persistent, consistent across restarts
  - Cons: Slower, requires cleanup logic

**Recommendation**: Start with Option A for simplicity. Upgrade to Option B if persistence proves necessary.

#### Q7: Structured Logging Format
**Question**: Should structured logs use JSON format (machine-parseable) or enhanced key-value format (human-readable)?

**Options**:
- JSON format: `{"timestamp": "...", "level": "INFO", "component": "...", "message": "..."}`
- Key-value format: `2026-02-13T16:00:00Z [INFO] component=inbox_handler activity_id=... message=...`

**Recommendation**: JSON format for production parsability. Can add console-friendly formatter for development.

#### Q8: Health Check Ready Conditions
**Question**: What should `/health/ready` check beyond data layer connectivity?

**Considerations**:
- Data layer read/write access
- Disk space availability
- Memory usage thresholds
- Queue depth (if async queue implemented)

**Recommendation**: Start with data layer connectivity check only. Add more checks as system complexity grows.

#### Q9: Test Coverage Enforcement
**Question**: Should coverage enforcement be strict (fail build on any decrease) or threshold-based (fail only below 80%)?

**Recommendation**: Threshold-based initially (80% overall, 100% critical paths). Can tighten to strict enforcement once stable.

#### Q10: Response Generation Timing
**Question**: When Phase 5 is implemented, should response generation be synchronous (blocking handler) or async (queued after handler returns)?

**Consideration**: Affects handler protocol design and testing approach.

**Recommendation**: Defer decision until Phase 4 handler logic is better understood. Likely async to maintain fast handler execution.

---

## Notes

**Research Prototype Context**: This is a research project exploring federated CVD protocol design. The focus is on:
- Demonstrating protocol feasibility
- Validating behavior tree modeling approach
- Establishing ActivityStreams vocabulary for CVD
- Building foundation for future interoperability

Performance optimization and production hardening are explicitly **not priorities** at this stage. The goal is correctness and specification compliance, not scale.
