# Implementation Notes

This file tracks insights, issues, and learnings during implementation.

**Last Updated**: 2026-02-18

---

## 2026-02-18: BT-1.3.4 - Created default policy implementation

### Task: Create AlwaysAcceptPolicy for report validation

**Status**: COMPLETE

**Changes**:
- Created `vultron/behaviors/report/policy.py` (162 lines)
- Created `test/behaviors/report/test_policy.py` (260 lines, 12 tests)
- Implemented per specs/behavior-tree-integration.md and plan/IMPLEMENTATION_PLAN.md

**Implementation Details**:

1. **ValidationPolicy Abstract Base Class**:
   - Defines interface for pluggable policy implementations
   - Two methods: `is_credible(report)` and `is_valid(report)`
   - Raises `NotImplementedError` for abstract methods
   - Extension point for custom policies (ML models, reputation systems, human-in-the-loop)

2. **AlwaysAcceptPolicy Implementation**:
   - Phase 1 prototype simplification: Always returns `True`
   - Logs policy decisions at INFO level for observability
   - Log message format: `"Policy: Accepting report {id} as {credible|valid} (AlwaysAcceptPolicy)"`
   - Suitable for demo environments, trusted reporters, development

3. **Design Patterns**:
   - Policy pattern for pluggable decision logic
   - No state stored in policy instance (stateless, reusable)
   - No mutation of report objects (pure evaluation)
   - Comprehensive docstrings with examples

**Test Coverage**:
- 12 tests covering:
  - Abstract base class contract (NotImplementedError for unimplemented methods)
  - Subclass implementation pattern (custom policy example)
  - AlwaysAcceptPolicy behavior (always returns True)
  - Logging verification (INFO level, correct message content)
  - Multiple reports handling (reusable policy instance)
  - Report immutability (no mutation during evaluation)
  - Inheritance verification (isinstance checks)
  - Log message traceability (report ID included)
- All tests passing (454 tests total: 442 base + 12 new)

**Integration with Existing Code**:
- Policy nodes (`EvaluateReportCredibility`, `EvaluateReportValidity`) in `nodes.py` currently use stub logic
- Future integration (Phase BT-1.4 or later): Pass `AlwaysAcceptPolicy` instance to nodes
- Policy can be injected via constructor or blackboard
- No changes to existing BT structure required

**Lessons Learned**:
1. **Abstract base classes**: Use `NotImplementedError` with descriptive messages for abstract methods
2. **Logging best practices**: Include entity IDs in log messages for traceability
3. **Policy pattern**: Stateless policies are reusable across multiple evaluations
4. **Extension documentation**: Docstrings should highlight extension points for future development

**Verification**:
- All 454 tests passing (no regressions)
- Black formatting applied to both files
- Test coverage: 100% for policy module (12 tests cover all paths)

**Next Step**: BT-1.4.1 - Refactor `validate_report` handler to use BT execution

---

## 2026-02-18: BT-1.3.3 - Composed validation behavior tree

### Task: Compose validation behavior tree

**Status**: COMPLETE

**Changes**:
- Created `vultron/behaviors/report/validate_tree.py` with `create_validate_report_tree()` factory (139 lines)
- Created `test/behaviors/report/test_validate_tree.py` with 12 comprehensive integration tests (502 lines)
- Fixed blackboard key registration in `CreateCaseActivity` and `UpdateActorOutbox` nodes
- Updated 2 tests in `test/behaviors/report/test_nodes.py` to handle blackboard key registration

**Tree Structure** (Phase 1 - Minimal Match to Procedural Handler):

```
ValidateReportBT (Selector)
├─ CheckRMStateValid                 # Early exit if already valid
└─ ValidationFlow (Sequence)
   ├─ CheckRMStateReceivedOrInvalid  # Precondition check
   ├─ EvaluateReportCredibility      # Policy check (stub)
   ├─ EvaluateReportValidity         # Policy check (stub)
   └─ ValidationActions (Sequence)
      ├─ TransitionRMtoValid         # Update statuses
      ├─ CreateCaseNode              # Create case object
      ├─ CreateCaseActivity          # Generate CreateCase activity
      └─ UpdateActorOutbox           # Add to outbox
```

