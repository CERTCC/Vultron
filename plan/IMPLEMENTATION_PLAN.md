# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-12

## Overview

This implementation plan tracks the development of the Vultron API v2 inbox handler system against the detailed specifications in `specs/*`. The system has a solid foundation with semantic pattern matching, message dispatching, and handler stubs, but requires substantial work to meet all specification requirements for production readiness.

### Current Status

**Completed:**
- [x] Core dispatcher architecture (`behavior_dispatcher.py`) with `DirectActivityDispatcher`
- [x] Semantic extraction system (`semantic_map.py`, `activity_patterns.py`)
- [x] All 47 MessageSemantics handlers registered in `semantic_handler_map.py`
- [x] Basic inbox endpoint at `POST /actors/{actor_id}/inbox/`
- [x] Background task processing infrastructure
- [x] Unit tests for dispatcher and semantic matching

**In Progress / Incomplete:**
- [ ] Handler implementations are stubs (return None)
- [ ] Limited request validation
- [ ] Missing health check endpoints
- [ ] No idempotency/duplicate detection
- [ ] No response generation logic
- [ ] Limited integration tests

**Critical Issues:**
- [ ] **Bug in `verify_semantics` decorator** - Missing `return wrapper` statement in `handlers.py:53`

## Prioritized Task List

### Phase 1: Critical Fixes and Core Infrastructure

#### 1. FIX CRITICAL BUG: Repair `verify_semantics` decorator
- [x] Fix missing `return wrapper` statement in `handlers.py:53`
- [x] Verify decorator properly validates semantic types
- [x] Add unit test to catch this regression
- **File**: `vultron/api/v2/backend/handlers.py:53`
- **Priority**: CRITICAL - blocks all semantic validation
- **Spec**: `HP-02-001`

#### 2. Implement Request Validation
- [ ] Add Content-Type validation (application/activity+json, application/ld+json)
- [ ] Implement 1MB payload size limit
- [ ] Add HTTP 413 response for oversized payloads
- [ ] Add HTTP 415 response for unsupported Content-Type
- [ ] Ensure HTTP 422 includes detailed validation errors
- **File**: `vultron/api/v2/routers/actors.py`
- **Specs**: `IE-03-001`, `IE-03-002`, `MV-06-001`, `MV-07-001`

#### 3. Create Health Check Endpoints
- [ ] Create `vultron/api/v2/routers/health.py`
- [ ] Implement `/health/live` endpoint (returns 200 if process running)
- [ ] Implement `/health/ready` endpoint (checks dependencies)
- [ ] Register health router in `vultron/api/v2/app.py`
- [ ] Add integration tests for health endpoints
- **Specs**: `OB-05-001`, `OB-05-002`

#### 4. Enhance Error Handling
- [ ] Add validation-specific exception classes to `vultron/api/v2/errors.py`
- [ ] Ensure all exceptions include activity_id context
- [ ] Ensure all exceptions include actor_id context
- [ ] Implement standardized error response format (status, error, message, activity_id)
- [ ] Add unit tests for each exception type
- **File**: `vultron/api/v2/errors.py`
- **Specs**: `EH-01-001` through `EH-06-001`

### Phase 2: Observability and Reliability

#### 5. Implement Structured Logging
- [ ] Add correlation ID tracking using activity ID
- [ ] Log activity received at INFO level
- [ ] Log activity validated at INFO level
- [ ] Log activity queued at INFO level
- [ ] Log handler invoked at INFO level
- [ ] Log state transitions at INFO level
- [ ] Log processing completed at INFO level
- [ ] Use ISO 8601 timestamps in all log entries
- [ ] Include activity_id in all relevant log entries
- [ ] Include actor_id in all relevant log entries
- **Files**: `vultron/api/v2/backend/behavior_dispatcher.py`, `vultron/api/v2/routers/actors.py`
- **Specs**: `OB-02-001`, `OB-03-001`, `OB-04-001`, `OB-06-001`

#### 6. Add Idempotency and Duplicate Detection
- [ ] Implement activity ID tracking mechanism (TinyDB or in-memory cache)
- [ ] Check for duplicate activity IDs before processing
- [ ] Return HTTP 202 for duplicate submissions without reprocessing
- [ ] Add TTL-based cleanup for old activity IDs
- [ ] Log duplicate detection at INFO level
- [ ] Add integration tests for duplicate detection
- **File**: `vultron/api/v2/routers/actors.py`
- **Specs**: `IE-10-001`, `IE-10-002`, `MV-08-001`

### Phase 3: Handler Business Logic

**Note**: Handler business logic implementation is deferred to future work. For now, it is sufficient to have stubs in place as long as we can confirm that an activity arriving at the API endpoint is correctly validated, dispatched, and routed to the correct handler function.

- [ ] Design handler business logic for vulnerability report submission
- [ ] Design handler business logic for report acknowledgment
- [ ] Design handler business logic for report validation/invalidation
- [ ] Design handler business logic for case creation and management
- [ ] Design handler business logic for participant management
- [ ] Design handler business logic for embargo management
- [ ] Design handler business logic for case status updates
- [ ] Implement handler business logic (47 handlers total)
- [ ] Add unit tests for each handler's business logic

### Phase 4: Response Generation

**Note**: Response generation is deferred to future work. Focus first on ensuring correct routing and validation.

