# Implementation Notes

This file tracks insights, issues, and learnings during implementation.

---

## Behavior Tree Integration

### Phase BT-1 Status: Complete ✅

Phase BT-1 successfully validated the BT integration approach:

- Bridge layer (`vultron/behaviors/bridge.py`), DataLayer helpers
  (`vultron/behaviors/helpers.py`), and report validation BT
  (`vultron/behaviors/report/`) are implemented.
- `validate_report` handler refactored to use BT execution (reduced from
  ~165 lines of procedural logic to ~25 lines of BT invocation).
- 78 BT tests passing.
- Performance: P50=0.44ms, P95=0.69ms, P99=0.84ms (well within 100ms target).
- ADR-0008 created for py_trees integration decision.

**Next**: Phase BT-2 — extend BT approach to remaining report handlers.

---

### Key Design Decisions

#### 1. py_trees for Prototype (Not Custom BT Engine)

Use the `py_trees` library (v2.2.0+) for prototype handler BTs. The existing
`vultron/bt/` simulation code uses a custom BT engine and MUST remain unchanged.

**Rationale**: py_trees is mature, well-tested, provides visualization and
debugging tools, and allows focus on workflow logic rather than BT engine
maintenance.

**Boundary**: `vultron/bt/` retains custom engine for simulation;
`vultron/behaviors/` uses py_trees for prototype handlers. These coexist
independently.

#### 2. Handler-Orchestrated BT (Handler-First)

Handlers orchestrate BT execution — handlers call BTs, BTs do not replace the
handler architecture.

**Rationale**: Preserves existing semantic extraction and dispatch
infrastructure. Allows gradual handler-by-handler migration. Keeps
ActivityStreams as the API surface (BT is an internal implementation detail).
Aligns with ADR-0007.

**Rejected alternative**: BTs directly consuming ActivityStreams — would require
rewriting semantic extraction and tighter coupling.

#### 3. DataLayer as State Store (No Separate Blackboard Persistence)

BTs interact directly with DataLayer for all persistent state. The py_trees
blackboard MAY be used for transient in-execution state only.

**Rationale**: Single source of truth, eliminates sync issues, simplifies
architecture, transaction semantics handled by DataLayer.

**Blackboard key naming**: Blackboard keys MUST NOT contain slashes (py_trees
hierarchical path parsing issues). Use `{noun}_{id_segment}` where `id_segment`
is the last path segment of the object's URI. Example: `object_abc123`,
`case_def456`, `actor_vendorco`.

**Rejected alternative**: Separate blackboard with periodic sync — risk of
inconsistencies, complex sync logic.

#### 4. Focused BTs per Workflow (Not Monolithic)

Create small, focused behavior trees triggered by specific message semantics.
Each `MessageSemantics` type has a corresponding BT encapsulating that workflow.

**Rationale**: Event-driven model (one message → one tree), easier to test in
isolation, clear handler entry points, composable via subtrees, better
performance.

**Rejected alternative**: Single monolithic `CvdProtocolBT` for prototype —
doesn't match event-driven handler architecture, harder to test, poor
performance.

#### 5. Single-Shot Execution (Not Persistent Tick Loop)

BTs execute to completion per handler invocation. No state is preserved between
handler invocations.

**Rationale**: Matches HTTP request/response model, simpler failure handling,
clear transaction boundaries (one execution = one commit).

**Rejected alternative**: Async tick-based execution with pause/resume —
requires BT state persistence between ticks, complex failure recovery.

#### 6. Case Creation Includes CaseActor Generation

VulnerabilityCase creation triggers CaseActor (ActivityStreams Service) creation
as part of the same workflow.

**Rationale**: Case needs a message-processing owner. CaseActor models
case-as-agent, enables multi-case coordination, clear responsibility boundary.
One CaseActor per VulnerabilityCase (1:1 relationship).

**CaseActor lifecycle**: Created during report validation → owns case-related
message processing → exists until case closure.

**Case ownership model**:
- **Case Owner**: Organizational Actor (vendor/coordinator) responsible for
  decisions
- **CaseActor**: ActivityStreams Service managing case state (NOT the case owner)
- **Initial Owner**: Typically the recipient of the VulnerabilityReport Offer

#### 7. CLI Invocation Support (MAY)

BTs can be invoked independently via CLI for testing and AI agent integration.
See `BT-08-*` in `specs/behavior-tree-integration.md`.

---

### Actor Isolation and BT Domains

Each actor has an isolated BT execution domain with no shared blackboard access:

- Actor A and Actor B have separate py_trees blackboards
- Cross-actor interaction happens ONLY through ActivityStreams messages
  (inboxes/outboxes)
- This models real-world CVD: independent organizations making autonomous
  decisions
- Each actor's internal state (RM/EM/CS state machines) is private

---

### Concurrency Model

**Prototype approach**: Sequential FIFO message processing.

**Rationale**: Eliminates race conditions without complexity. Single-threaded
execution of the inbox queue is sufficient for prototype validation.

**Implementation**: BackgroundTasks queues messages; inbox endpoint returns 202
immediately. BT execution happens in the background, sequentially.

**Future optimization paths** (defer until needed):
- Optimistic locking (version numbers on VulnerabilityCase)
- Resource-level locking (lock specific case during mutations)
- Actor-level concurrency (parallel across actors, sequential per-actor)

---

### Simulation-to-Prototype Translation Strategy

When implementing Phase BT-2 through BT-4, use simulation trees as
architectural reference (not code reuse targets).