**Key Implementation Details**:
1. **Factory function pattern**: `create_validate_report_tree()` returns configured root node
   - Accepts `report_id` and `offer_id` parameters
   - Returns `py_trees.composites.Selector` root
   - Composable: Can be used as subtree in larger workflows

2. **Blackboard key passing**:
   - `CreateCaseNode` writes `case_id` → `CreateCaseActivity` reads it → writes `activity_id` → `UpdateActorOutbox` reads it
   - Nodes register READ access to keys they consume
   - Registration in `setup()` method override (not `__init__`)

3. **Selector vs. Sequence at root**:
   - Selector allows early exit optimization (CheckRMStateValid returns SUCCESS)
   - Fallback path (invalidation) deferred to Phase 2
   - Current structure: SUCCESS if valid OR (preconditions met AND validation succeeds)

4. **Phase 1 simplifications** (noted in docstring):
   - No InvalidateReport fallback sequence
   - No information gathering loop
   - Policy nodes always return SUCCESS (stubs)
   - Direct translation of procedural handler logic

**Test Coverage**:
- 12 integration tests covering:
  - Tree creation and structural verification
  - Execution with various report states (RECEIVED, INVALID, VALID, no status)
  - Early exit optimization
  - Policy stub behavior
  - Error handling (missing DataLayer, actor_id, report)
  - Idempotency
  - Actor isolation
- All tests use proper fixtures (datalayer, bridge, actors, reports, offers)
- Tests verify both SUCCESS status and side effects (status updates)

**Lessons Learned**:

1. **Blackboard key registration**: Nodes consuming blackboard keys MUST register them in `setup()`
   - Use READ access for keys written by other nodes
   - Use WRITE access for keys the node itself writes
   - Failure to register causes "does not have read/write access" errors

2. **Import corrections during testing**:
   - Correct: `from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer`
   - Correct: `from vultron.as_vocab.base.objects.activities.transitive import as_Offer`
   - Correct: `from vultron.as_vocab.base.objects.actors import as_Service`
   - Use existing test files as reference for import paths

3. **DataLayer API usage**:
   - `datalayer.create(obj)` takes single object argument (not table name)
   - Status layer accessed via `get_status_layer()` (not datalayer)
   - `set_status(ReportStatus(...))` takes single ObjectStatus argument

4. **BTBridge fixture dependency**:
   - `BTBridge(datalayer=datalayer)` requires datalayer argument
   - Bridge fixture depends on datalayer fixture: `def bridge(datalayer): return BTBridge(datalayer=datalayer)`

5. **Test assertions for BTExecutionResult**:
   - `result.errors` is None (not `[]`) when no errors
   - Use `assert result.errors is None or result.errors == []` for robustness

6. **Updating existing tests after adding setup() overrides**:
   - When nodes register blackboard keys in `setup()`, tests expecting FAILURE must explicitly set keys to None
   - Must register key with WRITE access before calling `.set()`: `node.blackboard.register_key(key="case_id", access=py_trees.common.Access.WRITE)`
   - Then: `node.blackboard.set("case_id", None, overwrite=True)`

**Verification**:
- All 442 tests passing (430 base + 12 new)
- Full test suite: no regressions
- Black formatting applied (1 file reformatted, 3 unchanged)
- Integration tests verify tree composition, execution flow, and state transitions

**Next Step**: BT-1.3.4 - Create default policy implementation (or skip to BT-1.4.1 - Refactor validate_report handler)

---

## 2026-02-18: BT-1.3.2 - Implemented report validation BT nodes

### Task: Implement report validation BT nodes

**Status**: COMPLETE