- [ ] Design response activity structure per ActivityStreams 2.0
- [ ] Implement Accept response generation
- [ ] Implement Reject response generation
- [ ] Implement TentativeReject response generation
- [ ] Implement Update response generation
- [ ] Implement error response generation
- [ ] Add `inReplyTo` correlation to all responses
- [ ] Implement response delivery to actor inboxes
- [ ] Add duplicate response prevention
- [ ] Add unit tests for response generation
- [ ] Add integration tests for response delivery

### Phase 5: Testing and Validation

#### 13. Create Integration Tests
- [ ] Create `test/api/v2/routers/test_actors_inbox.py`
- [ ] Test full request → validation → dispatch → handler flow
- [ ] Test HTTP 202 for valid requests
- [ ] Test HTTP 400 for bad requests
- [ ] Test HTTP 404 for invalid actor_id
- [ ] Test HTTP 405 for non-POST methods
- [ ] Test HTTP 413 for oversized payloads
- [ ] Test HTTP 415 for unsupported Content-Type
- [ ] Test HTTP 422 for validation failures
- [ ] Test HTTP 500 for internal errors
- [ ] Test idempotency behavior
- [ ] Test duplicate detection
- [ ] Test async background processing
- [ ] Verify logging at each stage
- **Specs**: `IE-01-001` through `IE-10-002`

#### 14. Expand Unit Test Coverage
- [ ] Add tests for all dispatcher protocol requirements (`DR-01-*`)
- [ ] Add tests for all handler lookup requirements (`DR-02-*`)
- [ ] Add tests for all message validation requirements (`MV-*`)
- [ ] Add tests for all semantic extraction requirements (`SE-*`)
- [ ] Add tests for all handler protocol requirements (`HP-*`)
- [ ] Add tests for all error handling requirements (`EH-*`)
- [ ] Verify all tests use descriptive names (`TB-08-001`)
- [ ] Add docstrings to complex tests (`TB-08-002`)

#### 15. Enhance Test Infrastructure
- [ ] Create reusable test fixtures in `conftest.py` (`TB-05-001`)
- [ ] Implement test data factories (`TB-05-002`)
- [ ] Configure pytest markers for unit/integration separation (`TB-04-003`)
- [ ] Set up test database or database mocking (`TB-06-002`)
- [ ] Ensure test isolation and independence (`TB-06-001`)
- [ ] Configure randomized test execution in CI (`TB-06-001`)

#### 16. Achieve Test Coverage Targets
- [ ] Measure current code coverage
- [ ] Achieve 80%+ overall line coverage (`TB-02-001`)
- [ ] Achieve 100% coverage on message validation (`TB-02-002`)
- [ ] Achieve 100% coverage on semantic extraction (`TB-02-002`)
- [ ] Achieve 100% coverage on dispatch routing (`TB-02-002`)
- [ ] Achieve 100% coverage on error handling (`TB-02-002`)
- [ ] Configure CI to fail on coverage regression
- [ ] Generate coverage reports in CI pipeline

## Open Questions and Considerations

### 1. Async Dispatcher Priority
**Question**: Specs `DR-04-001` and `DR-04-002` recommend async queue-based dispatcher for production. Should this be prioritized now or deferred until scaling requirements are clearer?

**Answer**: Async processing at the FastAPI endpoint where a background task summons the inbox handler is already implemented. Everything downstream of that can be synchronous for now until we have a clearer idea of performance requirements.

### 2. Test Organization
**Question**: Should we separate unit and integration tests into `test/unit/` and `test/integration/` directories per `TB-04-003`, or use pytest markers?

**Answer**: pytest markers are sufficient for now.

### 3. URI Validation Scope
**Question**: Spec `MV-05-001` requires URI validation. Should this be syntax-only or include reachability checks?

**Answer**: This is a format check, not a liveness check. We just want to ensure that the URI is well-formed and uses an acceptable scheme (http, https, urn, etc.). We do not need to perform reachability checks at this time.

### 4. Handler Implementation Order
**Question**: With 47 handlers to implement, should we prioritize by CVD workflow criticality or by semantic grouping?

**Answer**: Do not implement any handler business logic at this time. Focus on ensuring that the correct handler is invoked for each semantic type and that the overall request validation and dispatch flow works correctly. We can implement handler logic in a later phase once the core infrastructure is solid.

### 5. Authorization System
**Question**: Multiple specs reference authorization (e.g., `HP-05-001`), but no auth system exists yet. Should this be specified and implemented as part of this phase?

**Answer**: Authorization is out of scope for the initial implementation. We can design the system to allow for easy integration of an auth layer in the future, but for now we will assume that all requests are authorized and focus on the core message handling functionality.

## Next Steps

### Immediate Actions (This Week)
- [ ] Fix the critical bug in `verify_semantics` decorator
- [ ] Implement request validation (Phase 1, items 2-4)
- [ ] Add health check endpoints

### Short Term (Current Sprint)
- [ ] Complete all Phase 1 tasks
- [ ] Complete all Phase 2 tasks
- [ ] Begin integration test development

### Medium Term (Next 2-3 Sprints)
- [ ] Complete integration test suite
- [ ] Achieve test coverage targets
- [ ] Document any remaining open questions

### Long Term
- [ ] Evaluate async dispatcher implementation needs
- [ ] Design and implement handler business logic
- [ ] Build response generation system
- [ ] Consider metrics and advanced observability features
- [ ] Plan for production deployment requirements

---

**Note**: This is a research prototype. Focus is on demonstrating protocol feasibility and correctness rather than production-scale performance optimization.
