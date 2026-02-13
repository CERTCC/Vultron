# Vultron API v2 Implementation Notes

**Last Updated**: 2026-02-13

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
   - **Logging**: Dispatchers log at INFO level for lifecycle events and DEBUG level for full activity payloads (added 2026-02-13)

3. **Handler System** (`vultron/api/v2/backend/handlers.py`)
   - 47 handler functions corresponding to each `MessageSemantics` value
   - All currently stubs returning None (needs implementation)
   - Uses `verify_semantics` decorator for validation (bug fixed 2026-02-12: added missing `return wrapper` statement)
   - Designed for idempotency per spec `HP-07-001`

4. **Inbox Endpoint** (`vultron/api/v2/routers/actors.py`)
   - FastAPI route: `POST /actors/{actor_id}/inbox/`
   - Accepts ActivityStreams JSON-LD activities
   - Returns HTTP 200 immediately, processes in background
   - Needs: Content-Type validation, size limits, idempotency checking

## Technical Insights

### Semantic Matching System

The semantic extraction uses a two-level matching strategy:

1. **Direct Pattern Match**: Check registered patterns for (activity_type, object_type) combinations
2. **Fallback Logic**: Handle activities without objects or nested object structures

**Optimization Consideration**: The current linear search through patterns could become a bottleneck with many patterns. Consider using a dictionary-based lookup if performance testing shows issues. The specs require <100ms response time (`IE-05-001`), and semantic extraction is on the critical path.

**Edge Case**: Activities with nested objects (e.g., `Announce` with embedded `Create` activity) need special handling. The current implementation extracts the inner activity's semantics, which may not always be correct for all CVD scenarios.

### Behavior Tree Integration

The Vultron protocol models processes as Behavior Trees (ADR-0002, ADR-0003):

- BT nodes in `vultron/bt/` implement CVD process logic
- Factory methods (`vultron/bt/base/factory.py`) create common node types
- Handler actions may need to trigger BT execution for complex workflows

**Note**: The current handler stubs are not integrated with BTs. Future work will need to connect handler logic to BT nodes to manage state transitions and multi-step processes but 
this is out of scope at this stage.


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

**Marker-based** (current approach):
```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.performance
```

**Directory-based** (alternative):
```tests/
├── unit/
│   ├── test_behavior_dispatcher.py
│   ├── test_semantic_activity_patterns.py
│   └── test_semantic_handler_map.py
├── integration/
│   └── test_inbox_flow.py
├── performance/
│   └── test_semantic_extraction_latency.py
```

Pros of marker-based:
- Flexible, can run subsets easily
- Less boilerplate
- Easier to maintain as test suite grows
Cons: Requires discipline to use markers correctly

Pros of directory-based:
- Clear separation of test types
- Easier to enforce test organization 
Cons: More boilerplate, harder to run mixed test types

### Test Data Best Practices (learned 2026-02-13)

**Use Proper Domain Objects**: Tests should use realistic domain objects, not simplified mock data. 

**Bad Example**:
```python
activity = as_Create(as_id="act-1", actor="actor-1", object="obj-1")
```

**Good Example**:
```python
report = VulnerabilityReport(name="TEST-001", content="Test report")
activity = as_Create(
    as_id="act-1",
    actor="https://example.org/users/tester",
    object=report
)
```

**Why**: Using proper objects ensures tests validate the full flow including semantic extraction, pattern matching, and handler verification. String-based mock data can hide bugs in type checking and pattern matching code.

**Testing Semantic Types**: Always use the correct `MessageSemantics` value that matches the activity structure. Don't use `MessageSemantics.UNKNOWN` unless specifically testing unknown activity handling. The `@verify_semantics` decorator validates that claimed semantics match actual activity structure.  

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

1. **Decorator Implementation**: The `verify_semantics` decorator initially had a missing `return wrapper` statement (fixed 2026-02-12), which caused all decorated handlers to be `None` instead of callable. This is a common Python decorator gotcha - always ensure decorators return their wrapper function. Added unit test in `test/api/v2/backend/test_handlers.py` to prevent regression.

2. **Circular Import Resolution**: Fixed circular import between `vultron/behavior_dispatcher.py` and `vultron/api/v2/backend/handlers.py` (fixed 2026-02-12). Created `vultron/types.py` to hold shared type definitions (`DispatchActivity` and `BehaviorHandler`), breaking the dependency cycle. All imports updated accordingly.