**Changes**:
- Created `vultron/behaviors/report/nodes.py` with 10 node classes (724 lines)
- Created `test/behaviors/report/test_nodes.py` with 18 comprehensive tests (398 lines)
- Implemented per specs/behavior-tree-integration.md requirements BT-07 and BT-10

**Node Classes Implemented**:

1. **Condition Nodes** (2):
   - `CheckRMStateValid(report_id)`: Check if report already in RM.VALID state (early exit optimization)
   - `CheckRMStateReceivedOrInvalid(report_id)`: Check preconditions for validation

2. **Action Nodes** (6):
   - `TransitionRMtoValid(report_id, offer_id)`: Set report=RM.VALID, offer=ACCEPTED
   - `TransitionRMtoInvalid(report_id, offer_id)`: Set report=RM.INVALID, offer=TENTATIVELY_REJECTED
   - `CreateCaseNode(report_id)`: Create VulnerabilityCase, store case_id in blackboard
   - `CreateCaseActivity(report_id, offer_id)`: Create CreateCase activity, collect addressees
   - `UpdateActorOutbox()`: Append activity_id to actor outbox.items

3. **Policy Nodes** (2 - stubs for Phase 1):
   - `EvaluateReportCredibility(report_id)`: Always returns SUCCESS (stub)
   - `EvaluateReportValidity(report_id)`: Always returns SUCCESS (stub)

**Key Implementation Details**:
- All nodes inherit from `DataLayerCondition` or `DataLayerAction` base classes (from Phase BT-1.2)
- Nodes access DataLayer and actor_id from blackboard (set by BTBridge)
- Blackboard key passing: `CreateCaseNode` → `case_id` → `CreateCaseActivity` → `activity_id` → `UpdateActorOutbox`
- Status updates via `vultron.api.v2.data.status.set_status()` (in-memory STATUS dict)
- Logging at appropriate levels: DEBUG for reads, INFO for state transitions, ERROR for failures

**Test Coverage**:
- 18 tests covering all node classes
- Tests for SUCCESS and FAILURE paths
- Condition node state checks (VALID, RECEIVED, INVALID, no status)
- Action node side effects (status updates, DataLayer persistence, blackboard state)
- Policy node stubs (always SUCCESS)
- Full integration test (9-step validation workflow)
- Idempotency test (duplicate case creation)

**Lessons Learned**:
1. **Import corrections during testing**:
   - `TinyDbDataLayer` (not `TinyDBDataLayer`)
   - `db_path=None` (not `storage=None`)
   - `as_Offer` from `vultron.as_vocab.base.objects.activities.transitive`
   - `as_Service` from `vultron.as_vocab.base.objects.actors`
2. **Blackboard write access**: Test helper must register keys with WRITE access before setting values
3. **Offer validation**: `as_Offer` requires `actor` field (not optional)

**Verification**:
- All 18 new tests passing
- Full test suite: 430 tests passing (412 base + 18 new, no regressions)
- Black formatting applied to both implementation and tests

**Next Step**: BT-1.3.3 - Compose validation behavior tree in `vultron/behaviors/report/validate_tree.py`

---

## 2026-02-18: BT-1.3.1 - Analyzed validate_report handler

### Task: Document procedural logic flow for BT implementation

**Status**: COMPLETE

**Changes**:
- Created comprehensive analysis document in session workspace: `validate_report_analysis.md`
- Documented step-by-step procedural flow (6 phases: rehydration, status updates, case creation, addressee collection, activity generation, outbox update)
- Identified decision points and potential condition nodes for BT implementation
- Compared procedural handler against simulation BT structure (`vultron/bt/report_management/_behaviors/validate_report.py`)
- Mapped proposed BT implementation strategy (Phase 1: minimal match, Phase 2: policy evaluation)

**Key Findings**:

1. **Current Handler Simplifications**:
   - No precondition checks on report state (assumes valid input)
   - No credibility/validity evaluation (implicitly always accepts)
   - Relies on DataLayer duplicate detection for idempotency
   - No early exit optimization

2. **Simulation BT vs. Procedural Handler**:
   - Simulation has explicit precondition checks (`RMinStateReceivedOrInvalid`)
   - Simulation has policy nodes (`EvaluateReportCredibility`, `EvaluateReportValidity`)
   - Simulation has fallback invalidation path (`_InvalidateReport`)
   - Simulation has information gathering loop (`_HandleRmI`)
   - Procedural handler integrates case creation (not in simulation)

3. **Proposed BT Structure** (Phase 1 - Minimal):
   ```
   ValidateReportBT (Sequence)
   ├─ ReadObject(...)                    # Rehydration (4 objects)
   ├─ CheckRMStateValid(...)             # Optional early exit
   ├─ TransitionRMtoValid(...)           # Status updates
   ├─ CreateCase(...)                    # Case creation
   ├─ CreateCaseActivity(...)            # Activity generation
   └─ UpdateActorOutbox(...)             # Outbox update
   ```

4. **DataLayer Access Pattern**:
   - Current: Handler calls `get_datalayer()` directly
   - BT: DataLayer injected via blackboard by `BTBridge` (from Phase BT-1.1)

5. **Required Nodes** (Phase BT-1.3.2):
   - Condition: `CheckRMStateValid`, `CheckRMStateReceivedOrInvalid`
   - Action: `TransitionRMtoValid`, `CreateCase`, `CreateCaseActivity`, `UpdateActorOutbox`
   - Policy: `EvaluateReportCredibility`, `EvaluateReportValidity` (stubs for Phase 1)

**Cross-References**:
- Analysis document: `/Users/adh/.copilot/session-state/669dec54-6467-4768-898d-72612c8242e1/files/validate_report_analysis.md`
- Current handler: `vultron/api/v2/backend/handlers.py::validate_report()`
- Simulation BT: `vultron/bt/report_management/_behaviors/validate_report.py`
- Spec: `specs/behavior-tree-integration.md`

**Verification**:
- All 412 tests still passing
- Analysis document created with detailed flow diagrams and comparison tables
- Ready for Phase BT-1.3.2: Implement report validation BT nodes

**Next Step**: BT-1.3.2 - Implement report validation BT nodes in `vultron/behaviors/report/nodes.py`

---

## 2026-02-18: BT-1.2.1 - Created DataLayer helper nodes

### Task: Implement DataLayer-aware BT helper nodes

**Status**: COMPLETE

**Changes**:
- Created `vultron/behaviors/helpers.py` with base classes and common CRUD nodes
- Created `test/behaviors/test_helpers.py` with comprehensive test coverage (18 tests)
- Implemented per specs/behavior-tree-integration.md requirements:
  - BT-07-001: BT nodes interact with DataLayer via Protocol interface ✅
  - BT-07-002: BT nodes use type-safe DataLayer wrappers ✅
  - BT-07-003: State transitions logged via DataLayer integration helpers ✅

**Implementation Details**:
- **Base classes**:
  - `DataLayerCondition`: Abstract base for condition nodes (check state, no side effects)
  - `DataLayerAction`: Abstract base for action nodes (modify state, side effects)
  - Both provide automatic blackboard setup for `datalayer` and `actor_id` access
- **Common CRUD nodes**:
  - `ReadObject(table, object_id)`: Read from DataLayer, store in blackboard
  - `UpdateObject(object_id, updates)`: Update object (requires prior ReadObject)
  - `CreateObject(table, object_data)`: Create new object in DataLayer
- **Blackboard key handling**:
  - py_trees blackboard keys cannot contain slashes (URL paths cause parsing errors)
  - Solution: Use simplified keys like `object_{last_path_segment}` instead of full URLs
  - Example: `https://example.org/objects/test-123` → blackboard key `object_test-123`