**Why NOT factory method reuse**: The simulation uses custom BT engine factory
methods (`sequence_node()`, `fallback_node()`) from `vultron/bt/base/factory.py`
that return custom node types. py_trees uses class-based hierarchy
(`py_trees.composites.Sequence`, `py_trees.composites.Selector`) with
incompatible initialization patterns. Direct py_trees implementation is faster
and cleaner.

**Translation steps**:

1. Find the corresponding simulation tree in
   `vultron/bt/report_management/_behaviors/` (or embargo/case equivalents).
2. Note the sequence/fallback composition hierarchy and node ordering.
3. Map condition nodes (e.g., `RMinStateValid`) to py_trees `Behaviour`
   subclasses checking DataLayer state.
4. Replace fuzzer nodes (e.g., `EvaluateReportCredibility`) with deterministic
   policy nodes using configurable defaults.
5. Preserve state transition order and precondition checks.
6. Wrap state changes with DataLayer update operations.
7. Generate ActivityStreams activities for outbox where simulation emits
   messages.

**Fuzzer node replacement pattern**: Create a policy class with a clear
interface (e.g., `ValidationPolicy.is_credible(report) -> bool`) and a default
`AlwaysAcceptPolicy` implementation. This provides a deterministic stub with an
explicit extension point.

**Simulation tree to handler mapping**:

| Handler | Simulation Reference | Key Behavior |
|---|---|---|
| `validate_report` | `_behaviors/validate_report.py:RMValidateBt` | ✅ DONE |
| `invalidate_report` | `_behaviors/validate_report.py:_InvalidateReport` | Sequence: transition to INVALID + emit RI |
| `close_report` | `_behaviors/close_report.py:RMCloseBt` | Sequence: check preconditions + transition to CLOSED + emit RC |
| `prioritize_report` | `_behaviors/prioritize_report.py:RMPrioritizeBt` | Policy-driven: evaluate priority + ACCEPTED or DEFERRED |
| `do_work` | `_behaviors/do_work.py:RMDoWorkBt` | Complex: fix dev, testing, deployment |

---

### Source of Truth Priority

When conflicts arise between reference documents during Phase BT-2+
implementation:

1. **Primary**: `docs/howto/activitypub/activities/*.md` — process descriptions,
   message examples, workflow steps
2. **Secondary**: `vultron/bt/report_management/_behaviors/*.py` — state machine
   logic, tree composition
3. **Tertiary**: `docs/topics/behavior_logic/*.md` — conceptual diagrams,
   motivation

---

### Open Questions for Future Phases

These questions were identified during Phase BT-1 planning and remain open for
Phase BT-2 through BT-4:

**Multi-actor state synchronization (Phase BT-3)**:
Each actor's BT loads only that actor's DataLayer state. Cross-actor
coordination happens via message exchange. Whether to add optimistic locking for
Phase 3 multi-actor scenarios should be decided based on observed issues during
testing.

**Message emission and outbox processing (Phase BT-2)**:
BT nodes generate activities and write to actor outbox via DataLayer. Whether
outbox delivery should be triggered synchronously after BT execution or
asynchronously remains to be decided.

**Human-in-the-loop decision handling (All phases)**:
Report validation, embargo acceptance, and similar steps require human judgment.
The prototype uses configurable default policies (always-accept stubs with audit
logging). Async workflow support with pause/resume is a Phase 4+ consideration.

**Performance optimization (Phase BT-4)**:
Current targets: P50 < 50ms, P99 < 100ms. Phase BT-1 results (P99 = 0.84ms)
far exceed targets. If more complex trees degrade performance, consider:
caching BT structure (instantiate once, reuse with fresh blackboard) and
batching DataLayer operations. Measure before optimizing.

---

### Specification References

- `specs/behavior-tree-integration.md` — formal BT requirements (BT-01 through
  BT-11)
- `specs/handler-protocol.md` — handler protocol BT-powered handlers must
  comply with
- `specs/testability.md` — test coverage requirements
- ADR-0002 — Use Behavior Trees (rationale)
- ADR-0007 — Behavior Dispatcher architecture
- ADR-0008 — py_trees integration decision

---

## Docker Health Check Coordination

**Symptom**: Demo container fails to connect to API server with "Connection
refused" despite both containers running.

**Cause**: Docker Compose `depends_on: service_started` only waits for
container start, not application readiness.

**Solution**: Add health check to API service and use
`condition: service_healthy` in dependent services. Add retry logic in client
code as defense in depth. See `docker/` for current configuration.

---

## FastAPI response_model Filtering

**Symptom**: API endpoints return objects missing subclass-specific fields.

**Cause**: FastAPI uses return type annotation as implicit `response_model`,
restricting JSON serialization to fields defined in the annotated base class.

**Solution**: Remove return type annotation from endpoints returning multiple
types, or use explicit `Union[Type1, Type2, ...]`.

---

## Idempotency Responsibility Chain

Handlers SHOULD check for existing records before creating new ones to prevent
duplicates. Use DataLayer queries to detect duplicates based on business keys
(report ID, case ID). Report handlers (`create_report`, `submit_report`) already
implement this pattern.

---

## Circular Import Patterns

**Common cause**: Core module importing from `api.v2.*` triggers full app
initialization. Use neutral shared modules (`types.py`,
`dispatcher_errors.py`) and lazy imports when needed. See `specs/code-style.md`
CS-05-* for requirements.

---

## ActivityStreams Rehydration

**Pattern**: Activities may contain string URI references instead of inline
objects. Always call `rehydrate()` on incoming activities before pattern
matching. The `inbox_handler.py` does this before dispatch, so handlers receive
fully expanded objects. See `vultron/api/v2/data/rehydration.py`.

