# Behavior Tree Integration Specification

## Overview

Handler functions may orchestrate business logic using behavior trees (BTs) for complex workflows. BTs provide hierarchical, composable process modeling with explicit preconditions and state transitions.

**Source**: ADR-0002 (Use Behavior Trees), ADR-0007 (Behavior Dispatcher),
ADR-0008 (py_trees integration)
**Status**: Phase BT-1 COMPLETE — infrastructure, handler refactoring, demo
validation, and documentation all done.

**Note**: BT integration is **optional**. Simple handlers may use procedural
logic. Complex workflows (report validation, case creation, embargo management)
SHOULD use BTs for clarity and maintainability.

---

## BT Execution Model (MUST)

- `BT-01-001` BT execution MUST be event-driven, triggered by handler invocation
- `BT-01-002` BTs MUST execute to completion (or max iterations) per invocation
- `BT-01-003` BT execution MUST NOT use continuous tick-based polling loops
- `BT-01-004` BTs MUST be single-shot executions within handler context

## BT Library (MUST)

- `BT-02-001` Prototype handlers MUST implement BT execution using industry-
  standard BT library
  - **Implementation**: Currently uses `py_trees` (v2.2.0+)
  - **Rationale**: Mature libraries provide visualization, debugging, and
    standard BT semantics
  - Future: Alternative libraries MAY be substituted if they provide equivalent
    BT execution semantics
- `BT-02-002` Simulation code in `vultron/bt/` MUST remain unchanged
  - Simulation uses custom BT engine; prototype uses py_trees
  - No refactoring of simulation to py_trees

## State Management (MUST)

- `BT-03-001` BTs MUST use DataLayer as persistent state store
- `BT-03-002` BTs MUST NOT maintain separate blackboard persistence
- `BT-03-003` BT blackboard MAY cache DataLayer state during execution
  - Blackboard keys MUST NOT contain slashes (hierarchical path parsing issues
    in py_trees)
  - Use simplified keys following the pattern `{noun}_{id_segment}` where
    `id_segment` is the last path segment of the object's URI
  - Examples: `object_abc123`, `case_def456`, `actor_vendorco`
  - Current convention: `object_{last_url_segment}` (see
    `vultron/behaviors/report/nodes.py`)
- `BT-03-004` State changes MUST be committed to DataLayer on successful
  execution

## Handler Integration (MUST)

- `BT-04-001` Handler protocol MUST be preserved (decorator, signature, registration)
- `BT-04-002` Handlers MAY invoke BTs via bridge layer
- `BT-04-003` Handlers MUST remain synchronous (BT execution within handler)
- `BT-04-004` BT execution errors MUST propagate to handler error handling

## BT Bridge Layer (SHOULD)

- `BT-05-001` System SHOULD provide BT execution bridge for handler-to-BT invocation
- `BT-05-002` Bridge SHOULD set up py_trees context with DataLayer access
- `BT-05-003` Bridge SHOULD populate blackboard with activity and actor state
- `BT-05-004` Bridge SHOULD execute tree and return execution result

## Workflow-Specific Trees (SHOULD)

- `BT-06-001` Complex workflows SHOULD have dedicated BT implementations
  - Report validation, case creation, embargo management
- `BT-06-002` BTs SHOULD match structure of simulation trees where applicable
  - **Verification**: Compare BT node sequence against simulation tree node
    sequence
  - Exact 1:1 mapping NOT required; semantic equivalence is sufficient
- `BT-06-003` BT nodes SHOULD be deterministic
  - **Definition**: Given same input state, node always returns same result
  - No random number generation, no time-dependent behavior (e.g., timeouts,
    retries with jitter)
  - Exception: Externally-driven nondeterminism (e.g., human-in-the-loop
    decisions) is acceptable

## DataLayer Integration (MUST)

- `BT-07-001` BT nodes MUST interact with DataLayer via Protocol interface
  - **Protocol**: `vultron.api.v2.datalayer.abc.DataLayer` (duck typing, not
    inheritance)
  - Methods: `get(id_)`, `create(obj)`, `update(id_, record)`, `delete(id_)`,
    `search(query)`, `get_status_layer()`
- `BT-07-002` BT nodes MUST use type-safe DataLayer operations
  - Pydantic models for object validation
  - Type hints on node methods
  - Runtime type checks where needed