- **Record format handling**:
  - DataLayer `get()` returns dict with `{id_, type_, data_}` structure
  - Helper nodes handle both Record dicts and plain data dicts
  - `UpdateObject` merges updates into `data_` field when present

**Key Learning: py_trees Blackboard Key Restrictions**:
- Blackboard keys are parsed as hierarchical paths
- Keys with slashes like `/https://example` cause "does not have read/write access" errors
- Always use simple, alphanumeric keys with underscores/hyphens only
- For object IDs (which are URLs), extract last path segment: `url.split('/')[-1]`

**Verification**:
- All 18 helper node tests passing
- Full test suite: 412 tests passing (no regressions)
- Test coverage includes:
  - Base class setup and blackboard access
  - CRUD operations (create, read, update)
  - Custom node names
  - Error handling (DataLayer unavailable, object not found)
  - Full CRUD workflow integration test
  - Actor isolation

**Notes**:
- Helper nodes follow Protocol-based design (duck typing, not inheritance)
- Nodes access DataLayer and actor_id from blackboard (set by BTBridge)
- Logging at appropriate levels (DEBUG for reads, INFO for writes, ERROR for failures)
- Ready for Phase BT-1.3: Report validation BT nodes

**Next Step**: BT-1.3.1 - Analyze existing `validate_report` handler

---

## 2026-02-18: BT-1.1.3 - Implemented BT bridge layer

### Task: Implement behavior tree bridge layer for handler-to-BT execution

**Status**: COMPLETE

**Changes**:
- Created `vultron/behaviors/bridge.py` with `BTBridge` class
- Created `test/behaviors/test_bridge.py` with comprehensive test coverage (16 tests)
- Implemented per specs/behavior-tree-integration.md requirements:
  - BT-05-001: BT execution bridge for handler-to-BT invocation ✅
  - BT-05-002: Sets up py_trees context with DataLayer access ✅
  - BT-05-003: Populates blackboard with activity and actor state ✅
  - BT-05-004: Executes tree and returns execution result ✅
  - BT-01-002: BTs execute to completion per invocation ✅
  - BT-01-003: No continuous tick-based polling loops ✅

**Implementation Details**:
- `BTBridge` class serves as adapter between handlers and py_trees execution
- `setup_tree()` creates BehaviourTree with blackboard populated with:
  - `datalayer`: DataLayer instance for persistent state access
  - `actor_id`: Actor executing the tree (for state isolation)
  - `activity`: Optional ActivityStreams activity being processed
  - Custom context data via kwargs
- `execute_tree()` runs single-shot execution with configurable max_iterations (default: 100)
- `execute_with_setup()` convenience method combines setup and execution
- `BTExecutionResult` dataclass returns status, feedback, and errors to handler

**Key Learning: py_trees API**:
- Blackboard keys must be registered with WRITE access to set values
- `BehaviourTree.setup()` (not `setup_with_descendants()`) initializes tree
- `BehaviourTree.tick()` (not `tick_once()`) executes one tick
- `Status` enum: SUCCESS, FAILURE, RUNNING, INVALID

**Verification**:
- All 16 bridge tests passing
- Full test suite: 394 tests passing (no regressions)
- Test coverage includes:
  - Basic setup and execution (SUCCESS/FAILURE/RUNNING states)
  - Blackboard population and access from nodes
  - Max iterations safety limit
  - Exception handling during execution
  - Actor isolation (multiple actors, sequential executions)
  - Convenience method testing

**Notes**:
- Bridge is minimal and focused per prototype approach
- No transaction management or rollback logic (deferred to future)
- Synchronous execution within handler context (meets BT-04-003)
- Ready for Phase BT-1.2: DataLayer-aware BT nodes

**Next Step**: BT-1.2.1 - Create DataLayer helper nodes (conditions and actions)

---

## 2026-02-18: BT-1.1.2 - Created behavior tree directory structure