3. **Multiple Circular Import Issues** (fixed 2026-02-13): Discovered and resolved a more complex circular import chain:
   
   **Problem**: `behavior_dispatcher.py` → `api.v2.errors` → `api.v2.__init__` → `app` → `routers` → `inbox_handler` → `behavior_dispatcher` (circular)
   
   **Solution (Multi-Part)**:
   - **Created `vultron/dispatcher_errors.py`**: Moved `VultronApiHandlerNotFoundError` from `api.v2.errors` to new core module, breaking the circular dependency. Core components should never depend on application layer modules.
   - **Lazy Initialization in `semantic_handler_map.py`**: Converted module-level `SEMANTICS_HANDLERS` dict to lazy initialization via `get_semantics_handlers()` function. Handler imports now happen inside the function, not at module load time. Added caching to avoid repeated initialization.
   - **Backward Compatibility**: `api.v2.errors` now re-exports `VultronApiHandlerNotFoundError` for existing imports. Module-level `SEMANTICS_HANDLERS` still works for backward compatibility.
   
   **Key Lesson**: Core modules (`behavior_dispatcher`, `semantic_handler_map`) should NEVER import from application layer modules (`api.v2`). Use lazy initialization patterns when unavoidable dependencies exist. Always check import chains when adding new imports between modules.

4. **Pattern Matching for String References** (fixed 2026-02-13): The `ActivityPattern.match_field()` method assumed all activity fields were objects with `as_type` attributes, causing `AttributeError` when fields contained string URIs/IDs.
   
   **Problem**: ActivityStreams spec allows both object references (`{"type": "Person", ...}`) and string references (`"https://example.org/users/alice"`). The pattern matching code only handled objects.
   
   **Solution**: Updated `match_field()` in `vultron/activity_patterns.py` to defensively handle strings:
   ```python
   if isinstance(activity_field, str):
       return True  # Can't match on type for URI references
   return pattern_field == getattr(activity_field, "as_type", None)
   ```
   
   This allows pattern matching to work with both inline objects and string references, matching the ActivityStreams 2.0 specification behavior.

5. **Nested Activities**: Some activities contain other activities as objects (e.g., `Announce{Create{VulnerabilityReport}}`). Semantic extraction must handle these correctly.

3. **Idempotency vs. State Changes**: An activity that's idempotent at the handler level might still cause state transitions. Need to distinguish between "duplicate submission" (return 202) and "valid retry" (process again).

4. **Response Timing**: Spec `RF-07-001` requires that response generation doesn't delay inbox acknowledgment. Background task processing is correct approach, but need to ensure responses are actually generated and delivered.

5. **Authorization Context**: Multiple specs reference authorization (e.g., `HP-05-001`), but no auth system exists. Handlers should be designed with auth placeholders that can be filled in later.

6. **State Machine Validation**: Not all activity sequences are valid. Handlers must validate current state before attempting transitions. Example: Can't `close_case` if case is already closed.

7. **Actor vs. Case Scope**: Some activities operate on actors (e.g., `invite_participant`), others on cases (e.g., `activate_case`). Handler implementation must maintain this distinction.

**Note:** Cases are intended to be long-lived "service" Actors themselves. This means that some activities may be sent to the case Actor's inbox rather than the human actor's inbox. This is an important design consideration for handler implementation and state management.

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

## Troubleshooting Guide

### Circular Import Debugging

When encountering circular import errors:

1. **Trace the Import Chain**: Run the failing test/module and note the full import traceback
2. **Identify the Cycle**: Map out which modules are importing from each other
3. **Check Layer Violations**: Look for core modules importing from application layers
4. **Solutions (in order of preference)**:
   - **Refactor**: Move shared code to a neutral location (e.g., `types.py`, `dispatcher_errors.py`)
   - **Lazy Import**: Move imports inside functions where they're used
   - **Dependency Inversion**: Use Protocol interfaces instead of concrete imports

**Common Anti-Patterns**:
- Core module importing from `api.v2.*` (violates layering)
- Module-level initialization of registries that import handlers
- Deeply nested import chains through `__init__.py` files

**Tools**:
```bash
# Visualize import chain
python -c "import sys; sys.path.insert(0, '.'); import vultron.behavior_dispatcher"

# Check for circular imports in a module
python -m pytest --collect-only test/test_module.py
```

### Pattern Matching Failures

When pattern matching raises `AttributeError` on field access:

1. **Check Field Types**: ActivityStreams allows both objects and string URIs
2. **Defensive Coding**: Always use `getattr()` with defaults or type checks
3. **Test with Both Types**: Create test cases with both inline objects and URI references

Example defensive pattern:
```python
if isinstance(field_value, str):
    # Handle URI reference
    return True  # or appropriate fallback
else:
    # Handle inline object
    return field_value.as_type == expected_type
```

---

**Note**: These notes reflect the state of the codebase as of 2026-02-13 and should be updated as implementation progresses.
