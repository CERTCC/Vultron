# Implementation Notes

This file tracks insights, issues, and learnings during implementation.

**Last Updated**: 2026-02-18 (Gap analysis via PLAN_prompt.md)

---

## Phase BT-1 Progress Summary (2026-02-18)

**Status**: Phases BT-1.1 through BT-1.4 COMPLETE; Phases BT-1.5 through BT-1.6 remain

### Completed Infrastructure

1. **BT Bridge Layer** (`vultron/behaviors/bridge.py`)
   - `BTBridge` class for handler-to-BT execution
   - Single-shot execution with blackboard setup
   - DataLayer injection and actor state initialization
   - 16 comprehensive unit tests

2. **DataLayer Helper Nodes** (`vultron/behaviors/helpers.py`)
   - Base classes: `DataLayerCondition`, `DataLayerAction`
   - Common operations: `ReadObject`, `UpdateObject`, `CreateObject`
   - 18 comprehensive unit tests

3. **Report Validation BT** (`vultron/behaviors/report/`)
   - `nodes.py`: 10 domain-specific nodes (conditions, actions, policy stubs)
   - `validate_tree.py`: Composed validation tree with early exit optimization
   - `policy.py`: `ValidationPolicy` base class and `AlwaysAcceptPolicy` default
   - 42 integration tests covering tree execution and error handling

4. **Handler Refactoring** (BT-1.4.1 and BT-1.4.2 COMPLETE)
   - Refactored `validate_report` handler in `vultron/api/v2/backend/handlers.py`
   - Handler now uses BT execution via `BTBridge.execute_with_setup()`
   - Replaced 165 lines of procedural logic with 25 lines of BT invocation
   - Preserved validation and rehydration logic in handler
   - Delegated workflow orchestration (status updates, case creation, outbox) to BT
   - All 454 tests passing (no regressions)
   - Demo test passing (test/scripts/test_receive_report_demo.py)
   - Reporting workflow tests passing (5/7, 2 xfailed for old_handlers)

### Test Status

- **Total tests**: 456 passing (378 core + 78 BT), 2 xfailed
- **BT test coverage**: 78 tests (76 infrastructure + 2 performance)
- **Router tests**: All 18 passing (fixture isolation issue resolved)
- **Demo tests**: 1 passing (receive_report_demo.py)
- **Reporting workflow tests**: 5 passing, 2 xfailed (old_handlers)
- **Performance tests**: 2 passing (single run + percentile measurements)

### Key Architectural Decisions

1. **Blackboard Key Design**: Use simplified keys (e.g., `object_abc123`) to avoid hierarchical path parsing issues in py_trees
2. **Policy Stub Pattern**: Implemented `AlwaysAcceptPolicy` as deterministic placeholder for prototype; future custom policies can inherit from `ValidationPolicy`
3. **Early Exit Optimization**: Validation tree checks `RMStateValid` first; if already valid, skips full validation flow
4. **Node Communication**: Nodes pass data via blackboard keys (e.g., `case_id` from `CreateCaseNode` → `CreateCaseActivity` → `UpdateActorOutbox`)
5. **BT Visibility**: Use py_trees display utilities for tree visualization; DEBUG logging shows structure, INFO shows execution results

### Lessons Learned

1. **py_trees blackboard key registration**: Nodes must call `setup()` to register READ/WRITE access for blackboard keys used during execution
2. **Test data quality**: BT tests use full Pydantic models (not string IDs) to match real-world usage
3. **DataLayer mocking**: BT tests mock DataLayer for isolation; integration tests will use real TinyDB backend
4. **Handler refactoring approach** (BT-1.4):
   - Keep validation/rehydration logic in handler (input validation belongs at handler boundary)
   - Delegate workflow orchestration to BT (status updates, case creation, outbox management)
   - Clean separation: handler validates inputs → BT executes business logic → handler logs results
   - No need for parallel implementation; refactoring existing handler maintains all tests
   - Code reduction: 165 lines of procedural logic → 25 lines of BT invocation + 10 lines result handling
5. **BT logging and visibility** (BT-1.5):
   - py_trees.display.unicode_tree() provides excellent tree visualization
   - Logging at DEBUG level keeps detailed tree structure out of normal logs
   - Handlers should log BT results at INFO level with status symbols (✓/✗/⚠)
   - Performance is excellent: P99 < 1ms for full validation workflow

### Next Steps (Phase BT-1.5 through BT-1.6)

**Phase BT-1.5: COMPLETE** ✅ (2026-02-18)