### Task: Create directory structure for behavior tree implementations

**Status**: COMPLETE

**Changes**:
- Created `vultron/behaviors/` directory with `__init__.py`
- Created `vultron/behaviors/report/` subdirectory with `__init__.py`
- Created `test/behaviors/` directory with `__init__.py`
- Created `test/behaviors/report/` subdirectory with `__init__.py`
- All __init__.py files include docstrings describing purpose

**Verification**:
- Directory structure verified with `tree -L 3`
- All 378 tests pass with new directories in place
- Black formatting applied (no changes needed)

**Notes**:
- Directory structure mirrors planned architecture from `plan/BT_INTEGRATION.md`
- Ready for implementing bridge layer (BT-1.1.3) and helper nodes (BT-1.2.1)
- No imports or code yet—just scaffolding

**Next Step**: BT-1.1.3 - Implement BT bridge layer

---

## 2026-02-18: BT-1.1.1 - Added py_trees dependency

### Task: Add py_trees to project dependencies

**Status**: COMPLETE

**Changes**:
- Added `py-trees>=2.2.0` to `pyproject.toml` dependencies (alphabetically ordered)
- Ran `uv sync` to install the package
- Verified import works: `import py_trees` succeeds
- All 378 tests still pass after adding dependency

**Notes**:
- The package is named `py-trees` in PyPI but imports as `py_trees` in Python
- py_trees module does not expose `__version__` attribute, but the import succeeds and module is functional
- No test regressions after adding the dependency

**Next Step**: BT-1.1.2 - Create behavior tree directory structure

---

## 2026-02-18: BT Integration Gap Analysis (PLAN_prompt.md)

### Gap Analysis Findings

Performed comprehensive analysis comparing `specs/behavior-tree-integration.md` requirements against current `vultron/api/v2` implementation per `prompts/PLAN_prompt.md` instructions.

**Key Discovery**: BT integration is in **design phase only**—no implementation exists yet.

#### Critical Gaps Identified

1. **py_trees Library Not Integrated**
   - `py_trees` NOT in `pyproject.toml` dependencies
   - Simulation code (`vultron/bt/`) uses custom BT engine
   - No py_trees-based handler implementations

2. **No BT Bridge Layer**
   - Missing: `vultron/behaviors/bridge.py` (proposed in spec)
   - Missing: Handler-to-BT execution interface
   - Missing: Blackboard setup with DataLayer injection

3. **No BT Node Implementations**
   - Missing: `vultron/behaviors/` directory entirely
   - Missing: Condition nodes (CheckRMState, CheckEMState, etc.)
   - Missing: Action nodes (TransitionRMto*, CreateCase, etc.)
   - Missing: Policy nodes (EvaluateReportCredibility, etc.)

4. **No Workflow BTs**
   - Missing: Report validation BT (`vultron/behaviors/report/validate_tree.py`)
   - Missing: Case creation BT
   - Missing: Embargo management BTs

5. **CaseActor Creation Gap** (BT-10-002)
   - `validate_report` handler creates `VulnerabilityCase` object
   - **Does NOT create corresponding `CaseActor` service**
   - `CaseActor` class defined in `vultron/case_actor/case_actor.py` but never instantiated
   - Spec requires: "Case creation MUST create corresponding CaseActor (Service)"

#### What IS Working (Baseline)

✅ **Handler Infrastructure**:
- All handlers follow protocol (`@verify_semantics`, synchronous execution, DataLayer integration)
- Sequential FIFO processing meets concurrency requirements (BT-11-001/002)
- Background task execution decouples HTTP response

✅ **Procedural Implementations** (Reference Logic):
- `validate_report`: Complex workflow with status updates, case creation, outbox management
- 5 other report handlers: create, submit, invalidate, ack, close
- These provide reference logic for BT node implementations

