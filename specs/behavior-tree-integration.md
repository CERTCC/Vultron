# Behavior Tree Integration Specification

## Overview

Handler functions may orchestrate business logic using behavior trees (BTs) for complex workflows. BTs provide hierarchical, composable process modeling with explicit preconditions and state transitions.

**Source**: ADR-0002 (Use Behavior Trees), ADR-0007 (Behavior Dispatcher),
ADR-0008 (py_trees integration)

**Note**: BT integration is **optional**. Simple handlers may use procedural
logic. Complex workflows (report validation, case creation, embargo management)
SHOULD use BTs for clarity and maintainability.

---

## BT Execution Model

- `BT-01-001` BT execution MUST be event-driven, triggered by handler invocation
- `BT-01-002` BTs MUST execute to completion (or max iterations) per invocation
- `BT-01-003` BT execution MUST NOT use continuous tick-based polling loops
- `BT-01-004` BTs MUST be single-shot executions within handler context

## BT Library

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

## State Management

- `BT-03-001` BTs MUST use DataLayer as persistent state store
- `BT-03-002` BTs MUST NOT maintain separate blackboard persistence
- `BT-03-003` BT blackboard MAY cache DataLayer state during execution
  - Blackboard keys MUST NOT contain slashes (hierarchical path parsing issues
    in py_trees)
  - Use simplified keys following the pattern `{noun}_{id_segment}` where
    `id_segment` is the last path segment of the object's URI
  - Examples: `object_abc123`, `case_def456`, `actor_vendorco`
  - Current convention: `object_{last_url_segment}` (see
    `vultron/core/behaviors/report/nodes.py`)
- `BT-03-004` State changes MUST be committed to DataLayer on successful
  execution

## Handler Integration

- `BT-04-001` Handler protocol MUST be preserved (decorator, signature, registration)
- `BT-04-002` Handlers MAY invoke BTs via bridge layer
- `BT-04-003` Handlers MUST remain synchronous (BT execution within handler)
- `BT-04-004` BT execution errors MUST propagate to handler error handling

## BT Bridge Layer

- `BT-05-001` System SHOULD provide BT execution bridge for handler-to-BT invocation
- `BT-05-002` Bridge SHOULD set up py_trees context with DataLayer access
- `BT-05-003` Bridge SHOULD populate blackboard with activity and actor state
- `BT-05-004` Bridge SHOULD execute tree and return execution result

## Workflow-Specific Trees

- `BT-06-001` All protocol-significant behavior MUST be implemented as BT
  nodes or subtrees. There is no "simple enough to skip" threshold.
  - **Rationale**: The BT is the domain documentation. If a behavior is not
    in the tree, it is invisible to analysis, audit, and explainability
    tools. The tree structure is the source of truth for what Vultron does —
    not the code around it.
  - **Procedural glue exception**: `execute()` MAY contain infrastructure
    glue: instantiating the BT, setting up the blackboard from the event,
    calling `bt.run()`, checking BT status, and extracting output from the
    blackboard. Nothing domain-significant lives outside the tree.
  - Per ADR-0015, case/participant creation and embargo initialization
    run in a dedicated `receive_report_case_tree` BT invoked by
    `SubmitReportReceivedUseCase`. The `validate_report` BT focuses on
    validation logic only.
- `BT-06-002` Prototype use-case BTs MUST correspond to identifiable
  subtrees of the canonical CVD protocol BT
  - **Canonical reference**: `vultron-bt.txt` (full tree dump),
    `docs/topics/behavior_logic/` (narrative docs), `vultron/bt/`
    (simulation implementation — read only)
  - The canonical BT is the normative definition of Vultron's domain
    behavior. Use-case BTs implement subtrees of it; they do not invent
    new structures.
  - **Divergence rule**: If a prototype BT diverges from the canonical
    tree structure, that divergence MUST be documented with justification
    (in a note or ADR). Undocumented divergence is a bug.
  - **Implementation guide**: `notes/canonical-bt-reference.md` — subtree
    map, trunk-removed branches model, implementation guidance
- `BT-06-003` BT nodes SHOULD be deterministic
  - **Definition**: Given same input state, node always returns same result
  - No random number generation, no time-dependent behavior (e.g., timeouts,
    retries with jitter)
  - Exception: Externally-driven nondeterminism (e.g., human-in-the-loop
    decisions) is acceptable
- `BT-06-004` Individual BT nodes MUST be simple and focused on a single
  concern (e.g., a single exception check or a single boolean condition)
  - Any node that contains complicated business logic is a candidate for
    refactoring into its own sub-tree
  - **Rationale**: The tree structure IS the documentation of what Vultron
    does. Surfacing business logic into the tree — rather than embedding it
    in node code or in `execute()` outside the tree — makes the process
    auditable and explainable without reading implementation code. If it is
    not in the tree, it cannot be reasoned about from the tree alone.
- `BT-06-005` (MUST) Cascades from a parent subtree to a child subtree in
  the canonical BT MUST be expressed as BT subtrees within the use case's
  BT — not as procedural calls in `execute()` after `bt.run()` returns.
  - **Example**: In the canonical BT, `?_RMValidateBt` (validate) and
    `?_RMPrioritizeBt` (engage/defer) are parent→child. Therefore, the
    validate→engage/defer cascade MUST be a subtree within the validate BT,
    not a call to `SvcEngageCaseUseCase()` after the BT completes.
  - **Anti-pattern** (MUST NOT): calling `SvcXxxUseCase().execute()` or any
    domain-significant function procedurally after `bridge.execute_with_setup()`
    returns. See `notes/canonical-bt-reference.md` for the corrected pattern.