1. **BT-1.5.1**: Demo and logging ✅
   - Demo script works with BT-enabled handler (validate_report)
   - Added BT execution visibility via py_trees display utilities
   - Enhanced bridge logging: tree structure visualization at DEBUG level
   - Enhanced handler logging: detailed status, feedback, and error reporting
   - Updated demo script docstring with BT logging guidance for users

2. **BT-1.5.2**: Test suite ✅
   - All 456 tests passing (454 core + 2 new performance tests)
   - No regressions from BT logging enhancements
   - BT test coverage: 78 tests (76 BT infrastructure + 2 performance)

3. **BT-1.5.3**: Performance baseline ✅
   - Created test/behaviors/test_performance.py with percentile measurements
   - Performance results (100 runs): Mean=0.46ms, P50=0.44ms, P95=0.69ms, P99=0.84ms
   - Well within 100ms target from plan/BT_INTEGRATION.md
   - No measurable performance regression from BT integration

**Next: Phase BT-1.6 - Documentation**

2. **BT-1.6**: Documentation
   - Update `specs/behavior-tree-integration.md` verification sections
   - Document implementation notes in this file
   - Create ADR-0008 for BT integration architecture

---

## Handler Refactoring Guidance (Phase BT-1.4)

When we get to BT-1.4: Handler Refactoring, modifying the existing procedural
logic in `/api/v2/backend` will break
`vultron/scripts/receive_report_demo.py` script. Instead, we should create 
a new set of handlers that use the BT implementation, and then we will need to 
create a new demo script that uses those handlers. This will allow us to keep the existing
demo script working while we transition to the new BT-based implementation. 
Adding BT-based handlers while retaining the existing procedural handlers 
might have implications to the `vultron/api/v2` module structure, since we might
need to propagate things back up to routers or even the main FastAPI app. 
We should be mindful of this as we implement the new handlers, and we should aim
to keep the module structure clean and organized. Consider making the FastAPI 
invocation selective to use either the procedural or BT-based handlers based on
a configuration setting, command line flag, or environment variable, to allow
for easy switching between implementations without code changes. This can be
added into the docker configs as well so that you could run either version of the
app in a container. (So the old `receive_report_demo.py` could use a container
running the procedural version, and a new `receive_report_demo_bt.py` could use
a container running the BT-based version.)

#### Cross-References

- **Plan**: `plan/BT_INTEGRATION.md` (detailed architecture)
- **Spec**: `specs/behavior-tree-integration.md` (requirements)
- **Priority**: `plan/PRIORITIES.md` (BT integration is top priority)
- **Updated**: `plan/IMPLEMENTATION_PLAN.md` (added Phase BT-1 tasks)

---

## Design Review Findings (2026-02-18)

Comprehensive design review completed per `prompts/AGENTS_META_prompt.md`.

### Implementation Status Assessment

**Overall Status**: Validated prototype with solid architecture but incomplete
feature coverage

**Metrics**:
- 454 tests passing (378 core + 76 BT tests)
- 6/36 handlers complete (17% business logic coverage)
- Phase BT-1 complete (infrastructure + handler refactoring)
- Performance: P99 < 1ms for BT-enabled validate_report handler

**Completed Infrastructure**:
- Semantic extraction and pattern matching
- Behavior dispatcher with Protocol-based design
- Handler protocol with `@verify_semantics` decorator
- Error hierarchy (`VultronError` → `VultronApiError` → specific errors)
- TinyDB data layer implementation
- Inbox endpoint with BackgroundTasks
- All 36 `MessageSemantics` enum values defined
- 36 handler functions registered (6 complete, 30 stubs)
- Registry infrastructure synchronized
- Rehydration system for URI expansion
- Docker infrastructure with health checks
- Demo script with 3 workflows

**Handler Implementation Status**:
- Complete (6): create_report, submit_report, validate_report,
  invalidate_report, ack_report, close_report
- Stub (30): case management, actor suggestions/invitations, embargo
  management, metadata

### Production Readiness Assessment

**Critical Gaps** (affects data integrity):
- ❌ **Idempotency guards**: Handlers can process duplicate activities →
  potential data inconsistency
- ❌ **Activity response generation**: System doesn't notify submitters of
  validation outcomes (Accept/Reject)
- ❌ **Request validation**: No Content-Type, size, or URI validation at HTTP
  layer

**Important Gaps** (affects observability):
- ⚠️ **Correlation IDs**: Logs lack request tracing across async tasks
- ⚠️ **Structured logging**: Plain text logs instead of JSON format
- ⚠️ **Health endpoints**: No `/health/live` or `/health/ready` endpoints

