# Vultron API v2 Implementation Notes

**Last Updated**: 2026-02-12

## Architecture Overview

The Vultron API v2 inbox handler system is built on several key architectural components that work together to process incoming ActivityStreams messages for Coordinated Vulnerability Disclosure (CVD):

### Core Components

1. **Semantic Extraction** (`vultron/semantic_map.py`, `vultron/activity_patterns.py`)
   - Pattern-based matching system using ActivityStreams type and object type combinations
   - Maps incoming activities to one of 47 `MessageSemantics` enum values
   - Handles complex nested object structures with fallback logic
   - Performance consideration: Pattern matching is O(n) where n = number of registered patterns

2. **Dispatcher Architecture** (`vultron/behavior_dispatcher.py`)
   - Current implementation: `DirectActivityDispatcher` (synchronous)
   - Alternative considered: Async queue-based dispatcher (see specs `DR-04-001`, `DR-04-002`)
   - Uses handler registry pattern with semantic-to-handler mapping
   - Background task processing via FastAPI's `BackgroundTasks`

3. **Handler System** (`vultron/api/v2/backend/handlers.py`)
   - 47 handler functions corresponding to each `MessageSemantics` value
   - All currently stubs returning None (needs implementation)
   - Uses `verify_semantics` decorator for validation ⚠️ **CRITICAL BUG**: Missing `return wrapper` on line 53
   - Designed for idempotency per spec `HP-07-001`

4. **Inbox Endpoint** (`vultron/api/v2/routers/actors.py`)
   - FastAPI route: `POST /actors/{actor_id}/inbox/`
   - Accepts ActivityStreams JSON-LD activities
   - Returns HTTP 200 immediately, processes in background
   - Needs: Content-Type validation, size limits, idempotency checking

## Critical Issues

### Bug in `verify_semantics` Decorator

**Location**: `vultron/api/v2/backend/handlers.py:53`

**Problem**: The decorator function is missing a `return wrapper` statement, causing it to return `None` instead of the decorated function. This breaks all handler semantic validation.

**Current Code**:
```python
def verify_semantics(expected: MessageSemantics):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(activity: dict, *args, **kwargs):
            # ... validation logic ...
            return func(activity, *args, **kwargs)
        # MISSING: return wrapper
    return decorator
```

**Fix Required**: Add `return wrapper` as the last line of the `decorator` function.

**Impact**: Without this fix, all decorated handler functions will fail silently. This blocks semantic validation testing and proper handler dispatch.

## Technical Insights

### Semantic Matching System

The semantic extraction uses a two-level matching strategy:

1. **Direct Pattern Match**: Check registered patterns for (activity_type, object_type) combinations
2. **Fallback Logic**: Handle activities without objects or nested object structures

**Optimization Consideration**: The current linear search through patterns could become a bottleneck with many patterns. Consider using a dictionary-based lookup if performance testing shows issues. The specs require <100ms response time (`IE-05-001`), and semantic extraction is on the critical path.

**Edge Case**: Activities with nested objects (e.g., `Announce` with embedded `Create` activity) need special handling. The current implementation extracts the inner activity's semantics, which may not always be correct for all CVD scenarios.

### Handler Implementation Strategy

When implementing the 47 handler stubs, consider this dependency order:

**Priority 1 - Foundation**:
- `create_report` - Creates initial vulnerability report
- `validate_report` - Marks report as valid (RM state transition)
- `create_case` - Creates CVD case from validated report

**Priority 2 - Core Workflow**:
- `activate_case` - Begins active case management
- `add_participant` / `invite_participant` - Participant management
- `join_case` / `accept_invitation` - Participant acceptance

**Priority 3 - State Management**:
- `deploy_fix` / `propose_fix` - Fix lifecycle
- `read_embargo` / `propose_embargo` - Embargo management
- `close_report` / `close_case` - Termination

**Priority 4 - Communication**:
- All `REJECT`, `TENTATIVE_REJECT`, `UNDO`, and informational handlers

### Integration with Case State Machines

The Vultron protocol uses three interacting state machines (see ADR-0002):

1. **Report Management (RM)**: `vultron/case_states/states.py`
2. **Embargo Management (EM)**: `vultron/case_states/states.py`
3. **Case State (CS)**: `vultron/case_states/patterns.py`

**Key Consideration**: Handlers must update the appropriate state machine(s) and ensure state transitions are valid. Invalid transitions should be rejected with `TentativeReject` per spec `RF-02-001`.

**Testing Challenge**: Integration tests must verify that handler actions properly transition state machines. This requires:
- Setting up initial states
- Calling handlers with appropriate activities
- Verifying final states match expected transitions
- Checking that response activities are generated correctly

### Behavior Tree Integration

The Vultron protocol models processes as Behavior Trees (ADR-0002, ADR-0003):

- BT nodes in `vultron/bt/` implement CVD process logic
- Factory methods (`vultron/bt/base/factory.py`) create common node types
- Handler actions may need to trigger BT execution for complex workflows

**Note**: The current inbox handler implementation doesn't directly integrate with BTs. This may be needed for complex multi-step processes like case creation workflows that involve multiple checks and state transitions.

## Testing Strategy

### Current Test Coverage

**Strong Coverage**:
- Dispatcher unit tests (`test/test_behavior_dispatcher.py`) - 100% coverage
- Semantic pattern matching (`test/test_semantic_activity_patterns.py`) - comprehensive
- Handler map registration (`test/test_semantic_handler_map.py`) - complete

**Missing Coverage**:
- Integration tests for full inbox flow (request → dispatch → handler → response)
- Handler function unit tests (all are stubs)
- Error handling and validation tests
- Performance tests for <100ms requirement
- Idempotency and duplicate detection tests