- `BT-06-006` (MUST NOT) Protocol-observable actions and state transitions
  MUST NOT be performed as procedural code outside the BT.
  - Protocol-observable = emitting activities, transitioning RM/EM/CS state,
    creating/updating domain objects, cascading to downstream behaviors.
  - The only code permitted outside the BT is infrastructure glue: loading
    actor/case IDs for blackboard setup, calling `bt.run()`, checking status,
    extracting output.

## DataLayer Integration

- `BT-07-001` BT nodes MUST interact with DataLayer via Protocol interface
  - **Protocol**: `vultron.core.ports.datalayer.DataLayer` (duck typing, not
    inheritance)
  - Methods: `get(id_)`, `create(obj)`, `update(id_, record)`, `delete(id_)`,
    `search(query)`, `get_status_layer()`
- `BT-07-002` BT nodes MUST use type-safe DataLayer operations
  - Pydantic models for object validation
  - Type hints on node methods
  - Runtime type checks where needed
- `BT-07-003` State transitions MUST be logged at the appropriate level
  - BT-07-003 depends-on SL-03-001
  - BT-07-003 depends-on SL-04-001

## Command-Line Execution

- `BT-08-001` System MAY provide CLI interface for BT execution
  - Enables testing and AI agent integration
- `BT-08-002` CLI SHOULD support invoking specific trees with test data
- `BT-08-003` CLI SHOULD log BT execution visualization

## Actor Isolation

- `BT-09-001` Each actor MUST have isolated BT execution context
- `BT-09-002` Actor blackboards MUST NOT share state
- `BT-09-003` Actor interaction MUST occur only via protocol messages

## CaseActor Management

- `BT-10-001` Report validation MUST trigger VulnerabilityCase creation
  - BT-10-001 implements VP-02-015
  - BT-10-001 implements VP-02-020
- `BT-10-002` Case creation MUST create corresponding CaseActor (Service)
- `BT-10-003` CaseActor MUST manage case-related message processing
- `BT-10-004` `PROD_ONLY` CaseActor MUST enforce case-level authorization
- `BT-10-005` When an actor accepts a case invitation, the system
  SHOULD automatically advance the accepting actor's RM state to
  ACCEPTED via BT or use-case execution
  - BT-10-005 implements CM-11-001

## VFD/PXA State Machine Usage

- `BT-12-001` (MUST) When implementing VFD (vendor fix deployed) or PXA (public
  exploit/attack) state transitions, new code MUST use `create_vfd_machine()`
  and `create_pxa_machine()` (defined in `vultron/core/states/cs.py`) as the
  authoritative source of valid transition sequences. Hand-rolled transition
  logic for these state dimensions MUST NOT be introduced.
  - **Rationale**: Ensures the `transitions` machines remain the normative
    definition of valid VFD/PXA state progressions as new features are added,
    preventing divergence between the machines and the implementation.
  - **See also**: OPP-06 in `notes/state-machine-findings.md`

## Concurrency

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

- Code review: BT-using handlers are registered in USE_CASE_MAP and invoked via the dispatcher
- Unit test: BT execution occurs synchronously within handler
- Unit test: BT exceptions propagate to handler error handling

### BT-06-001, BT-06-005, BT-06-006 Verification

- Code review: `execute()` contains no domain-significant code after
  `bridge.execute_with_setup()` returns — only status checks and output
  extraction from blackboard
- Code review: No use case calls `SvcXxxUseCase().execute()` or similar
  procedurally after a BT run
- Code review: Each cascade that is parent→child in the canonical BT is
  implemented as a BT subtree, not a procedural function call
- Unit test: validate-report BT includes prioritize (engage/defer) subtree
  as a child; no `_auto_engage` or equivalent outside the tree

### BT-06-002 Verification

- Code review: Each use-case BT corresponds to a named subtree path in
  `vultron-bt.txt` / `docs/topics/behavior_logic/`
- Documentation check: Any divergence from canonical structure is documented
  with justification in a note or ADR

### BT-10-001 through BT-10-005 Verification

- Integration test: Validate report → creates VulnerabilityCase
- Integration test: Case creation → creates CaseActor service
- Unit test: CaseActor exists in DataLayer with correct case reference
- Unit test: Invitation acceptance triggers RM→ACCEPTED without
  separate engage-case trigger (BT-10-005)

### BT-11-001, BT-11-002 Verification

- Integration test: Concurrent inbox POSTs process sequentially
- Integration test: HTTP 202 returned immediately (not blocked by BT execution)

### BT-12-001 Verification

- Code review: Any code adding VFD or PXA state transitions uses
  `create_vfd_machine()` or `create_pxa_machine()` rather than hand-rolled
  logic

## Related

- **Canonical BT Reference**: `notes/canonical-bt-reference.md` (subtree
  map, trunk-removed branches model, anti-pattern examples)
- **Behavior Trees in CVD**: `docs/topics/behavior_logic/`
- **Simulation Trees**: `vultron/bt/` (reference, not modified)
- **Handler Protocol**: `specs/handler-protocol.md`
- **Case Management**: `specs/case-management.md` (CaseActor, actor isolation)
- **Data Layer**: `specs/testability.md` (DataLayer abstraction)
- **Design Notes**: `notes/bt-integration.md` (durable design decisions),
  `notes/canonical-bt-reference.md` (canonical subtree map)
- **ADRs**: ADR-0002 (BT rationale), ADR-0007 (dispatcher architecture)
- **Implementation**: `vultron/core/behaviors/` (bridge layer, helpers,
  report trees)
- **Tests**: `test/behaviors/`