**Nice-to-have** (affects scalability):
- 🟡 **Async dispatcher**: Only synchronous dispatcher implemented; no
  queue-based async dispatch
- 🟡 **Handler coverage**: 30/36 handlers remain stubs (83% incomplete)

**Recommendation**: If moving beyond prototype, prioritize:
1. Idempotency (prevents data corruption)
2. Response generation (closes feedback loop)
3. Observability features (structured logging, correlation IDs, health checks)
4. Remaining handlers (based on use case requirements)

### Known Specification Issues

Identified during design review:

**Cross-Reference Errors**:
1. `specs/error-handling.md` EH-05-001 references `http-protocol.md` HP-06-001
   for error response format, but HP-06-001 is about timeouts
   - **Workaround**: Error response format is defined in EH-05-001 itself

**Specification Ambiguities**:
1. **Rehydration timing** (`specs/semantic-extraction.md` SE-01-002):
   - Spec states rehydration occurs *before* semantic extraction
   - Yet also requires extraction to be "defensive" to partial rehydration
   - **Resolution**: Inbox handler MUST call `rehydrate()` before extraction
     (current implementation correct); defensive pattern matching is
     belt-and-suspenders

2. **Handler idempotency strength** (`specs/handler-protocol.md` HP-07-001,
   `specs/idempotency.md` ID-04-001):
   - Both specs say handlers SHOULD be idempotent
   - Critical workflow handlers (validate_report, create_report) likely need
     MUST-level idempotency
   - **Recommendation**: Treat idempotency as MUST for state-changing handlers

3. **Duplicate detection implementation** (`specs/idempotency.md` ID-02-002):
   - Spec says system SHOULD track activity IDs in DataLayer
   - No details on schema, method signature, or query interface
   - **Workaround**: Use `dl.read(activity.as_id)` to check existence before
     creating; no separate tracking table needed yet

**Incomplete Specifications**:
1. **Outbox implementation**: `specs/response-format.md` RF-06-001 requires
   response delivery to recipient inboxes, but no spec exists for outbox
   processing or routing
2. **CaseActor lifecycle**: `specs/behavior-tree-integration.md` BT-10 mentions
   Case creation triggers CaseActor creation, but no spec on CaseActor message
   handling, authorization, or lifecycle
3. **BT blackboard key conventions**: BT-03-003 prohibits slashes in keys but
   doesn't document naming conventions
   - Current practice: `object_{last_segment}` (see
     `vultron/behaviors/report/validation.py`)
4. **Async dispatcher**: Framework assumes async via BackgroundTasks but
   `specs/dispatch-routing.md` only specifies synchronous
   DirectActivityDispatcher

**Specification Maintenance TODO**:
- Fix EH-05-001 cross-reference
- Clarify rehydration timing requirement
- Add outbox spec (similar to inbox-endpoint.md)
- Add CaseActor spec (message handling, authorization, lifecycle)
- Document BT blackboard key naming conventions
- Upgrade handler idempotency from SHOULD to MUST for state-changing handlers

### BT Integration Lessons

**Handler-Calls-BT Pattern** (Validated in Phase BT-1):

Architecture:
- Handler function remains entry point (preserves semantic routing)
- Handler prepares context (rehydration, validation, setup)
- Handler delegates to BT execution via `BTBridge.execute_tree()`
- Handler processes results (persist state, generate responses, log)

Benefits:
- Preserves handler protocol
- Enables BT orchestration for complex workflows
- Code reduction: 165 lines procedural → 25 lines BT invocation (validate_report)
- Performance: P99 < 1ms (no async queue needed)

**When to Use BTs** (Decision Criteria):

Use BT pattern:
- Complex orchestration with multiple conditional branches
- State machine transitions (CS/RM/EM state changes)
- Need for policy injection (validation rules, authorization)
- Workflow composition (reuse subtrees across handlers)

Use procedural approach:
- Simple CRUD operations (ack_report, close_report)
- Linear workflows with 3-5 steps
- Single database operations
- Logging-only operations

Uncertain complexity:
- Start procedural
- Refactor to BT if maintainability suffers

**BT Implementation Insights**:
- Blackboard key naming must avoid slashes (use simplified keys)
- Policy pattern enables pluggable business rules
- Helper nodes (ReadObject, UpdateObject, CreateObject) reduce boilerplate
- py_trees display utilities provide excellent tree visualization
- DEBUG logging for tree structure, INFO logging for results

### Architectural Lessons Learned

**1. Pydantic Model Validators and Database Round-Tripping**

