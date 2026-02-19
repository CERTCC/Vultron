# Behavior Tree Integration Plan

**Created**: 2026-02-17  
**Last Updated**: 2026-02-18  
**Status**: Planning - Refined  
**Related**: ADR-0002 (Use Behavior Trees), ADR-0007 (Behavior Dispatcher)

---

## Prototype Implementation Context

This document describes the **next iteration** of the Vultron protocol
prototype.

**Project Phase**: Research Prototype

- This is NOT a production-ready system
- Focus: Demonstrate protocol feasibility and BT integration viability
- Priorities: Simplicity, correctness, and clarity over performance optimization
- Architecture decisions should be "production-informed" but implementation can
  be simplified

**Prototype Approach**:

- Functionality can be stubbed with clear extension points for future work
- Example: Policy engine that returns default decisions but has clear interface
  for complex logic
- Example: Message authenticator that validates structure but defers
  cryptographic verification
- Distinction: Stubs ≠ fuzzer nodes (stubs are deterministic placeholders;
  fuzzers simulate non-deterministic behavior for protocol exploration)

**Actor Isolation and BT Domains**:

Each actor exists in its own behavior tree execution domain with isolated state:

- **Actor A** and **Actor B** have separate BT blackboards with no shared access
- Interaction happens exclusively through Vultron Protocol message exchange (
  ActivityStreams)
- Clean separation models real-world CVD: independent organizations making
  autonomous decisions
- Each actor's internal state (RM/EM/CS state machines) is private

**CaseActor as Resource Manager**:

The CaseActor is an ActivityStreams Service object that manages a
VulnerabilityCase:

- **Purpose**: Provide canonical case state and coordinate multi-actor workflows
- **Scope**: One CaseActor per VulnerabilityCase (1:1 relationship)
- **Lifecycle**: Created during report validation; exists until case closure
- **Authority**: Enforces case-level rules and authorization (e.g., only case
  owner can close case)
- **Communication Hub**: Broadcasts case updates to CaseParticipants via direct
  messages

**Case Ownership Model**:

- **Case Owner**: Organizational Actor (e.g., vendor) responsible for case
  decisions
- **CaseActor**: Service managing case state (NOT the case owner)
- **Authorization**: `vultron_as:CaseOwnerActivity` in ontology defines
  owner-restricted actions
- **Initial Owner**: Typically the recipient of the VulnerabilityReport Offer
- **Ownership Transfer**: Explicit workflow transferring responsibility between
  actors

**Factory Methods and Code Reuse** (ADR-0004):

The existing simulation in `vultron/bt` uses factory methods (
`vultron/bt/base/factory.py`) to create BT nodes:

- **Purpose**: Abstract node creation to allow engine swapping
- **Current Use**: Custom BT engine for simulation with fuzzer nodes
- **Simulation Example**: `vultron/bt/report_management/_behaviors/validate_report.py` uses `sequence_node()` and `fallback_node()` factories
- **Integration Challenge**: py_trees uses different node classes and APIs than custom engine
- **Phase 1 Exploration**: Test whether factories can return py_trees nodes with minimal changes
- **Likely Outcome**: Direct py_trees implementation (not factory-based) due to API incompatibilities
- **Benefit if Feasible**: Reuse high-level BT structure (composition logic) from simulation trees
- **Risk Mitigation**: If infeasible, implement new trees directly in py_trees using simulation trees as *design reference* only

**Recommended Phase 1 Approach**:

1. Start with direct py_trees implementation (don't attempt factory reuse initially)
2. Use simulation tree structure as architectural guide:
   - Match node composition (sequence/fallback hierarchy)
   - Preserve semantic intent (preconditions, actions, state transitions)
   - Translate fuzzer nodes to deterministic policy nodes
3. If time permits, explore factory method compatibility as stretch goal
4. Document findings in Phase 1 lessons learned

**Key Insight**: Prioritize working POC over code reuse abstractions; demonstrate BT integration value before optimizing for maintainability

**Concurrency and Data Layer Integrity**:

Concurrent handler execution may require coordination to prevent race
conditions:

**Challenge**:

- Multiple messages processed concurrently (BackgroundTasks)
- BT executions may overlap when accessing shared resources (e.g.,
  VulnerabilityCase)
- Side effects of one BT execution could affect another's behavior

**Prototype Approach (Simple First)**:

- **Sequential Processing**: Process messages in FIFO order with single-threaded
  execution
- **Benefits**: Eliminates race conditions; simple to implement and reason about
- **Implementation**: Queue with lock or single async worker processing inbox
- **Performance**: Acceptable for prototype (asynchronous to HTTP layer, still
  returns 202 immediately)

**Future Optimization Paths** (if needed):

- Optimistic locking: Version numbers on VulnerabilityCase objects
- Resource-level locking: Lock specific case during update operations
- Actor-level concurrency: Allow parallel execution for different actors,
  sequential per-actor
- CaseActor as coordinator: Require explicit lock acquisition before case
  mutations

**Design Principle**: Prioritize correctness over performance in prototype
phase; measure before optimizing

**Mapping Existing BT Structures to Handlers**:

Current handler implementations can leverage existing BT models in `vultron/bt` as design references:

**Simulation Trees as Design Templates**:

The simulation trees provide high-level process flow and state machine logic that can guide prototype implementation:

| Handler Function | Simulation BT Reference | Key Behavior |
|------------------|-------------------------|--------------|
| `validate_report()` | `vultron/bt/report_management/_behaviors/validate_report.py:RMValidateBt` | Fallback: already valid OR (gather info + evaluate + transition) OR invalidate |
| `invalidate_report()` | `vultron/bt/report_management/_behaviors/validate_report.py:_InvalidateReport` | Sequence: transition to INVALID + emit RI message |
| `close_report()` | `vultron/bt/report_management/_behaviors/close_report.py:RMCloseBt` | Sequence: check preconditions + transition to CLOSED + emit RC message |
| `prioritize_report()` | `vultron/bt/report_management/_behaviors/prioritize_report.py:RMPrioritizeBt` | Policy-driven: evaluate priority + transition to ACCEPTED or DEFERRED |
| `do_work()` | `vultron/bt/report_management/_behaviors/do_work.py:RMDoWorkBt` | Complex workflow: fix development, testing, deployment orchestration |

**Translation Strategy**:

1. **Identify Simulation Tree**: Find corresponding tree in `vultron/bt/report_management/_behaviors/`
2. **Extract Structure**: Note sequence/fallback composition and node ordering
3. **Map Conditions**: Convert condition nodes (e.g., `RMinStateValid`) to py_trees condition behaviors checking DataLayer state
4. **Replace Fuzzers**: Convert fuzzer nodes (e.g., `EvaluateReportCredibility`) to deterministic policy nodes with configurable defaults
5. **Preserve Semantics**: Keep state transition order and precondition checks intact
6. **Add Persistence**: Wrap state changes with DataLayer update operations
7. **Emit Activities**: Generate ActivityStreams activities for outbox where simulation emits messages

**Example Translation** (RMValidateBt):

Simulation structure (factory-based):
```python
RMValidateBt = fallback_node(
    "RMValidateBt",
    RMinStateValid,           # Condition: already valid?
    _HandleRmI,               # Sequence: if invalid, gather more info
    _ValidationSequence,      # Sequence: evaluate + transition
    _InvalidateReport,        # Fallback: if validation fails, invalidate
)
```

Prototype structure (py_trees-based):
```python
class ValidateReportBT(py_trees.composites.Selector):  # Selector = Fallback
    def __init__(self, blackboard):
        children = [
            CheckRMStateValid(blackboard),              # Already valid? Success
            HandleInvalidState(blackboard),             # Gather validation info if needed
            ValidationSequence(blackboard),             # Evaluate credibility/validity + transition
            InvalidateReportSequence(blackboard),       # Fallback: invalidate if validation fails
        ]
        super().__init__(children=children, name="ValidateReportBT")
```

**Important Notes**:

- Simulation trees contain fuzzer nodes that MUST be replaced with deterministic logic
- Simulation trees branch on message types; handlers already know semantic type (skip branching)
- Simulation trees represent full message-processing pipelines; handlers focus on single semantic action
- **When conflicts arise**: Follow ActivityPub documentation (`docs/howto/activitypub/activities/`) over simulation trees

**Source of Truth Priority**:

1. **Primary**: `docs/howto/activitypub/activities/*.md` (process descriptions, message examples)
2. **Secondary**: `vultron/bt/report_management/_behaviors/*.py` (state machine logic, composition)
3. **Tertiary**: `docs/topics/behavior_logic/*.md` (conceptual diagrams, motivation)

---

## Executive Summary

This document outlines a plan to integrate Behavior Tree (BT) logic with the
ActivityStreams-based handler system in `vultron/api/v2/`. The goal is to
leverage the process modeling advantages of behavior trees for **prototype
execution** while maintaining the existing simulation capability in
`vultron/bt/`.

**Key Architectural Decisions**:

1. **Use py_trees for Prototype Handlers**: Handler implementations will use the
   mature `py_trees` library, providing robust BT infrastructure, visualization
   tools, and debugging support. The existing `vultron/bt/` simulation code
   remains unchanged for protocol exploration.

2. **Event-Driven BT Execution**: Rather than one monolithic behavior tree per
   actor, handlers will trigger focused behavior trees specific to each message
   semantic type. Each handler invocation sets up BT context and executes the
   relevant tree to completion.

3. **DataLayer as Blackboard**: The existing data layer serves as the persistent
   state store. Behavior trees will read from and write to the data layer
   directly, avoiding duplicate state management systems.

4. **Case Creation Workflow**: Report validation triggers VulnerabilityCase
   creation, which includes creating a corresponding CaseActor (ActivityStreams
   Service) that owns and processes case-related messages.

**Key Challenge**: Bridging simulation-focused BT models with prototype
event-driven handlers while preserving composability, testability, and alignment
with CVD protocol documentation.



---

## Background

### Current Architecture: Two Parallel Systems

#### 1. Behavior Tree System (`vultron/bt/`)

**Purpose**: Simulate CVD process logic for protocol testing and exploration

**Key Components**:

- **BT Engine**: Base classes in `vultron/bt/base/` (BtNode, composites,
  decorators, Blackboard)
- **Process Models**: Report Management, Embargo Management, Case State
  transitions
- **Message Handling**: Inbound/outbound message behaviors (
  `vultron/bt/messaging/`)
- **Fuzzer Nodes**: Stochastic simulation nodes (e.g., `AlmostAlwaysSucceed`,
  `ProbablySucceed`)
- **CVD Protocol BT**: `CvdProtocolBt` - monolithic tree modeling full CVD
  lifecycle

**Design for Simulation**:

- Tick-based execution (continuous loop)
- Probabilistic decision nodes for state space exploration
- Blackboard state management (in-memory dict)
- No persistence or external integration

**Strengths**:

- ✅ Hierarchical, composable process modeling
- ✅ Clear preconditions and state transitions
- ✅ Matches documentation (`docs/topics/behavior_logic/`)
- ✅ Implements CVD protocol state machines

**Limitations for Prototype Implementation**:

- ❌ Fuzzer nodes simulate rather than implement real logic
- ❌ No integration with ActivityStreams vocabulary
- ❌ No data layer persistence
- ❌ Designed for continuous tick loop, not event-driven processing

#### 2. Handler System (`vultron/api/v2/backend/handlers.py`)

**Purpose**: Process real ActivityStreams activities with persistence and
event-driven execution

**Key Components**:

- **Semantic Extraction**: Maps (Activity Type, Object Type) →
  MessageSemantics (`vultron/semantic_map.py`)
- **Behavior Dispatcher**: Routes DispatchActivity to handlers via
  `SEMANTIC_HANDLER_MAP` (`vultron/behavior_dispatcher.py`)
- **Handler Functions**: Business logic for each semantic type with
  `@verify_semantics` decorator
- **Data Layer**: TinyDB persistence with Protocol abstraction (
  `vultron/api/v2/datalayer/`)
- **Inbox Processing**: FastAPI endpoint with BackgroundTasks (
  `vultron/api/v2/routers/actors.py`)

**Current Implementation Status** (as of 2026-02-18):

- ✅ 7/36 handlers have complete business logic (19%)
    - Report workflow: `create_report`, `submit_report`, `validate_report`,
      `invalidate_report`, `ack_report`, `close_report`
    - Special handlers: `unknown` (handles unrecognized semantic types)
- ⚠️ 29/36 handlers are stubs (log at DEBUG, no side effects)
- ✅ All handlers follow protocol: decorator, signature, registration
- ✅ Infrastructure complete: semantic extraction, dispatcher, data layer, inbox
  endpoint
- ✅ Demo script complete: Three working workflows demonstrating report lifecycle

**Design for Prototype Implementation**:

- Event-driven (one activity → one handler invocation)
- HTTP 202 asynchronous processing via BackgroundTasks
- Persistent state via data layer
- Type-safe ActivityStreams processing

**Strengths**:

- ✅ Real ActivityStreams message processing
- ✅ Persistent state in data layer
- ✅ Type-safe with Pydantic models
- ✅ Semantic extraction matching BT message types
- ✅ Event-driven execution model

**Limitations**:

- ❌ Business logic is procedural (not hierarchical)
- ❌ State transitions are implicit in code
- ❌ No composability or reusability of business logic
- ❌ Process flow not visible in structure
- ❌ Most handlers lack implemented business logic

---

## Integration Goals

### Primary Objectives

1. **Process Logic Reuse**: Leverage BT models for state transitions and
   decision flow, adapted from simulation to prototype implementation
2. **Prototype BT Infrastructure**: Use `py_trees` library for mature,
   well-tested behavior tree execution in prototype handlers
3. **Event-Driven Execution**: Handlers trigger focused behavior trees specific
   to message semantics (not monolithic tick loop)
4. **Unified State Management**: DataLayer serves as persistent state store;
   eliminate separate blackboard/datalayer duplication
5. **Case Workflow Clarity**: Validate→CreateCase→CreateCaseActor flow
   explicitly modeled in BT structure
6. **Maintainability**: Keep BT models as high-level process documentation
   matching specifications
7. **Simulation Preservation**: Retain existing `vultron/bt/` simulation
   capability unchanged
8. **Handler Completion**: Implement remaining stub handlers using BT logic
   where appropriate
9. **Command-Line BT Execution**: Support triggering behavior trees
   independently for testing and agentic AI contexts

### Non-Goals

- ❌ **Not** refactoring existing `vultron/bt/` simulation to use `py_trees`
- ❌ **Not** replacing the semantic extraction or dispatcher infrastructure
- ❌ **Not** changing the ActivityStreams-based API surface or inbox endpoint
  behavior
- ❌ **Not** introducing continuous tick-based simulation into prototype (
  single-shot execution only)
- ❌ **Not** bypassing the handler protocol (handlers remain entry points with
  `@verify_semantics`)
- ❌ **Not** specifying exact implementation signatures or method details (design
  intent only)

---

## Proposed Architecture

### Hybrid Approach: Handlers Orchestrate Focused BTs

**Key Insights**:

1. **Event-Driven BT Invocation**: Handlers act as entry points that trigger
   focused behavior trees, not monolithic CVD lifecycle trees
2. **py_trees Foundation**: Production trees use `py_trees` library for robust
   execution, visualization, and debugging
3. **DataLayer as State Store**: BTs read/write persistent state via DataLayer
   Protocol; no separate blackboard sync
4. **Semantic-Specific Trees**: Each MessageSemantics type has a corresponding
   behavior tree encapsulating that workflow

**Architecture Overview**:

```
┌─────────────────────────────────────────────────────────┐
│ FastAPI Inbox Endpoint                                  │
│ POST /actors/{actor_id}/inbox (inbox_handler.py)        │
│ - HTTP 202 response within 100ms                        │
│ - Queue via BackgroundTasks                             │
│ - Rehydrate activity before dispatch                    │
└─────────────────────┬───────────────────────────────────┘
                      │ (ActivityStreams Activity, rehydrated)
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Semantic Extraction (semantic_map.py)                   │
│ Pattern Matching: (Activity Type, Object Type)          │
│                   → MessageSemantics.SUBMIT_REPORT      │
│ Uses SEMANTICS_ACTIVITY_PATTERNS (ordered matching)     │
└─────────────────────┬───────────────────────────────────┘
                      │ (DispatchActivity)
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Behavior Dispatcher (behavior_dispatcher.py)            │
│ DirectActivityDispatcher (synchronous)                  │
│ Lookup: SEMANTIC_HANDLER_MAP[semantic_type]             │
│ Invoke: handler(dispatchable)                           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Handler Function (handlers.py)                          │
│ @verify_semantics(MessageSemantics.SUBMIT_REPORT)      │
│ def submit_report(dispatchable: DispatchActivity):      │
│     # Option A: Pure procedural (current)               │
│     # ... business logic ...                            │
│                                                         │
│     # Option B: BT-orchestrated (proposed)              │
│     result = execute_bt_for_handler(                    │
│         bt_node=ProcessRMMessagesBt,                    │
│         activity=dispatchable.payload,                  │
│         actor_id=extract_actor_id(dispatchable),        │
│     )                                                   │
│     return result                                       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ BT Bridge Layer (NEW: vultron/api/v2/bt_bridge.py)    │
│                                                         │
│ 1. Load actor state from data layer                     │
│ 2. Create BT-compatible blackboard (DataLayerBacked)    │
│ 3. Populate blackboard: activity, current_message, etc. │
│ 4. Instantiate BT with prototype node implementations   │
│ 5. Execute BT: single-shot tick loop (max iterations)   │
│ 6. Commit blackboard changes to data layer on success   │
│ 7. Return BTExecutionResult (status, errors, effects)   │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │                           │
        ▼                           ▼
┌──────────────────┐      ┌──────────────────────┐
│ Behavior Tree    │      │ Data Layer Protocol  │
│ Execution        │◄────►│ (TinyDB backend)     │
│ (vultron/bt/)    │      │ - Actor state        │
│ - Production     │      │ - Reports, Cases     │
│   nodes          │      │ - Activities         │
└──────────────────┘      └──────────────────────┘
```

**Critical Design Points**:

1. **Handler Protocol Preserved**: BT integration does NOT bypass
   `@verify_semantics`, `DispatchActivity`, or handler registration
2. **DataLayer as Source of Truth**: BTs interact with DataLayer for all state
   operations; no separate blackboard persistence
3. **Single-Shot Execution**: BTs execute to completion (or max iterations) per
   handler invocation
4. **Parallel Implementations**: Production trees (py_trees-based) coexist with
   simulation trees (custom BT engine)
5. **Event-Driven Entry**: Handlers remain event-driven entry points (not
   tick-based polling)
6. **VulnerabilityCase Creation**: Report validation triggers case creation,
   which creates CaseActor (Service) for case message handling
7. **Command-Line Support**: Behavior trees can be invoked independently via CLI
   for testing and AI agent contexts

### Key Components Overview

The integration adds a behavior execution layer between handlers and the data
layer:

**New Components** (to be designed in implementation phase):

1. **BT Execution Bridge** (`vultron/behaviors/bridge.py` or similar):
    - Entry point for handler-to-BT invocation
    - Sets up py_trees context with DataLayer access
    - Executes tree to completion (single-shot)
    - Returns execution result to handler
    - **Prototype Simplification**: Synchronous execution within handler; no
      complex async state management

2. **Prototype Behavior Trees** (using `py_trees`):
    - Focused trees for specific workflows (e.g., ValidateReportBT,
      CreateCaseBT)
    - Node implementations interact with DataLayer directly
    - Match structure and semantics of simulation trees where applicable
    - Organized by workflow category (report, case, embargo)
    - **Prototype Simplification**: Deterministic nodes (no fuzzer nodes);
      configurable default policies for human-decision points

3. **DataLayer Integration Utilities**:
    - Helpers for common patterns (state transitions, object creation, outbox
      management)
    - Type-safe wrappers for data layer operations within BT nodes
    - Commit-on-success semantics (no complex rollback for prototype)
    - **Prototype Simplification**: Simple helper functions; defer complex
      transaction management to future iterations

4. **Command-Line Interface** (optional for Phase 1):
    - CLI commands to invoke specific behavior trees for testing
    - Support for AI agent integration and standalone workflow execution
    - **Prototype Simplification**: Basic invoke-and-log interface; advanced
      features deferred

**Directory Structure** (proposed, notional):

```
vultron/
  bt/                    # Existing simulation (unchanged)
    base/                # Custom BT engine for simulation
    report_management/   # Simulation fuzzer nodes
    embargo_management/
    case_state/
  behaviors/             # NEW: Prototype behavior trees
    bridge.py            # BT execution bridge
    helpers.py           # DataLayer integration utilities
    report/              # Report workflow trees (py_trees)
    case/                # Case workflow trees
    embargo/             # Embargo workflow trees
  api/v2/
    backend/
      handlers.py        # Handlers invoke behaviors/*
    datalayer/           # Existing DataLayer (state store for BTs)
```

**Note**: Exact directory structure will be determined during Phase 1 POC based
on practical experience with py_trees integration.

### Example: Report Validation Workflow

To illustrate the integration approach, consider the report validation workflow:

**Current Procedural Handler** (
`vultron/api/v2/backend/handlers.py:validate_report`):

```python
@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
# 1. Rehydrate nested objects
# 2. Validate report exists
# 3. Update offer status → ACCEPTED
# 4. Update report status → VALID
# 5. Create VulnerabilityCase
# 6. Create CaseActor (Service) for the case
# 7. Add CreateCase activity to actor outbox
# 8. Persist all changes via DataLayer
```

**BT-Powered Approach** (proposed):

```python
@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    # Handler delegates to BT execution bridge
    result = execute_bt_for_handler(
            bt_tree=ValidateReportBT,
            activity=dispatchable.payload,
            actor_id=extract_actor_id(dispatchable),
    )
    # BT returns SUCCESS/FAILURE; handler logs result
    if result.status == BTStatus.FAILURE:
        logger.error(f"Validation failed: {result.errors}")
        raise ValidationError(result.errors)
```

**BT Tree Structure** (adapted from
`vultron/bt/report_management/_behaviors/validate_report.py:RMValidateBt`):

- **Fallback Node** (succeeds if any child succeeds):
    - **Condition**: RMinStateValid (already validated? short-circuit to
      success)
    - **Sequence** (all must succeed):
        - **Condition**: RMinStateReceivedOrInvalid (check precondition)
        - **Action**: EvaluateReportCredibility (organizational policy)
        - **Action**: EvaluateReportValidity (organizational policy)
        - **Sequence** (perform validation):
            - **Action**: TransitionRMtoValid (RM state machine)
            - **Action**: CreateCase (includes CaseActor creation subtree)
            - **Action**: EmitResponseActivities (add to outbox)

**Benefits**:

- Process flow visible in tree structure (matches documentation)
- Reusable nodes (e.g., CreateCase used in multiple workflows)
- Testable in isolation from HTTP layer
- Composable for complex workflows
- Policy decisions (credibility, validity evaluation) encapsulated in action
  nodes with clear extension points

---

## Implementation Phases

### Phase 1: Foundation and Proof of Concept

**Goal**: Demonstrate BT execution from a single handler using py_trees

**Scope**: Report validation workflow with end-to-end BT execution paralleling `scripts/receive_report_demo.py`

**Key Reference Documents**:

- Process documentation (ActivityStreams): `docs/howto/activitypub/activities/report_vulnerability.md`
- BT design (simulation): 
  - `docs/topics/behavior_logic/rm_bt.md` - Report Management state machine
  - `docs/topics/behavior_logic/rm_validation_bt.md` - Validation behavior tree
  - `docs/topics/behavior_logic/reporting_bt.md` - Reporting process overview
  - `docs/topics/behavior_logic/msg_rm_bt.md` - RM message handling
- Existing simulation code: `vultron/bt/report_management/_behaviors/validate_report.py`
- Current handler: `vultron/api/v2/backend/handlers.py:validate_report`

**Key Objectives**:

1. Set up `vultron/behaviors/` directory with py_trees dependency
2. Create execution bridge for handler-to-BT invocation
3. Implement report validation workflow as py_trees behavior tree:
   - Convert fuzzer nodes to deterministic policy nodes
   - Integrate with DataLayer for state persistence
   - Handle VulnerabilityCase and CaseActor creation
4. Create new demo script (`scripts/receive_report_bt_demo.py`) mirroring existing demo
5. Add Docker Compose service for BT demo (parallel to `receive-report-demo`)
6. Validate approach with existing test suite (no regressions)

**Demonstration Workflows** (matching current demo):

The Phase 1 POC must demonstrate all three report lifecycle workflows:

1. **Accept Workflow**: 
   - Submit report (Offer VulnerabilityReport)
   - Validate report (Accept Offer → transition RM to VALID)
   - Create VulnerabilityCase
   - Create CaseActor (ActivityStreams Service)
   - Add originator and receiver as CaseParticipants
   - Add CreateCase activity to actor outbox

2. **Invalidate Workflow**:
   - Submit report (Offer VulnerabilityReport)
   - Invalidate report (TentativeReject Offer → transition RM to INVALID)
   - Log decision with audit trail

3. **Reject and Close Workflow**:
   - Submit report (Offer VulnerabilityReport)
   - Invalidate report (TentativeReject Offer)
   - Close report (Reject Offer → transition RM to CLOSED)

**CaseActor Requirements**:

The CaseActor creation workflow must:

- Create ActivityStreams Service object with case context
- Assign unique ID (e.g., `urn:vultron:case:actor:{case_id}`)
- Add CaseActor to organization's actor registry (for message routing)
- Add CaseActor as CaseParticipant in VulnerabilityCase
- Enable CaseActor to receive case-related messages (e.g., AddReportToCase)
- Log CaseActor creation at INFO level

**BT Execution Logging**:

All BT executions must log:

- Tree invocation (INFO): Handler name, semantic type, activity ID
- Node execution (DEBUG): Node name, status (SUCCESS/FAILURE/RUNNING)
- State transitions (INFO): Before/after states with clear description
- Policy decisions (INFO): Credibility evaluation, validity evaluation results
- DataLayer operations (DEBUG): Create/update/read operations
- Errors (ERROR): Exception details, activity context, recovery actions

**Success Criteria**:

- One handler successfully triggers py_trees-based BT
- All three demo workflows complete successfully
- State transitions persist to DataLayer
- VulnerabilityCase and CaseActor creation working
- Test suite passes without regressions
- Performance acceptable for proof-of-concept (P99 < 200ms for POC)
- BT execution visible in logs for debugging

**Deliverable**: 

- Working proof-of-concept demonstrating feasibility
- New demo script and Docker Compose service
- Documentation of lessons learned for Phase 2 planning

---

### Phase 2: Report Management Workflows

**Goal**: Complete all report workflow handlers using behavior trees

**Scope**: Extend BT integration to all 6 report-related handlers

**Key Objectives**:

- Implement behavior trees for remaining report workflows
- Establish patterns for state transitions, validation, and message emission
- Ensure demo scripts (`scripts/receive_report_demo.py`) work with BT execution
- Validate state transitions match protocol documentation

**Success Criteria**:

- All report handlers use BT logic
- Demo script passes with BT execution
- State transitions match documentation (
  `docs/topics/behavior_logic/msg_rm_bt.md`)
- No test regressions

**Deliverable**: Complete RM message processing via behavior trees

---

## Phase 1 Implementation Guide

This section provides concrete guidance for Phase 1 POC development based on analysis of existing code and requirements.

### Starting Point: Direct py_trees Implementation

**Recommended Approach**: Implement prototype behavior trees directly using py_trees classes, using simulation trees as architectural reference.

**Rationale**:
- Fastest path to working POC (no abstraction layer development)
- Validates BT integration value before optimizing for code reuse
- Allows Phase 1 team to learn py_trees APIs through direct use
- Simulation trees provide clear design template for composition

**Implementation Pattern**:

1. **Study Simulation Tree**: Read corresponding tree in `vultron/bt/report_management/_behaviors/`
2. **Identify Structure**: Note sequence/fallback composition and preconditions
3. **Create py_trees Composite**: Use `py_trees.composites.Sequence` or `Selector` (fallback)
4. **Implement Child Behaviors**: Create `py_trees.behaviour.Behaviour` subclasses for conditions and actions
5. **Wire to DataLayer**: Access persistent state via blackboard-wrapped DataLayer
6. **Add Logging**: Log at appropriate levels per structured logging requirements
7. **Test Incrementally**: Unit test each behavior, integration test full tree

### Behavior Tree Node Types for Phase 1

**Condition Nodes** (check state, return SUCCESS/FAILURE):

```python
import py_trees

class CheckRMStateValid(py_trees.behaviour.Behaviour):
    """Check if report management state is VALID."""
    
    def __init__(self, actor_id: str, report_id: str, datalayer: DataLayer):
        super().__init__(name="CheckRMStateValid")
        self.actor_id = actor_id
        self.report_id = report_id
        self.datalayer = datalayer
    
    def update(self) -> py_trees.common.Status:
        # Read report from data layer
        report = self.datalayer.read(self.report_id)
        
        if report and report.status == ReportStatus.VALID:
            self.logger.debug(f"Report {self.report_id} is VALID")
            return py_trees.common.Status.SUCCESS
        else:
            self.logger.debug(f"Report {self.report_id} is not VALID")
            return py_trees.common.Status.FAILURE
```

**Action Nodes** (modify state, return SUCCESS/FAILURE):

```python
class TransitionRMtoValid(py_trees.behaviour.Behaviour):
    """Transition report management state to VALID."""
    
    def __init__(self, actor_id: str, report_id: str, offer_id: str, datalayer: DataLayer):
        super().__init__(name="TransitionRMtoValid")
        self.actor_id = actor_id
        self.report_id = report_id
        self.offer_id = offer_id
        self.datalayer = datalayer
    
    def update(self) -> py_trees.common.Status:
        try:
            # Read report and offer
            report = self.datalayer.read(self.report_id)
            offer = self.datalayer.read(self.offer_id)
            
            # Update statuses
            old_report_status = report.status
            report.status = ReportStatus.VALID
            offer.status = OfferStatus.ACCEPTED
            
            # Persist changes
            self.datalayer.update(report.as_id, object_to_record(report))
            self.datalayer.update(offer.as_id, object_to_record(offer))
            
            self.logger.info(
                f"Report {self.report_id} transitioned from {old_report_status} to VALID"
            )
            return py_trees.common.Status.SUCCESS
            
        except Exception as e:
            self.logger.error(f"Failed to transition report to VALID: {e}")
            return py_trees.common.Status.FAILURE
```

**Policy Nodes** (configurable decision logic):

```python
class EvaluateReportCredibility(py_trees.behaviour.Behaviour):
    """Evaluate report credibility using organizational policy."""
    
    def __init__(self, report_id: str, datalayer: DataLayer, policy: ReportValidationPolicy):
        super().__init__(name="EvaluateReportCredibility")
        self.report_id = report_id
        self.datalayer = datalayer
        self.policy = policy
    
    def update(self) -> py_trees.common.Status:
        report = self.datalayer.read(self.report_id)
        
        if self.policy.is_credible(report):
            self.logger.info(f"Report {self.report_id} evaluated as credible")
            return py_trees.common.Status.SUCCESS
        else:
            self.logger.warning(f"Report {self.report_id} evaluated as not credible")
            return py_trees.common.Status.FAILURE
```

**Default Policy Implementation** (for Phase 1):

```python
class AlwaysAcceptPolicy:
    """Default policy that accepts all reports (prototype simplification)."""
    
    def is_credible(self, report: VulnerabilityReport) -> bool:
        logger.info(f"Policy: Accepting report {report.as_id} as credible (default policy)")
        return True
    
    def is_valid(self, report: VulnerabilityReport) -> bool:
        logger.info(f"Policy: Accepting report {report.as_id} as valid (default policy)")
        return True
```

### Composite Tree Example

```python
class ValidateReportBT(py_trees.composites.Selector):
    """
    Behavior tree for report validation workflow.
    
    Based on: vultron/bt/report_management/_behaviors/validate_report.py:RMValidateBt
    
    Structure:
    - Fallback (Selector) over:
      1. Already valid? (short-circuit success)
      2. Validation sequence: evaluate credibility, evaluate validity, transition to VALID
      3. Invalidation fallback: transition to INVALID if validation fails
    """
    
    def __init__(self, actor_id: str, report_id: str, offer_id: str, 
                 datalayer: DataLayer, policy: ReportValidationPolicy):
        
        # Create child behaviors
        check_already_valid = CheckRMStateValid(actor_id, report_id, datalayer)
        
        validation_sequence = py_trees.composites.Sequence(
            name="ValidationSequence",
            children=[
                CheckRMStateReceivedOrInvalid(actor_id, report_id, datalayer),
                EvaluateReportCredibility(report_id, datalayer, policy),
                EvaluateReportValidity(report_id, datalayer, policy),
                TransitionRMtoValid(actor_id, report_id, offer_id, datalayer),
            ]
        )
        
        invalidation_sequence = py_trees.composites.Sequence(
            name="InvalidationSequence",
            children=[
                TransitionRMtoInvalid(actor_id, report_id, offer_id, datalayer),
            ]
        )
        
        # Initialize selector (fallback) with children
        super().__init__(
            name="ValidateReportBT",
            children=[
                check_already_valid,
                validation_sequence,
                invalidation_sequence,
            ]
        )
```

### Handler Integration Pattern

```python
@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    """
    Process a ValidateReport activity (Accept(Offer(VulnerabilityReport))).
    
    Uses behavior tree execution for business logic.
    """
    activity = dispatchable.payload
    
    # Extract context
    actor_id = activity.actor
    offer = activity.as_object  # Accept's object is the Offer
    report = offer.as_object    # Offer's object is the VulnerabilityReport
    
    logger.info(f"Actor '{actor_id}' validating report '{report.as_id}' via BT")
    
    # Get data layer
    dl = get_datalayer()
    
    # Create policy (default for Phase 1)
    policy = AlwaysAcceptPolicy()
    
    # Instantiate behavior tree
    bt = ValidateReportBT(
        actor_id=actor_id,
        report_id=report.as_id,
        offer_id=offer.as_id,
        datalayer=dl,
        policy=policy,
    )
    
    # Execute tree (single-shot)
    bt.setup_with_descendants()
    final_status = bt.tick_once()
    
    if final_status == py_trees.common.Status.SUCCESS:
        logger.info(f"Report validation succeeded via BT")
        
        # If validation succeeded and created case, handle case actor creation
        # (This would be in a subtree, but shown here for clarity)
        # create_case_workflow(actor_id, report, dl)
        
    elif final_status == py_trees.common.Status.FAILURE:
        logger.warning(f"Report validation failed via BT")
    else:
        logger.error(f"BT execution incomplete (RUNNING status unexpected)")
        raise VultronBTExecutionError("BT did not complete")
```

### DataLayer Integration Pattern

**Option A: Pass DataLayer to Node Constructors** (Recommended for Phase 1)

```python
# Simple, explicit, no global state
node = TransitionRMtoValid(actor_id, report_id, offer_id, datalayer=dl)
```

**Option B: Use py_trees Blackboard for Shared State** (Explore in Phase 1)

```python
# Blackboard provides shared key-value store across tree
blackboard = py_trees.blackboard.Client(name="ValidateReportBT")
blackboard.register_key(key="datalayer", access=py_trees.common.Access.READ)
blackboard.datalayer = dl

# Nodes access via blackboard
class TransitionRMtoValid(py_trees.behaviour.Behaviour):
    def setup(self):
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(key="datalayer", access=py_trees.common.Access.READ)
    
    def update(self):
        dl = self.blackboard.datalayer
        # ... use dl ...
```

**Recommendation**: Start with Option A (constructor injection) for simplicity; explore Option B if blackboard proves valuable for complex trees.

### Testing Strategy for Phase 1

**1. Unit Tests for Individual Behaviors**:

```python
def test_check_rm_state_valid_when_valid(datalayer_with_valid_report):
    """Test condition node returns SUCCESS when report is VALID."""
    node = CheckRMStateValid("actor1", "report1", datalayer_with_valid_report)
    node.setup()
    assert node.update() == py_trees.common.Status.SUCCESS

def test_transition_rm_to_valid_updates_datalayer(datalayer_with_received_report):
    """Test action node persists state change to data layer."""
    dl = datalayer_with_received_report
    node = TransitionRMtoValid("actor1", "report1", "offer1", dl)
    node.setup()
    
    status = node.update()
    
    assert status == py_trees.common.Status.SUCCESS
    report = dl.read("report1")
    assert report.status == ReportStatus.VALID
```

**2. Integration Tests for Full Trees**:

```python
def test_validate_report_bt_accepts_valid_report(datalayer_with_received_report):
    """Test full validation BT successfully accepts report."""
    dl = datalayer_with_received_report
    policy = AlwaysAcceptPolicy()
    
    bt = ValidateReportBT("actor1", "report1", "offer1", dl, policy)
    bt.setup_with_descendants()
    
    final_status = bt.tick_once()
    
    assert final_status == py_trees.common.Status.SUCCESS
    assert dl.read("report1").status == ReportStatus.VALID
    assert dl.read("offer1").status == OfferStatus.ACCEPTED
```

**3. Handler Integration Tests**:

```python
def test_validate_report_handler_with_bt(client_with_report):
    """Test handler successfully invokes BT and persists changes."""
    # Setup: Create report and offer in datalayer
    # Action: POST activity to inbox
    # Assert: Report status updated, case created, outbox contains CreateCase
```

### Phase 1 Checklist

- [ ] Install py_trees dependency (`pip install py_trees`)
- [ ] Create `vultron/behaviors/` directory
- [ ] Implement condition nodes (CheckRMState*)
- [ ] Implement action nodes (TransitionRMto*, CreateCase, etc.)
- [ ] Implement policy nodes (EvaluateReportCredibility, EvaluateReportValidity)
- [ ] Implement composite tree (ValidateReportBT)
- [ ] Modify validate_report handler to invoke BT
- [ ] Write unit tests for all nodes
- [ ] Write integration test for full tree
- [ ] Write handler integration test
- [ ] Create receive_report_bt_demo.py script
- [ ] Add Docker Compose service for BT demo
- [ ] Run all three demo workflows (accept, invalidate, reject+close)
- [ ] Verify no regressions in existing test suite
- [ ] Measure performance (establish baseline)
- [ ] Document lessons learned

---

### Phase 3: Case and Embargo Workflows

**Goal**: Extend BT integration to case and embargo management (35+ handlers)

**Scope**: Multi-actor coordination, embargo timelines, case lifecycle

**Key Objectives**:

- Implement behavior trees for case creation and management
- Model VulnerabilityCase → CaseActor creation workflow
- Implement embargo proposal, acceptance, and timeline trees
- Support multi-actor coordination via DataLayer
- Create demo scripts for complex workflows

**Success Criteria**:

- Case and embargo workflows function via BTs
- Multi-actor coordination works correctly
- Demo scripts show end-to-end workflows
- Integration tests cover multi-party scenarios

**Deliverable**: Full case/embargo workflow support (35+ handlers)

**Challenges**:

- Human-in-loop decisions (use configurable policies + audit logging)
- Multi-actor state synchronization via DataLayer
- Complex state machine interactions (EM/CS)

---

### Phase 4: Hardening and Documentation

**Goal**: Refine BT integration for broader use with comprehensive documentation

**Scope**: Error handling, observability, performance, specifications

**Key Objectives**:

- Comprehensive error handling and recovery mechanisms
- Structured logging per `specs/structured-logging.md`
- Performance measurement and optimization
- Create `specs/bt-integration.md` with testable requirements
- Write ADR documenting BT integration architecture
- Update `AGENTS.md` and developer documentation
- Achieve 80%+ test coverage for BT integration code

**Success Criteria**:

- Error handling complete with proper logging
- Performance meets targets (P99 < 100ms typical workflows)
- Comprehensive documentation and specifications
- Test coverage ≥80% for BT code
- ADR peer-reviewed and accepted

**Deliverable**: Refined BT integration with full documentation
---

## Design Decisions

### 1. Use py_trees for Prototype Implementation

**Decision**: Prototype behavior trees use the `py_trees` library

**Rationale**:

- ✅ Mature, well-tested BT framework with active development
- ✅ Built-in visualization and debugging tools
- ✅ Extensive documentation and examples
- ✅ Follows established BT design patterns from robotics/AI community
- ✅ Allows focus on workflow logic rather than BT engine maintenance

**Implementation Boundary**:

- `vultron/bt/` retains custom BT engine for simulation
- `vultron/behaviors/` uses py_trees for prototype handlers
- Simulation and prototype coexist independently

---

### 2. Handler-Orchestrated vs. BT-First

**Decision**: Handlers orchestrate BT execution (handler-first approach)

**Rationale**:

- ✅ Preserves existing semantic extraction and dispatch infrastructure
- ✅ Allows gradual migration handler-by-handler
- ✅ Keeps ActivityStreams as API surface (BT as internal implementation detail)
- ✅ Easier to test handlers with/without BT
- ✅ Aligns with ADR-0007 Behavior Dispatcher architecture

**Alternative Rejected**: BTs directly consume ActivityStreams

- ❌ Would require rewriting semantic extraction
- ❌ Harder to migrate incrementally
- ❌ Tighter coupling between BT and ActivityStreams

---

### 3. DataLayer as State Store (No Separate Blackboard)

**Decision**: Behavior trees interact directly with DataLayer for state
management

**Rationale**:

- ✅ Single source of truth (eliminates sync issues)
- ✅ Simplifies architecture (one state system, not two)
- ✅ Transaction semantics already handled by DataLayer
- ✅ Reduces memory footprint (no duplicate state)

**Design Implication**:

- BT nodes will use DataLayer Protocol for reads/writes
- py_trees "blackboard" may be used for transient execution state only
- Persistent state (actors, cases, reports) stored in DataLayer

**Alternative Rejected**: Separate blackboard with periodic sync

- ❌ Risk of state inconsistencies
- ❌ Complex sync logic
- ❌ Harder to test and debug

---

### 4. Focused BTs per Workflow (Not Monolithic)

**Decision**: Create small, focused behavior trees triggered by specific message
semantics

**Rationale**:

- ✅ Event-driven execution model (one message → one tree)
- ✅ Easier to test in isolation
- ✅ Clear entry points from handlers
- ✅ Composable via subtrees when needed
- ✅ Better performance (smaller trees = faster execution)

**Examples**:

- ValidateReportBT (triggered by VALIDATE_REPORT handler)
- CreateCaseBT (subtree of ValidateReportBT)
- ProposeEmbargoBT (triggered by CREATE_EMBARGO_EVENT handler)

**Alternative Rejected**: Single monolithic CvdProtocolBT for prototype

- ❌ Doesn't match event-driven handler architecture
- ❌ Harder to test and debug
- ❌ Poor performance (ticking entire tree per event)
- ❌ Unclear entry points

---

### 5. Single-Shot Execution (Not Persistent Tick Loop)

**Decision**: BTs execute to completion per handler invocation

**Rationale**:

- ✅ Matches event-driven HTTP request/response model
- ✅ Simpler failure handling (no pause/resume state)
- ✅ Clear transaction boundaries (one execution = one commit)
- ✅ No need for tick state persistence

**Implementation**:

- Handler invokes BT
- BT executes until SUCCESS/FAILURE or max iterations
- Result returned to handler
- No state preserved between handler invocations

**Alternative Rejected**: Async tick-based execution with pause/resume

- ❌ Requires BT state persistence between ticks
- ❌ Complex failure recovery
- ❌ Doesn't match current handler architecture

---

### 6. Case Creation Includes CaseActor Generation

**Decision**: VulnerabilityCase creation triggers CaseActor (Service) creation
as part of same workflow

**Rationale**:

- ✅ Case needs owner for message processing
- ✅ Models case-as-agent pattern (case receives messages, updates state)
- ✅ Enables multi-case coordination within single organization
- ✅ Clear responsibility boundary (CaseActor owns case lifecycle)

**Workflow**:

1. VALIDATE_REPORT handler invoked
2. ValidateReportBT executes
3. Validation succeeds → CreateCaseBT subtree
4. CreateCaseBT creates VulnerabilityCase
5. CreateCaseBT creates CaseActor (Service) with case as context
6. CaseActor added to organization's actor registry
7. CreateCase activity added to outbox

**Alternative Rejected**: Case creation without CaseActor

- ❌ Unclear message routing for case-specific events
- ❌ Organization actor becomes overloaded
- ❌ Harder to model multi-case scenarios

---

### 7. Command-Line BT Invocation Support

**Decision**: Provide CLI interface for invoking behavior trees independently of
HTTP handlers

**Rationale**:

- ✅ Enables testing BTs in isolation
- ✅ Supports agentic AI integration (LLM-driven workflows)
- ✅ Facilitates debugging and development
- ✅ Allows manual workflow execution for maintenance tasks

**Use Cases**:

- Testing:
  `vultron run-behavior validate-report --actor=vendor --report=TEST-001`
- AI agents: Invoke workflows based on LLM decision-making
- Maintenance: Manually trigger case cleanup, embargo expiration checks
- Debugging: Step through workflow logic without HTTP overhead

---

## Migration Strategy

### Gradual Handler Migration

**Priority Order**:

1. **Report handlers** (already complete, good test coverage)
2. **Case handlers** (depends on report handlers)
3. **Embargo handlers** (parallel to case handlers)
4. **Participant/metadata handlers** (lower priority)

**Per-Handler Checklist**:

- [ ] Identify corresponding BT node(s)
- [ ] Implement prototype versions of fuzzer nodes (deterministic logic)
- [ ] Create test data for BT execution
- [ ] Modify handler to use BT bridge
- [ ] Update handler tests to verify BT execution
- [ ] Update integration tests if needed

---

## Testing Strategy

### 1. Unit Tests for BT Nodes

Test individual prototype nodes in isolation using standard pytest patterns with
DataLayer fixtures.

**Coverage Requirements**:

- Condition nodes: Test SUCCESS/FAILURE logic with various inputs
- Action nodes: Verify state changes via DataLayer reads
- Composite trees: Test node execution order and short-circuit behavior

---

### 2. Integration Tests for BT Execution

Test complete handler → BT → DataLayer flow:

**Test Patterns**:

- Verify handler invokes BT correctly
- Confirm state transitions persist to DataLayer
- Check activity generation (outbox items)
- Validate logging at appropriate levels

---

### 3. Simulation Tests (Existing)

Preserve existing simulation tests in `vultron/bt/` for protocol exploration and
probabilistic testing.

**No Changes Required**: Simulation tests continue to use custom BT engine with
fuzzer nodes.

---

## Open Questions and Key Considerations

### 1. State Synchronization in Multi-Actor Scenarios

**Question**: How should behavior trees coordinate state across multiple actors
in complex workflows?

**Context**: Case and embargo workflows involve multiple actors (finder, vendor,
coordinator) with independent state machines.

**Prototype Approach**:

- Each actor's BT execution loads only that actor's state from DataLayer
- Cross-actor coordination happens via message exchange (ActivityStreams
  activities in outboxes/inboxes)
- DataLayer serves as shared persistence layer but doesn't provide inter-actor
  locking by default
- Race conditions handled by:
    1. **Sequential message processing** (simple, sufficient for prototype)
    2. **Idempotent operations** (handlers check existing state before mutations
       per HP-07-*)
    3. **Optimistic concurrency** (defer to Phase 4 if sequential proves
       insufficient)

**Design Consideration**: Whether to implement optimistic locking or conflict
detection in Phase 3/4 based on observed issues in testing

---

### 2. Message Emission and Outbox Processing

**Question**: How should BT nodes emit ActivityStreams activities to actor
outboxes?

**Approach**:

- BT nodes generate activities and write to actor outbox via DataLayer
- Outbox processing (delivery to other actors) remains separate concern
- Trees focus on local state transitions and message generation, not delivery

**Design Consideration**: Whether outbox processing should be triggered
synchronously after BT execution or asynchronously

---

### 3. Human-in-the-Loop Decision Handling

**Question**: How to handle workflow steps requiring human judgment (report
validation, embargo acceptance)?

**Prototype Approach (Phases 1-3)**:

- Use **configurable default policies** (organizational rules encoded as policy
  objects)
- **Example**: ReportValidationPolicy with `is_credible()` and `is_valid()`
  methods
- **Default Implementation**: Always returns True (accept all reports) with
  audit logging
- **Extension Point**: Policy interface allows plugging in real logic without
  changing BT structure
- Log decisions at INFO level for audit and review
- Allow manual override via separate administrative actions (out of scope for
  initial prototype)

**Policy Node Pattern**:

```python
class EvaluateReportCredibility(py_trees.behaviour.Behaviour):
    def __init__(self, policy: ReportValidationPolicy):
        self.policy = policy

    def update(self):
        report = self.blackboard.get("report")
        if self.policy.is_credible(report):
            logger.info(f"Report {report.id} deemed credible")
            return py_trees.common.Status.SUCCESS
        else:
            logger.warning(f"Report {report.id} deemed not credible")
            return py_trees.common.Status.FAILURE
```

**Phase 4+ Consideration** (deferred):

- Async workflow support with pause/resume for human review
- Integration with external decision services or notification systems
- Workflow queues for pending human decisions

---

### 4. Performance Optimization Strategy

**Question**: What is acceptable performance overhead for BT execution?

**Baseline Targets** (for prototype evaluation, not hard requirements):

- P50 latency: <50ms (comparable to procedural handlers)
- P99 latency: <100ms (acceptable for typical workflows)
- P99.9 latency: <500ms (complex multi-actor scenarios)

**Measurement Approach**:

- Phase 1: Establish baseline metrics with POC
- Phase 2-3: Monitor and identify bottlenecks
- Phase 4: Optimize critical paths if needed (only if blocking real usage)

**Potential Optimizations** (defer to Phase 4 unless necessary):

- Cache BT structure (instantiate once, reuse with fresh blackboard)
- Batch DataLayer operations
- Profile and optimize hot paths

**Principle**: Measure before optimizing; prototype phase prioritizes
correctness and maintainability

---

### 5. Testing Strategy Across Simulation and Production

**Question**: How to maintain test coverage for both simulation and prototype
implementations?

**Approach**:

- Keep existing simulation tests for protocol exploration
- Add prototype BT tests for deterministic workflows
- Integration tests validate full handler → BT → DataLayer flow
- Unit tests for individual BT nodes (condition/action logic)

---

## Implementation Risks and Mitigation

### Risk 1: py_trees Integration Complexity

**Risk**: py_trees may not integrate cleanly with existing DataLayer and
ActivityStreams models

**Mitigation**:

- Phase 1 POC validates integration feasibility early
- Small scope (1 handler) limits risk exposure
- Fallback: If py_trees proves unsuitable, can use custom BT engine or
  procedural handlers

**Indicators of Success**:

- Clean DataLayer access from BT nodes
- Reasonable performance (<100ms P99)
- Tree visualization aids debugging

### Risk 2: Factory Method Reuse Infeasibility

**Risk**: Existing simulation BT structures may not map cleanly to py_trees due to API differences

**Context**: 

- Simulation uses custom BT engine with factory methods (`sequence_node()`, `fallback_node()`)
- py_trees uses class-based node hierarchy (`py_trees.composites.Sequence`, `py_trees.composites.Selector`)
- Factory method signatures and return types differ between engines
- Node initialization patterns incompatible (custom uses class types, py_trees uses instances)

**Mitigation**:

- Document intent in ADR-0004 but don't force reuse
- Phase 1 focuses on direct py_trees implementation (fastest path to working POC)
- Use simulation trees as *design reference* only:
  - Match composition hierarchy (sequence/fallback structure)
  - Preserve semantic intent (preconditions, actions, state transitions)
  - Translate fuzzer nodes to policy nodes with explicit logic
- Explore factory compatibility only if time permits after core POC working

**Fallback Strategy**: 

Implement new trees directly in py_trees, documenting correspondence to simulation trees in comments:

```python
class ValidateReportBT(py_trees.composites.Selector):
    """
    Behavior tree for report validation workflow.
    
    Based on simulation tree: vultron/bt/report_management/_behaviors/validate_report.py:RMValidateBt
    Adapted for prototype execution with py_trees.
    """
    def __init__(self, blackboard):
        # Mirrors simulation structure: fallback over (already valid, validation sequence, invalidation)
        children = [...]
```

**Decision Criteria**:

- ✅ **Accept**: Direct py_trees implementation sufficient for Phase 1 POC
- ⚠️ **Explore**: If Phase 2 shows extensive duplication, revisit factory abstraction
- ❌ **Reject**: Don't block Phase 1 on factory method compatibility

### Risk 3: Over-Engineering for Prototype

**Risk**: BT integration adds complexity that may not justify benefits for
prototype phase

**Mitigation**:

- Phase 1 POC demonstrates value before committing to full implementation
- Preserve procedural handlers as working examples (don't delete during
  migration)
- Gradual migration allows reverting individual handlers if BT approach proves
  problematic
- Document decision in ADR for future reference

**Decision Criteria**: If Phase 1 POC shows BT approach is:

- ✅ **Valuable**: Proceed with Phases 2-4
- ⚠️ **Uncertain**: Implement 2-3 more handlers in Phase 2, reassess
- ❌ **Problematic**: Document findings, revert to procedural handlers, close out
  ADR

### Risk 4: Performance Degradation

**Risk**: BT execution overhead degrades handler response times

**Mitigation**:

- Establish baseline metrics in Phase 1
- Set P99 < 100ms as go/no-go threshold for Phase 2
- Profile and optimize hot paths before proceeding to Phase 3

**Acceptable Outcomes**:

- If overhead < 50ms: Proceed as planned
- If overhead 50-100ms: Proceed with monitoring
- If overhead > 100ms: Optimize critical paths or reconsider approach

---

## Success Metrics

### Phase 1 (POC)

- [ ] One handler successfully uses BT
- [ ] Data layer persistence works via blackboard
- [ ] No test regressions

### Phase 2 (RM Messages)

- [ ] All 6 report handlers use BTs
- [ ] Demo script passes with BT execution
- [ ] State transitions match BT documentation

### Phase 3 (Case/Embargo)

- [ ] Complex workflows (multi-actor) work via BTs
- [ ] New demo scripts for case/embargo workflows
- [ ] Integration tests for all workflows

### Phase 4 (Hardening)

- [ ] Error handling complete
- [ ] Performance acceptable (<100ms P99)
- [ ] Documentation complete
- [ ] ADR written

---

## Specification Alignment

### Handler Protocol Compliance

BT integration MUST comply with all handler protocol requirements
(`specs/handler-protocol.md`):

- **HP-01-001/HP-01-002**: Handler signature (BT bridge called from handler, not
  replacing it)
- **HP-02-001/HP-02-002**: Semantic verification (`@verify_semantics` decorator
  required)
- **HP-03-001/HP-03-002**: Handler registration (BT-powered handlers still in
  `SEMANTIC_HANDLER_MAP`)
- **HP-04-001/HP-04-002**: Payload access (via `dispatchable.payload`, passed to
  BT
  bridge)
- **HP-05-001/HP-05-002**: Error handling (BT exceptions caught in bridge,
  logged
  appropriately)
- **HP-06-001/HP-06-002/HP-06-003**: Logging (BT execution logged per structured
  logging requirements)
- **HP-07-001/HP-07-002**: Idempotency (BT execution idempotent by design,
  blackboard
  fresh load)
- **HP-08-001/HP-08-002/HP-08-003**: Data model persistence (blackboard uses
  `object_to_record()`, correct signatures)

### Dispatch Routing Compliance

BT integration MUST comply with dispatcher requirements (
`specs/dispatch-routing.md`):

- **DR-01-001/DR-01-002/DR-01-003**: Dispatcher protocol (handlers invoked via
  dispatcher, not BT-first)
- **DR-02-001/DR-02-002**: Handler lookup (semantic type → handler lookup
  unchanged)
- **DR-03-001/DR-03-002**: Direct dispatch (BT executed synchronously within
  handler,
  exceptions logged)

### Inbox Endpoint Compliance

BT integration MUST comply with inbox endpoint requirements (
`specs/inbox-endpoint.md`):

- **IE-02-001**: HTTP 202 response (BT execution via BackgroundTasks, not
  blocking)
- **IE-05-001**: Activity rehydration (activities rehydrated before dispatch to
  BT)
- **IE-06-001**: Background processing (BT executes asynchronously after 202
  response)
- **IE-10-001**: Idempotency (BT fresh load per execution supports idempotent
  processing)

### New Specification Required

Phase 4 will create `specs/bt-integration.md` with testable requirements:

- **BT-01-***: Bridge layer requirements (execute_bt_for_handler interface,
  result format)
- **BT-02-***: Blackboard/DataLayer integration (load, commit, state management)
- **BT-03-***: Prototype node requirements (interface, logging, error handling)
- **BT-04-***: Message mapping requirements (ActivityStreams ↔ BT message types)
- **BT-05-***: Performance requirements (latency targets, timeout handling)

**Relationship to Existing Specs**:

BT integration does NOT replace existing specifications but rather adds a layer:

- **Handler Protocol** (`handler-protocol.md`): BT-powered handlers MUST still
  comply with HP-* requirements
- **Semantic Extraction** (`semantic-extraction.md`): BT invocation happens
  AFTER semantic extraction
- **Dispatch Routing** (`dispatch-routing.md`): BTs execute WITHIN handlers, not
  replacing dispatcher
- **Inbox Endpoint** (`inbox-endpoint.md`): BT execution via BackgroundTasks (
  async to HTTP)

BT integration is an **implementation detail** of handler business logic, not a
replacement for the handler architecture.

---

## References

### Documentation

- `docs/topics/behavior_logic/index.md` - BT overview and motivation
- `docs/topics/behavior_logic/msg_rm_bt.md` - RM message processing BT structure
- `docs/topics/behavior_logic/rm_bt.md` - Report Management BT state machine
- `docs/topics/behavior_logic/em_bt.md` - Embargo Management BT state machine
- `docs/topics/behavior_logic/cs_bt.md` - Case State BT state machine
- `plan/IMPLEMENTATION_PLAN.md` - Handler implementation status and progress
- `plan/IMPLEMENTATION_NOTES.md` - Lessons learned from handler implementation
- `AGENTS.md` - Agent instructions and architectural guidance

### Architecture Decision Records

- **ADR-0002**: Use Behavior Trees for modeling CVD processes (rationale for BT
  approach)
- **ADR-0007**: Use Behavior Dispatcher for semantic routing (establishes
  handler
  architecture)
- **ADR-0008** (future): BT integration with handlers (to be created in Phase 4)

### Code

#### Behavior Tree System

- `vultron/bt/base/` - BT engine base classes and utilities
- `vultron/bt/base/bt.py` - BehaviorTree class, tick execution
- `vultron/bt/base/blackboard.py` - Blackboard (dict subclass for shared state)
- `vultron/bt/base/bt_node.py` - BtNode base class, NodeStatus enum
- `vultron/bt/behaviors.py` - Top-level CVD protocol BT (CvdProtocolBt)
- `vultron/bt/states.py` - ActorState model (blackboard subclass for simulation)
- `vultron/bt/messaging/inbound/_behaviors/rm_messages.py` - RM message handling
  BT
- `vultron/bt/report_management/_behaviors/validate_report.py` - Report
  validation BT
- `vultron/bt/report_management/fuzzer/` - Stochastic simulation nodes
- `vultron/bt/embargo_management/behaviors.py` - Embargo management BT structure

#### Handler System

- `vultron/api/v2/backend/handlers.py` - Handler implementations (6/47 complete)
- `vultron/api/v2/backend/inbox_handler.py` - Inbox processing entry point
- `vultron/behavior_dispatcher.py` - Dispatcher interface and
  DirectActivityDispatcher
- `vultron/semantic_map.py` - Semantic extraction (pattern matching)
- `vultron/semantic_handler_map.py` - Handler registry (MessageSemantics →
  handler)
- `vultron/api/v2/datalayer/` - Data layer abstraction and TinyDB backend
- `vultron/api/v2/routers/actors.py` - FastAPI inbox endpoint

#### Integration Points (to be created)

- `vultron/api/v2/bt_bridge.py` - BT execution bridge (Phase 1)
- `vultron/api/v2/bt_blackboard.py` - DataLayer-backed blackboard (Phase 1)
- `vultron/api/v2/bt_messages.py` - ActivityStreams ↔ BT message mapping (Phase
    1)
- `vultron/behaviors/` - Prototype node implementations (Phase 1-3)

### Specifications

- `specs/meta-specifications.md` - How to read and write specifications
- `specs/handler-protocol.md` - Handler function requirements (HP-*)
- `specs/semantic-extraction.md` - Pattern matching and semantic types (SE-*)
- `specs/dispatch-routing.md` - Dispatcher requirements (DR-*)
- `specs/inbox-endpoint.md` - Inbox endpoint behavior (IE-*)
- `specs/http-protocol.md` - HTTP status codes, Content-Type, size limits
- `specs/structured-logging.md` - Log format, levels, correlation IDs
- `specs/message-validation.md` - ActivityStreams schema validation
- `specs/error-handling.md` - Exception hierarchy and error responses
- `specs/testability.md` - Test coverage and testing patterns
- `specs/bt-integration.md` - BT integration requirements (to be created in
  Phase 4)

---

## Next Steps

1. **Review and Refine**: Discuss this plan with maintainers, gather feedback
2. **Prototype Phase 1**: Build minimal POC with one handler
3. **Evaluate**: Measure performance, validate approach, adjust plan if needed
4. **Iterate**: Proceed with Phases 2-4 based on learnings

---

## Appendix A: Key Technology References

### py_trees Library

- **GitHub**: [py_trees](https://github.com/splintered-reality/py_trees)
- **Documentation**: [py_trees docs](https://py-trees.readthedocs.io/)
- **Rationale**: Mature BT framework with visualization, debugging, and
  extensive documentation

### Behavior Tree Theory

- Michele Colledanchise, Petter Ögren: *Behavior Trees in Robotics and
  AI* ([arXiv](https://arxiv.org/abs/1709.00084))
- Petter Ögren's [YouTube channel](https://www.youtube.com/@petterogren7535) for
  BT tutorials
-

Wikipedia: [Behavior Tree (AI, Robotics)](https://en.wikipedia.org/wiki/Behavior_tree_(artificial_intelligence,_robotics_and_control))

---

## Appendix B: Glossary

- **Behavior Tree (BT)**: Hierarchical decision/action structure for modeling
  processes as composable nodes
- **Node**: Single unit in a behavior tree (condition, action, composite,
  decorator)
- **py_trees**: Python library providing production-ready BT infrastructure with
  visualization
- **Tick**: Single execution step of a BT node (returns SUCCESS/FAILURE/RUNNING)
- **Fuzzer Node**: Stochastic simulation node for protocol exploration (custom
  BT engine)
- **Prototype Node/Tree**: Deterministic py_trees-based BT for handler workflow
  execution
- **Handler**: Python function processing specific ActivityStreams semantic
  types
- **Semantic Extraction**: Pattern matching to determine message meaning from
  activity structure
- **Data Layer**: Persistence abstraction (Protocol with TinyDB implementation)
- **Dispatcher**: Routes activities to appropriate handlers based on semantic
  type
- **Single-Shot Execution**: BT executes to completion in one handler
  invocation (vs. continuous tick loop)
- **CaseActor**: ActivityStreams Service object created during case creation to
  own case lifecycle
- **VulnerabilityCase**: Domain object representing a case; created during
  report validation

---

## Summary

This plan outlines an architecture for integrating behavior trees with the
handler system:

**Core Principles**:

1. **py_trees Foundation**: Prototype behavior trees use the mature py_trees
   library
2. **Event-Driven Execution**: Handlers trigger focused BTs per message
   semantic (not monolithic tick loop)
3. **DataLayer as State Store**: BTs interact with DataLayer for all
   persistence; no separate blackboard sync
4. **Simulation Preserved**: Existing `vultron/bt/` simulation code remains
   unchanged for protocol exploration
5. **Case Creation Workflow**: Validate→CreateCase→CreateCaseActor flow
   explicitly modeled
6. **Gradual Migration**: Handler-by-handler implementation starting with report
   workflows

**Key Design Decisions**:

- **Handler-First**: Handlers orchestrate BT execution (not BT-first)
- **Single-Shot**: BTs execute to completion per handler invocation
- **Focused Trees**: Small semantic-specific trees (not one monolithic CVD tree)
- **Command-Line Support**: BTs invokable independently for testing and AI
  agents
- **Configurable Policies**: Human-decision nodes use default policies with
  audit logging

**Implementation Roadmap**:

- **Phase 1**: Foundation - one BT-powered handler proof-of-concept with
  py_trees
- **Phase 2**: Report workflows - all 6 report handlers using BTs
- **Phase 3**: Case/Embargo workflows - remaining handlers for complex
  coordination
- **Phase 4**: Hardening - error handling, documentation, specifications, ADR

**Success Criteria**:

- BT execution integrated with handler system
- Process logic matches CVD protocol documentation
- No regressions in existing functionality
- Performance acceptable (P99 < 100ms)
- Comprehensive documentation and specifications

**Next Actions**:

1. **Maintainer Review**: Discuss refined plan and design decisions
2. **Phase 1 Prototyping**: Build proof-of-concept with py_trees integration
3. **Evaluation**: Measure performance, validate approach, adjust as needed
4. **Iteration**: Proceed with Phases 2-4 based on learnings

---

**Document Status**: REFINED (2026-02-18)  
**Refinement Summary**: 
- Clarified prototype context (replaced "production" terminology)
- Added comprehensive Phase 1 implementation guide with concrete py_trees examples
- Updated handler completion status (7/36, not 6/36)
- Expanded factory method reuse discussion with API compatibility analysis
- Added detailed simulation-to-prototype translation strategy
- Included node type examples (condition, action, policy) with code
- Added testing patterns and Phase 1 checklist
- Improved risk mitigation strategies with decision criteria
- Added concrete guidance on DataLayer integration options
**Purpose**: Design intent and architectural guidance (not detailed
implementation specification)  
**Next Step**: Review with maintainers, then create detailed Phase 1
implementation plan  
**Contact**: See `CONTRIBUTING.md` for discussion channels