### Test Organization Recommendation

**Option 1: Directory-based** (per spec `TB-04-003`):
```
test/
  unit/
    test_dispatcher.py
    test_semantic_extraction.py
    test_handlers.py
  integration/
    test_inbox_endpoint.py
    test_full_workflow.py
  performance/
    test_response_time.py
```

**Option 2: Marker-based** (current approach):
```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.performance
```

**Recommendation**: Use directory-based organization for clearer test discovery and faster selective test execution. This aligns with the project's modular structure.

## Dependencies and Data Flow

### Request Processing Flow

```
1. FastAPI receives POST /actors/{actor_id}/inbox/
   ↓
2. Request validation (Content-Type, size, schema)
   ↓
3. Idempotency check (duplicate activity ID?)
   ↓ (if new)
4. Background task: inbox_handler.handle_inbox_activity()
   ↓
5. Semantic extraction: activity → MessageSemantics
   ↓
6. Dispatcher: MessageSemantics → handler function
   ↓
7. Handler: execute business logic, update state
   ↓
8. Response generation: create Accept/Reject/TentativeReject
   ↓
9. Outbox: queue response for delivery
```

Note that present implementation is only required to confirm that 7 is reached,
business logic, update state, response generation, and outbox are out of scope for now.

### Component Dependencies

- **Handlers** depend on:
  - State machines (`vultron/case_states/`)
  - Data layer (TinyDB via `vultron/api/v2/backend/data.py`)
  - Response generator (not yet implemented)
  
- **Dispatcher** depends on:
  - Semantic extraction system
  - Handler registry
  - Error handling system

- **Inbox endpoint** depends on:
  - Dispatcher
  - Idempotency tracking (not yet implemented)
  - Background task system

## Deployment Considerations

### Synchronous vs. Asynchronous Dispatcher

**Current**: `DirectActivityDispatcher` (synchronous)
- Simple, easy to test
- Processes activities in FastAPI background task
- Sufficient for research prototype

**Alternative**: Async queue-based dispatcher (specs `DR-04-001`, `DR-04-002`)
- Better for production scale
- Allows distributed processing
- Requires queue infrastructure (Redis, RabbitMQ, etc.)
- More complex error handling and retry logic

**Recommendation**: Keep synchronous dispatcher until:
1. Performance testing shows bottlenecks
2. Need for distributed processing emerges
3. Production deployment is planned

### Observability Requirements

Per spec `OB-02-001` through `OB-07-001`:

**Required**:
- Structured logging with correlation IDs (activity ID)
- State transition logging
- Error logging with context
- Health check endpoints (`/health/live`, `/health/ready`)

**Optional**:
- Metrics endpoint (`/metrics`) - Prometheus format
- Distributed tracing
- Performance profiling

**Recommendation**: Implement required observability features first. Add metrics endpoint when monitoring strategy is defined.

## Potential Gotchas and Edge Cases

1. **ActivityStreams Profiles**: Spec `IE-03-001` requires support for both `application/activity+json` and `application/ld+json` with proper profile parameters. Content-Type parsing must be robust.

2. **Nested Activities**: Some activities contain other activities as objects (e.g., `Announce{Create{VulnerabilityReport}}`). Semantic extraction must handle these correctly.

3. **Idempotency vs. State Changes**: An activity that's idempotent at the handler level might still cause state transitions. Need to distinguish between "duplicate submission" (return 202) and "valid retry" (process again).

4. **Response Timing**: Spec `RF-07-001` requires that response generation doesn't delay inbox acknowledgment. Background task processing is correct approach, but need to ensure responses are actually generated and delivered.

5. **Authorization Context**: Multiple specs reference authorization (e.g., `HP-05-001`), but no auth system exists. Handlers should be designed with auth placeholders that can be filled in later.

6. **State Machine Validation**: Not all activity sequences are valid. Handlers must validate current state before attempting transitions. Example: Can't `close_case` if case is already closed.

7. **Actor vs. Case Scope**: Some activities operate on actors (e.g., `invite_participant`), others on cases (e.g., `activate_case`). Handler implementation must maintain this distinction.

## Questions for Future Consideration

1. **Handler Transaction Semantics**: Should handler operations be atomic? If a handler fails midway through multiple state updates, how should rollback work?

2. **Response Delivery Guarantees**: What happens if response delivery fails? Should there be retries? Dead letter queue?

3. **Multi-Actor Coordination**: When multiple actors need to agree (e.g., embargo terms), how are conflicts resolved? Does the protocol define consensus mechanisms?

4. **Historical State Queries**: Should the system maintain activity history for audit purposes? If so, where and for how long?

5. **Protocol Version Negotiation**: How will future protocol versions be handled? Should there be a version field in activities?

6. **Error Recovery**: If a handler crashes mid-execution, how is recovery handled? Are activities replayable?

7. **Rate Limiting**: Should there be rate limits on inbox submissions per actor? This isn't in current specs but may be needed for production.

## References

- **ADR-0002**: Model Vultron processes as Behavior Trees
- **ADR-0003**: Build custom Python BT engine
- **ADR-0004**: Use factory methods for BT nodes
- **ADR-0005**: Use ActivityStreams Vocabulary for messages
- **Spec Files**: `specs/*.md` (10 specification documents)
- **CVD Protocol**: [CERT Guide to CVD](https://certcc.github.io/CERT-Guide-to-CVD)
- **ActivityStreams**: [W3C Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/)

---

**Note**: These notes reflect the state of the codebase as of 2026-02-12 and should be updated as implementation progresses.