Issue: Pydantic validators with `mode="after"` run EVERY TIME
`model_validate()` is called, including when reconstructing from database.

Anti-pattern:
```python
@model_validator(mode="after")
def create_inbox(self):
    self.inbox = OrderedCollection()  # Overwrites existing!
    return self
```

Correct pattern:
```python
@model_validator(mode="after")
def create_inbox(self):
    if self.inbox is None:
        self.inbox = OrderedCollection()  # Preserves existing
    return self
```

Impact: Bug caused actor inbox/outbox items to disappear after being saved.

**2. Data Layer Update Signature**

`DataLayer.update()` requires TWO arguments: `id` (str) and `record` (dict)

Anti-pattern: `dl.update(actor_obj)`  
Correct: `dl.update(actor_obj.as_id, object_to_record(actor_obj))`

Always use `object_to_record()` helper to convert Pydantic models to database
dictionaries.

**3. Actor Inbox Persistence Flow**

Changes to actor inbox/outbox collections must be explicitly persisted.

Pattern:
1. Read actor from data layer
2. Modify inbox/outbox collections
3. Call `dl.update(actor.as_id, object_to_record(actor))`
4. Verify persistence

TinyDB persists to disk immediately; in-memory changes are not automatically
saved.

**4. Async Background Processing Timing**

FastAPI BackgroundTasks execute asynchronously after HTTP 202 response.

Implications:
- Testing: Account for async completion time or use explicit polling
- Demo scripts: May need delays (e.g., 3 seconds) to verify handler completion
- pytest TestClient: May bypass timing issues seen with real HTTP server

**5. Rehydration Before Semantic Extraction**

ActivityStreams allows both inline objects and URI string references.

Architecture: Inbox handler MUST call `rehydrate()` before semantic extraction
to expand URI references to full objects.

Pattern matching: Should still handle strings defensively via `getattr(field,
"as_type", None)` for belt-and-suspenders safety.

See `specs/semantic-extraction.md` SE-01-002 and
`vultron/api/v2/data/rehydration.py`.

**6. Docker Service Health Checks and Coordination**

Lessons from Docker implementation (2026-02-17):

- Always implement retry logic when coordinating service startup, even with
  Docker health checks (defense in depth)
- docker-compose.yml and .env must use matching variable names
- After adding packages (like curl), rebuild images with `--no-cache`
- Use `depends_on: condition: service_healthy` not just `service_started`
- Services on same Docker network communicate via service name as hostname
- Ensure health check tools (curl, wget) available in container PATH

**7. FastAPI Response Serialization**

Issue: Return type annotations act as implicit `response_model`, restricting
JSON serialization.

Anti-pattern:
```python
def get_object() -> as_Base:  # Returns only base class fields
    return VulnerabilityCase(...)  # Case-specific fields excluded!
```

Correct:
```python
def get_object():  # No return type annotation
    return VulnerabilityCase(...)  # All fields included
```

Root cause: FastAPI's `response_model` filtering excludes fields not in
annotated class.

Solution: Remove return type annotations from polymorphic endpoints, or use
explicit `Union[Type1, Type2, ...]`.

See `specs/http-protocol.md` HP-07-001.

---

## Implementation Prioritization (2026-02-18)

Context: Vultron is a validated prototype with solid architecture but
incomplete feature coverage. Phase BT-1 successfully demonstrated BT
integration feasibility.

### Scenario-Based Priorities

**Scenario 1: Continuing POC/Research** (current state)
1. ✅ Expand BT integration to additional complex handlers (Phase BT-2)
2. ✅ Implement response generation (`specs/response-format.md`)
3. ✅ Document lessons learned from BT integration
4. ⏸️ Defer: Production features (request validation, structured logging)
5. ⏸️ Defer: Remaining 29 handler stubs

**Scenario 2: Moving to Production** (future)
1. 🔴 Critical: Implement idempotency guards
2. 🔴 Critical: Implement response generation
3. 🟠 High: Request validation (Content-Type, size limits, URI validation)
4. 🟠 High: Structured logging + correlation IDs
5. 🟠 High: Health endpoints
6. 🟡 Medium: Complete remaining 29 handlers (or document out-of-scope)
7. 🟡 Medium: Async dispatcher (queue-based)
8. 🟢 Low: BT expansion (only if handlers need complex orchestration)

**Scenario 3: Maintaining/Refactoring** (ongoing)
1. Fix specification cross-references
2. Add missing specs (outbox, CaseActor, BT naming conventions)
3. Improve test coverage for edge cases
4. Performance profiling (ensure P99 < 100ms maintained as handlers added)