- `BT-07-003` State transitions MUST be logged via DataLayer integration
  - Log at INFO level for state changes (e.g., "Report RM.RECEIVED →
    RM.VALID")
  - Log at DEBUG level for reads
  - Include activity_id and actor_id in log context

## Command-Line Execution (MAY)

- `BT-08-001` System MAY provide CLI interface for BT execution
  - Enables testing and AI agent integration
- `BT-08-002` CLI SHOULD support invoking specific trees with test data
- `BT-08-003` CLI SHOULD log BT execution visualization

## Actor Isolation (MUST)

- `BT-09-001` Each actor MUST have isolated BT execution context
- `BT-09-002` Actor blackboards MUST NOT share state
- `BT-09-003` Actor interaction MUST occur only via protocol messages

## CaseActor Management (MUST)

- `BT-10-001` Report validation MUST trigger VulnerabilityCase creation
- `BT-10-002` Case creation MUST create corresponding CaseActor (Service)
- `BT-10-003` CaseActor MUST manage case-related message processing
- `BT-10-004` `PROD_ONLY` CaseActor MUST enforce case-level authorization

## Concurrency (MUST)

- `BT-11-001` Prototype MUST process messages sequentially (FIFO order)
  - **Rationale**: Eliminates race conditions in prototype phase
- `BT-11-002` Sequential processing MUST NOT block HTTP response (BackgroundTasks)
- `BT-11-003` `PROD_ONLY` Future optimizations MAY introduce resource-level locking

## Verification

### BT-01-001, BT-01-002, BT-01-003, BT-01-004 Verification

- Unit test: Handler invokes BT; BT executes once per handler call
- Unit test: BT returns result after completion (not ongoing tick loop)
- Integration test: Multiple handler invocations trigger separate BT executions

### BT-02-001 Verification

- Code review: Prototype BT implementations import `py_trees` library
- Unit test: BT nodes are py_trees.behaviour.Behaviour subclasses

### BT-03-001, BT-03-002, BT-03-004 Verification

- Unit test: BT nodes read state via DataLayer protocol
- Unit test: BT state changes persist to DataLayer after execution
- Unit test: No separate blackboard persistence layer

### BT-04-001, BT-04-002, BT-04-003 Verification

- Code review: BT-using handlers have @verify_semantics decorator
- Unit test: BT execution occurs synchronously within handler
- Unit test: BT exceptions propagate to handler error handling

### BT-10-001, BT-10-002, BT-10-003 Verification

- Integration test: Validate report → creates VulnerabilityCase
- Integration test: Case creation → creates CaseActor service
- Unit test: CaseActor exists in DataLayer with correct case reference

### BT-11-001, BT-11-002 Verification

- Integration test: Concurrent inbox POSTs process sequentially
- Integration test: HTTP 202 returned immediately (not blocked by BT execution)

## Related

- **Behavior Trees in CVD**: `docs/topics/behavior_logic/`
- **Simulation Trees**: `vultron/bt/` (reference, not modified)
- **Handler Protocol**: `specs/handler-protocol.md`
- **Data Layer**: `specs/testability.md` (DataLayer abstraction)
- **Architecture**: `plan/IMPLEMENTATION_NOTES.md` (design decisions and
  rationale)
- **ADRs**: ADR-0002 (BT rationale), ADR-0007 (dispatcher architecture)

## Implementation

- **Bridge Layer**: `vultron/behaviors/bridge.py` ✅ (Phase BT-1.1.3)
  - `BTBridge` class: Handler-to-BT execution adapter
  - Single-shot execution with blackboard setup
  - `get_tree_visualization()` for DEBUG-level tree display
- **DataLayer Helpers**: `vultron/behaviors/helpers.py` ✅ (Phase BT-1.2.1)
  - `DataLayerCondition`, `DataLayerAction` base classes
  - `ReadObject`, `UpdateObject`, `CreateObject` common nodes
- **Report Validation Trees**: `vultron/behaviors/report/` ✅ (Phase
  BT-1.3.2, BT-1.3.3, BT-1.3.4)
  - `nodes.py`: 10 domain-specific nodes (conditions, actions, policy stubs)
  - `validate_tree.py`: Composed validation tree with early exit optimization
  - `policy.py`: `ValidationPolicy` base class and `AlwaysAcceptPolicy`
- **Handler Integration**: `vultron/api/v2/backend/handlers.py` ✅ (Phase
  BT-1.4.1)
  - `validate_report` handler refactored to use `BTBridge.execute_with_setup()`
  - Replaced ~165 lines of procedural logic with ~25 lines of BT invocation
  - Preserved `@verify_semantics` decorator and error handling
- **Tests**: `test/behaviors/` ✅ (78 tests passing)
  - `test_bridge.py`, `test_helpers.py`, `test/behaviors/report/` subtests
  - `test_performance.py`: P50=0.44ms, P95=0.69ms, P99=0.84ms (well within
    100ms target)