✅ **Specifications Defined**:
- `specs/behavior-tree-integration.md` exists with 40+ requirements (BT-01 through BT-11)
- Requirements use RFC 2119 keywords (MUST, SHOULD, MAY)
- Verification criteria defined

#### Comparison: Simulation vs. Prototype

| Aspect | Simulation (`vultron/bt/`) | Prototype API (`vultron/api/v2`) |
|--------|---------------------------|----------------------------------|
| **BT Engine** | Custom engine in `vultron/bt/base/` | None (handlers use procedural logic) |
| **Execution Model** | Tick-based continuous loop | Event-driven, single-shot per handler |
| **Node Types** | BtNode, Sequence, Fallback, Fuzzer | None |
| **State Management** | In-memory Blackboard | DataLayer (TinyDB) persistence |
| **Purpose** | Protocol simulation & exploration | ActivityStreams activity processing |
| **Integration** | Standalone simulation | REST API with persistence |

**Key Insight**: Simulation and prototype are **completely separate systems**. Per BT-02-002, simulation code MUST remain unchanged. BT integration requires **new py_trees-based implementation** for handlers.

#### Implementation Strategy (Updated IMPLEMENTATION_PLAN.md)

Added **Phase BT-1** as top priority per PRIORITIES.md:

1. **BT-1.1**: Infrastructure setup (py_trees dependency, directory structure)
2. **BT-1.2**: DataLayer-aware BT nodes (condition/action base classes)
3. **BT-1.3**: Report validation BT implementation (refactor `validate_report`)
4. **BT-1.4**: Handler refactoring (integrate BT execution)
5. **BT-1.5**: Demo and validation (verify no regressions)
6. **BT-1.6**: Documentation (update specs, lessons learned)

**Success Criteria**: Working POC with `validate_report` using py_trees execution, all tests passing, performance acceptable (P99 < 100ms).

#### Open Questions

1. **Factory Method Reuse**: Can simulation tree factories return py_trees nodes?
   - `plan/BT_INTEGRATION.md` suggests "likely infeasible" due to API differences
   - Recommends: Direct py_trees implementation, use simulation as design reference only
   - Decision: Test feasibility in Phase BT-1; don't block on abstraction

2. **Blackboard vs. Constructor Injection**: Which pattern for DataLayer access?
   - Option A: Pass DataLayer to node constructors (simpler for Phase 1)
   - Option B: Use py_trees blackboard for shared state (explore if valuable)
   - Decision: Start with Option A; evaluate Option B during implementation

3. **Policy Engine Scope**: How complex should `AlwaysAcceptPolicy` be?
   - Phase 1: Simple always-accept stubs with logging
   - Future: Configurable policies, pluggable decision logic
   - Document extension points in code

4. **Performance Impact**: What is acceptable overhead?
   - Target: P99 < 100ms per `plan/BT_INTEGRATION.md`
   - Baseline: Measure current `validate_report` handler timing
   - Compare: Before/after BT integration

#### Files to Create (Phase BT-1)

```
vultron/behaviors/
├── __init__.py
├── bridge.py              # BT execution bridge
├── helpers.py             # DataLayer-aware base nodes
└── report/
    ├── __init__.py
    ├── nodes.py           # Validation-specific nodes
    ├── validate_tree.py   # ValidateReportBT composite
    └── policy.py          # AlwaysAcceptPolicy

test/behaviors/
├── __init__.py
├── test_bridge.py         # Bridge unit tests
├── test_helpers.py        # Base node tests
└── report/
    ├── __init__.py
    ├── test_nodes.py      # Node unit tests
    └── test_validate_tree.py  # Integration tests
```

#### Cross-References

- **Plan**: `plan/BT_INTEGRATION.md` (detailed architecture)
- **Spec**: `specs/behavior-tree-integration.md` (requirements)
- **Priority**: `plan/PRIORITIES.md` (BT integration is top priority)
- **Updated**: `plan/IMPLEMENTATION_PLAN.md` (added Phase BT-1 tasks)

---
