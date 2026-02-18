# Behavior Tree Integration Plan

**Created**: 2026-02-17  
**Last Updated**: 2026-02-18  
**Status**: Planning  
**Related**: ADR-0002 (Use Behavior Trees), ADR-0007 (Behavior Dispatcher)

---

## Executive Summary

This document outlines a plan to integrate the existing Vultron Behavior
Tree (BT) logic from `vultron/bt/` with the ActivityStreams-based handler
system in `vultron/api/v2/`. The goal is to leverage the process logic encoded
in behavior trees while transitioning from stochastic simulation to
deterministic real-world execution.

**Key Challenge**: The existing BT system is designed for **simulation**
(using fuzzer nodes for stochastic testing and tick-based execution), while the
handler system is designed for **production** (processing real ActivityStreams
messages with persistence and event-driven execution). We need a bridge that
preserves the BT modeling advantages while enabling concrete execution within
the event-driven handler architecture.

---

## Background

### Current Architecture: Two Parallel Systems

#### 1. Behavior Tree System (`vultron/bt/`)

**Purpose**: Model CVD process logic as composable hierarchical behaviors

**Key Components**:

- **BT Nodes**: Base classes in `vultron/bt/base/` (BtNode, composites,
  decorators)
- **Blackboard**: Shared state dictionary (`vultron/bt/base/blackboard.py`)
- **Process Models**: Report Management, Embargo Management, Case State
  transitions
- **Message Handling**: Inbound/outbound message behaviors
  (`vultron/bt/messaging/`)
- **Fuzzer Nodes**: Stochastic simulation nodes (e.g., `AlmostAlwaysSucceed`,
  `ProbablySucceed`)

**Example BT**: `_HandleRs` in `vultron/bt/messaging/inbound/_behaviors/rm_messages.py`

```python
_HandleRs = sequence_node(
    "_HandleRs",
    "Handle an RS message (incoming report)",
    IsMsgTypeRS,              # Condition: Check message type
    _LeaveRmStart,            # Action: Transition RM state S→R
    _RecognizeVendorNotifiedIfNecessary,  # Action: Set CS→V if vendor
)
```

**Strengths**:

- ✅ Hierarchical, composable process modeling
- ✅ Clear preconditions and state transitions
- ✅ Matches documentation (docs/topics/behavior_logic/)
- ✅ Already implements CVD protocol state machines

**Limitations**:

- ❌ Fuzzer nodes simulate but don't implement real logic
- ❌ No integration with ActivityStreams vocabulary
- ❌ No data layer persistence
- ❌ Designed for tick-based simulation, not event-driven processing

#### 2. Handler System (`vultron/api/v2/backend/handlers.py`)

**Purpose**: Process real ActivityStreams activities with persistence

**Key Components**:

- **Semantic Extraction**: Maps (Activity Type, Object Type) →
  MessageSemantics (`vultron/semantic_map.py`)
- **Behavior Dispatcher**: Routes DispatchActivity to handlers via
  `SEMANTIC_HANDLER_MAP` (`vultron/behavior_dispatcher.py`)
- **Handler Functions**: Business logic for each semantic type with
  `@verify_semantics` decorator
- **Data Layer**: TinyDB persistence with Protocol abstraction
  (`vultron/api/v2/datalayer/`)
- **Inbox Processing**: FastAPI endpoint with BackgroundTasks
  (`vultron/api/v2/routers/actors.py`)

**Example Handler**: `validate_report`

```python
@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    # 1. Rehydrate objects from data layer
    # 2. Validate business rules (currently procedural logic)
    # 3. Update status (offer→ACCEPTED, report→VALID)
    # 4. Create VulnerabilityCase
    # 5. Add CreateCase activity to actor outbox
    # 6. Persist changes
    # 7. Log state transitions at INFO level
```

**Current Implementation Status** (as of 2026-02-13):

- ✅ 6/47 handlers have complete business logic (13%)
  - Report workflow: `create_report`, `submit_report`, `validate_report`,
    `invalidate_report`, `ack_report`, `close_report`
- ⚠️ 41/47 handlers are stubs (log at DEBUG, no side effects)
- ✅ All handlers follow protocol: decorator, signature, registration
- ✅ Infrastructure complete: semantic extraction, dispatcher, data layer, inbox
  endpoint

**Strengths**:

- ✅ Real ActivityStreams message processing
- ✅ Persistent state in data layer
- ✅ Type-safe with Pydantic models
- ✅ Semantic extraction matching BT message types
- ✅ Event-driven execution model (HTTP 202 + BackgroundTasks)

**Limitations**:

- ❌ Business logic is procedural (not hierarchical)
- ❌ State transitions are implicit in code
- ❌ No composability or reusability of business logic
- ❌ Process flow not visible in structure
- ❌ Most handlers lack implemented business logic

---

## Integration Goals

### Primary Objectives

1.  **Process Logic Reuse**: Leverage existing BT models for state transitions and
   decision flow
2.  **Deterministic Execution**: Replace fuzzer nodes with real implementations for
   production use
3.  **Data Layer Integration**: Connect BT blackboard to TinyDB persistence via
   `DataLayer` Protocol
4.  **ActivityStreams Compatibility**: Bridge BT message types with AS2 vocabulary and
   semantic extraction
5.  **Maintainability**: Keep BT models as high-level process documentation that matches
   specifications
6.  **Handler Completion**: Implement remaining 41 stub handlers using BT logic where
   appropriate

### Non-Goals

- ❌ **Not** replacing the semantic extraction or dispatcher infrastructure
- ❌ **Not** porting all fuzzer nodes to production immediately (gradual migration)
- ❌ **Not** changing the ActivityStreams-based API surface or inbox endpoint behavior
- ❌ **Not** introducing tick-based simulation into production (single-shot
  execution only)
- ❌ **Not** bypassing the handler protocol (handlers remain entry points with
  `@verify_semantics`)
- ❌ **Not** modifying existing BT simulation code (create parallel production
  implementations)

---

## Proposed Architecture

### Hybrid Approach: Handlers Orchestrate BTs

**Key Insight**: Handlers act as **entry points** that set up BT context and
trigger execution. BTs provide the process logic model, handlers provide the
ActivityStreams interface.

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
│ 4. Instantiate BT with production node implementations  │
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

1.  **Handler Protocol Preserved**: BT integration does NOT bypass `@verify_semantics`,
   `DispatchActivity`, or handler registration
2.  **Data Layer as Source of Truth**: BT blackboard reads/writes via `DataLayer`
   Protocol (not direct TinyDB access)
3.  **Single-Shot Execution**: BTs execute to completion (or max ticks) per handler
   invocation (no tick-based loop across HTTP requests)
4.  **Parallel Implementations**: Production nodes coexist with fuzzer nodes (simulation
   capability preserved)
5.  **Event-Driven Entry**: Handlers remain event-driven entry points (not tick-based
   polling)

### Key Components to Build

#### 1. BT Bridge Module (`vultron/api/v2/bt_bridge.py`)

**Purpose**: Translate between handler context and BT execution context

```python
def execute_bt_for_handler(
    bt_node: type[BtNode],
    activity: as_Activity,
    actor_id: str,
    datalayer: Optional[DataLayer] = None,
    max_ticks: int = 100,
) -> BTExecutionResult:
    """
    Execute a behavior tree in the context of a handler.
    
    Steps:
    1. Get data layer (default: get_datalayer())
    2. Load actor state from data layer
    3. Create DataLayerBackedBlackboard
    4. Populate blackboard: activity, current_message, state machine states
    5. Instantiate BT with blackboard
    6. Execute BT: tick loop until SUCCESS/FAILURE or max_ticks
    7. Commit blackboard changes to data layer on success
    8. Return BTExecutionResult (status, blackboard dict, errors)
    
    Args:
        bt_node: BT node class to execute (e.g., ProcessRMMessagesBt)
        activity: Rehydrated ActivityStreams activity
        actor_id: ID of actor processing activity
        datalayer: Optional DataLayer (injected for testing)
        max_ticks: Maximum tick iterations (timeout safety)
    
    Returns:
        BTExecutionResult with status, final blackboard state, and errors
    """
```

**Responsibilities**:

- Blackboard initialization from ActivityStreams activities
- Actor state loading via `DataLayer.read(actor_id)`
- BT instantiation and setup (via `BehaviorTree` class)
- Tick loop execution with timeout protection
- Blackboard commit/rollback based on BT result
- Structured logging (INFO for success, ERROR for failures)
- Result packaging for handler consumption

**Key Constraints**:

- MUST use `DataLayer` Protocol (not direct TinyDB access)
- MUST respect handler protocol (called from `@verify_semantics` handlers)
- MUST implement single-shot execution (no tick persistence across HTTP requests)
- MUST handle BT timeouts gracefully (max_ticks exceeded → FAILURE)

#### 2. Production Node Implementations (`vultron/bt/production/`)

**Purpose**: Provide production implementations of fuzzer nodes for real execution

**Directory Structure**:

```
vultron/bt/
  base/              # BT engine (unchanged)
  report_management/
    fuzzer/          # Stochastic simulation nodes (unchanged)
      validate_report.py
    production/      # NEW: Real implementations
      validate_report.py
  embargo_management/
    fuzzer/
    production/      # NEW
  case_state/
    fuzzer/
    production/      # NEW
```

**Example**: `EvaluateReportValidity` Production Implementation

```python
# vultron/bt/report_management/production/validate_report.py

from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.node_status import NodeStatus

class EvaluateReportValidity(ActionNode):
    """
    Evaluate report validity based on organizational criteria.
    
    Production implementation that replaces the fuzzer node.
    
    Blackboard Requirements:
    - bb["current_report"]: VulnerabilityReport object
    - bb["validation_criteria"]: Optional dict of org-specific rules
    
    Returns:
    - SUCCESS if report is valid according to organizational policy
    - FAILURE if report is invalid or out of scope
    """
    name = "EvaluateReportValidity"
    
    def _tick(self, depth=0):
        report = self.bb.get("current_report")
        if not report:
            logger.error("EvaluateReportValidity: no current_report in blackboard")
            return NodeStatus.FAILURE
        
        # Check organizational scope
        if not self._is_in_scope(report):
            logger.info(f"Report {report.as_id} is out of scope")
            return NodeStatus.FAILURE
        
        # Check quality standards
        if not self._meets_quality_standards(report):
            logger.info(f"Report {report.as_id} does not meet quality standards")
            return NodeStatus.FAILURE
        
        logger.info(f"Report {report.as_id} is valid")
        return NodeStatus.SUCCESS
    
    def _is_in_scope(self, report) -> bool:
        """
        Check if report is in scope for organization.
        
        Example criteria:
        - Product mentioned is supported by org
        - Vulnerability type is relevant to org's mission
        - Report is not duplicate of existing case
        """
        # Phase 1: Simple heuristics (e.g., check product field)
        # Phase 2+: Pluggable policy engine
        criteria = self.bb.get("validation_criteria", {})
        # ... implementation ...
        return True  # Placeholder
    
    def _meets_quality_standards(self, report) -> bool:
        """
        Check if report meets minimum quality standards.
        
        Example criteria:
        - Has description or reproduction steps
        - Includes affected versions
        - Credibility assessment passed
        """
        # Phase 1: Simple checks (non-empty fields)
        # Phase 2+: Scoring system
        return report.content and len(report.content) > 20  # Placeholder
```

**Implementation Strategy**:

1. **Phase 1**: Implement subset of critical nodes (validation, state transitions)
2. **Phase 2**: Expand to messaging and embargo nodes
3. **Phase 3**: Implement advanced nodes (human-in-loop placeholders)
4. **Future**: Pluggable policy engines for organization-specific logic

**Categories of Nodes to Implement**:

-  **Condition Nodes**: Check state, validate data, verify preconditions (return
  SUCCESS/FAILURE)
-  **Action Nodes**: Mutate blackboard state, trigger side effects (return
  SUCCESS/FAILURE)
-  **State Transition Nodes**: Move between state machine states (RM/EM/CS), persist to
  data layer
- **Message Emission Nodes**: Add activities to actor outbox via data layer

**Key Constraints**:

- MUST use `_tick()` method (BT base class convention)
- MUST access state via `self.bb` (blackboard)
- MUST use data layer for persistence (not direct database access)
- MUST log state changes at INFO level (per `specs/structured-logging.md`)
- SHOULD match simulation node interface (drop-in replacement)

#### 3. Blackboard-DataLayer Adapter (`vultron/api/v2/bt_blackboard.py`)

**Purpose**: Sync BT blackboard state with persistent data layer

```python
from vultron.bt.base.blackboard import Blackboard
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.api.v2.data.helpers import object_to_record

class DataLayerBackedBlackboard(Blackboard):
    """
    Blackboard that persists state to data layer.
    
    Design:
    - Extends base Blackboard (dict subclass)
    - Tracks modifications during BT execution
    - Commits changes on success (rollback on failure)
    - Maps blackboard keys to data layer operations
    
    Lifecycle:
    1. __init__: Load actor state from data layer
    2. BT execution: Nodes read/write via bb[key]
    3. commit(): Persist dirty keys to data layer
    """
    
    def __init__(self, datalayer: DataLayer, actor_id: str):
        super().__init__()
        self._datalayer = datalayer
        self._actor_id = actor_id
        self._dirty = set()  # Track modified keys
        
        # Load initial actor state
        self._load_actor_state()
    
    def _load_actor_state(self):
        """Load actor's state machines and metadata from data layer"""
        try:
            actor = self._datalayer.read(self._actor_id)
            # Map actor fields to blackboard keys
            self["q_rm"] = actor.q_rm  # RM state
            self["q_em"] = actor.q_em  # EM state
            self["q_cs"] = actor.q_cs  # CS state
            # ... other state as needed
        except KeyError:
            logger.warning(f"Actor {self._actor_id} not found, using defaults")
            self["q_rm"] = RM.START
            self["q_em"] = EM.NO_EMBARGO
            self["q_cs"] = CS.vfdpxa
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._dirty.add(key)
    
    def commit(self):
        """
        Persist dirty state to data layer.
        
        Maps blackboard keys to appropriate data layer operations:
        - State machine states → update actor record
        - Outbox messages → append to actor.outbox
        - Created objects → data layer create()
        """
        if not self._dirty:
            return
        
        logger.debug(
            f"Committing {len(self._dirty)} dirty keys for actor {self._actor_id}"
        )
        
        # Update actor state machine states
        if any(k in self._dirty for k in ["q_rm", "q_em", "q_cs"]):
            self._update_actor_state()
        
        # Handle outbox messages
        if "msgs_emitted_this_tick" in self._dirty:
            self._emit_messages()
        
        # Handle created objects (reports, cases, etc.)
        if "created_objects" in self._dirty:
            self._persist_created_objects()
        
        self._dirty.clear()
        logger.info(f"Blackboard committed for actor {self._actor_id}")
    
    def _update_actor_state(self):
        """Update actor's state machine states in data layer"""
        actor = self._datalayer.read(self._actor_id)
        actor.q_rm = self.get("q_rm", actor.q_rm)
        actor.q_em = self.get("q_em", actor.q_em)
        actor.q_cs = self.get("q_cs", actor.q_cs)
        self._datalayer.update(actor.as_id, object_to_record(actor))
    
    def _emit_messages(self):
        """Add emitted messages to actor outbox"""
        messages = self.get("msgs_emitted_this_tick", [])
        if not messages:
            return
        
        actor = self._datalayer.read(self._actor_id)
        for msg in messages:
            # Convert BT message to ActivityStreams activity
            activity = bt_message_to_activity(msg)
            actor.outbox.orderedItems.append(activity)
        
        self._datalayer.update(actor.as_id, object_to_record(actor))
    
    def _persist_created_objects(self):
        """Persist any objects created during BT execution"""
        objects = self.get("created_objects", [])
        for obj in objects:
            try:
                self._datalayer.create(obj)
            except ValueError as e:
                logger.warning(f"Object {obj.as_id} already exists: {e}")
```

**Key Responsibilities**:

- **State Loading**: Read actor state from data layer on initialization
- **Change Tracking**: Track all blackboard modifications via `_dirty` set
- **Transactional Commit**: Persist all changes atomically (or rollback on failure)
-  **Type Mapping**: Convert between BT types (RM/EM/CS enums) and data layer
  representations
- **Message Translation**: Convert BT messages to ActivityStreams activities

**Constraints**:

- MUST use `DataLayer` Protocol (not direct TinyDB access)
-  MUST use `object_to_record()` helper for Pydantic model persistence (per
  `specs/handler-protocol.md` HP-08-001)
- MUST call `DataLayer.update(id, record)` with both parameters (per HP-08-002)
- MUST NOT overwrite existing data during load (defensive validators per HP-08-003)

#### 4. Message Type Bridge (`vultron/api/v2/bt_messages.py`)

**Purpose**: Map ActivityStreams activities to BT message types

```python
def activity_to_bt_message(activity: Activity) -> BTMessage:
    """
    Convert ActivityStreams activity to BT message format.
    
    Maps MessageSemantics → BT message type (RS, RV, RI, etc.)
    """
    semantic = find_matching_semantics(activity)
    
    mapping = {
        MessageSemantics.SUBMIT_REPORT: BTMessageType.RS,
        MessageSemantics.VALIDATE_REPORT: BTMessageType.RV,
        MessageSemantics.INVALIDATE_REPORT: BTMessageType.RI,
        # ... etc
    }
    
    return BTMessage(
        type=mapping.get(semantic),
        payload=activity,
        sender=activity.actor,
    )
```

---

## Implementation Phases

### Phase 1: Foundation (Proof of Concept)

**Goal**: Demonstrate BT execution from a single handler

**Scope**: Report submission flow (SUBMIT_REPORT semantic → RM state S→R transition)

**Tasks**:

- [ ] 1.1: Create `vultron/api/v2/bt_bridge.py`
  - Implement `execute_bt_for_handler()` function
  - Implement `BTExecutionResult` class
  - Add structured logging (INFO for execution, ERROR for failures)
  - Handle BT timeouts (max_ticks exceeded → FAILURE)

- [ ] 1.2: Create `vultron/api/v2/bt_blackboard.py`
  - Implement `DataLayerBackedBlackboard` class
  - Implement `_load_actor_state()` method
  - Implement `commit()` with state machine persistence
  - Add dirty tracking for modified keys

- [ ] 1.3: Create `vultron/api/v2/bt_messages.py`
  - Implement `activity_to_bt_message()` function
  - Define `SEMANTICS_TO_BT_MESSAGE` mapping (RM messages only)
  - Stub `bt_message_to_activity()` for Phase 2

- [ ] 1.4: Create `vultron/bt/report_management/production/` directory structure
  - Implement production version of `IsMsgTypeRS` condition node
  - Implement production version of `q_rm_to_R` state transition node
  - Match simulation node interfaces (drop-in replacement)

- [ ] 1.5: Modify `submit_report` handler to invoke BT
  - Import `execute_bt_for_handler` from bt_bridge
  - Import `ProcessRMMessagesBt` or `_HandleRs` node
  - Replace procedural logic with BT execution
  - Handle `BTExecutionResult` (log success/failure)

- [ ] 1.6: Add unit tests for BT bridge components
  - Test `DataLayerBackedBlackboard` load/commit cycle
  - Test `activity_to_bt_message` mapping
  - Test `execute_bt_for_handler` with mock BT

- [ ] 1.7: Add integration test for full flow
  - POST Offer(VulnerabilityReport) to inbox
  - Verify BT execution logged
  - Verify RM state transition S→R in data layer
  - Verify existing submit_report tests still pass

**Success Criteria**:

- ✅ `submit_report` successfully triggers BT execution
- ✅ RM state transitions from START→RECEIVED persist to data layer
- ✅ Test suite passes (no regressions in existing handlers)
- ✅ Structured logging shows BT execution flow
- ✅ Performance acceptable (<100ms for POC flow)

**Deliverable**: Working proof-of-concept with one BT-powered handler

**Risk Mitigation**:

- Keep existing procedural handler logic in fallback branch
- Use feature flag or config to enable BT execution (gradual rollout)
- Add comprehensive error logging to diagnose BT failures

---

### Phase 2: Report Management Message Expansion

**Goal**: Integrate BT logic for all report management messages (6 handlers)

**Scope**: Complete RM message handling via behavior trees

**Tasks**:

- [ ] 2.1: Implement production nodes for RM message handlers:
  - `_HandleRs` (RS: Report Submitted) - ✅ done in Phase 1
  - `_HandleRv` (RV: Report Validated)
    - Production: `EvaluateReportCredibility`, `EvaluateReportValidity`
    - State transition: `q_rm_to_V` (RECEIVED/INVALID → VALID)
  - `_HandleRi` (RI: Report Invalidated)
    - State transition: `q_rm_to_I` (RECEIVED → INVALID)
  - `_HandleRc` (RC: Report Closed)
    - State transition: `q_rm_to_C` (any → CLOSED)
  - `_HandleRk` (RK: Report Acknowledged)
    - No state transition, just acknowledgment logging
  - `_HandleRe` (RE: Report Error) - if applicable

- [ ] 2.2: Update handlers to use BT bridge:
  - ✅ `submit_report` → `_HandleRs` (done in Phase 1)
  - `validate_report` → `RMValidateBt` (includes validation + case creation)
  - `invalidate_report` → `_InvalidateReport` node
  - `close_report` → `_CloseReport` node
  - `ack_report` → `_HandleRk` node
  - Keep create_report procedural (no BT needed for simple creation)

- [ ] 2.3: Expand message type mapping:
  - Add all RM message types to `SEMANTICS_TO_BT_MESSAGE`
  - Document mapping in `bt_messages.py`
  - Add validation tests for mapping completeness

- [ ] 2.4: Implement BT message emission:
  - Complete `bt_message_to_activity()` for RM messages
  - Integrate with `DataLayerBackedBlackboard._emit_messages()`
  - Test outbox population after BT execution

- [ ] 2.5: Add tests for each RM message type:
  - Unit tests for production nodes (validation, state transitions)
  - Integration tests for full handler → BT → data layer flow
  - Verify state transitions match BT documentation

- [ ] 2.6: Update demo scripts:
  - Verify `scripts/receive_report_demo.py` still works
  - Add BT execution logging to demo output
  - Document BT behavior in demo comments

**Success Criteria**:

-  ✅ All 6 report handlers use BT logic (submit, validate, invalidate, close, ack +
  create)
- ✅ Demo script (`scripts/receive_report_demo.py`) passes with BT execution
- ✅ State transitions match BT documentation (`docs/topics/behavior_logic/msg_rm_bt.md`)
- ✅ Outbox messages generated correctly from BT emission
- ✅ No regressions in existing tests

**Deliverable**: Complete RM message processing via BTs

**Dependencies**:

- Phase 1 completion (BT bridge infrastructure)
- Existing handler tests as regression suite
- BT documentation for state transition validation

---

### Phase 3: Case and Embargo Management Integration

**Goal**: Extend BT integration to case/embargo workflows (35 handlers)

**Scope**: Multi-actor coordination, embargo timelines, case lifecycle management

**Rationale**: Case and embargo handlers are currently stubs (41 of 47 handlers). BT integration provides a structured way to implement complex coordination logic.

**Tasks**:

- [ ] 3.1: Analyze case/embargo BT models:
  - Review `vultron/bt/case_state/behaviors.py`
  - Review `vultron/bt/embargo_management/behaviors.py`
  - Identify which BT nodes have production-ready equivalents
  - Document gaps where new BT structure is needed

- [ ] 3.2: Implement production nodes for case management:
  - Case creation and initialization
  - Actor invitation/acceptance/rejection
  - Case participant management (add/remove)
  - Case status updates
  - Case closure and reopening

- [ ] 3.3: Implement production nodes for embargo management:
  - Embargo proposal/acceptance/rejection
  - Embargo timeline management
  - Embargo exit conditions
  - Embargo participant coordination

- [ ] 3.4: Update case handlers to use BT bridge:
  - `create_case` → Case creation BT
  - `add_report_to_case` → Case-report association
  -  `invite_actor_to_case` / `accept_invite_actor_to_case` /
    `reject_invite_actor_to_case`
  - `update_case`, `close_case`, `reopen_case`
  - Participant management handlers (11 handlers total)

- [ ] 3.5: Update embargo handlers to use BT bridge:
  - `create_embargo_event` → Embargo proposal BT
  - `accept_embargo` / `reject_embargo`
  - `update_embargo_event`, `close_embargo_event`
  - Embargo participant handlers (12 handlers total)

- [ ] 3.6: Add demo scripts for complex workflows:
  - Multi-actor case creation and coordination
  - Embargo timeline management
  - Case lifecycle (create → work → close → reopen)
  - Participant invitation and acceptance flows

- [ ] 3.7: Add integration tests:
  - Multi-actor workflows (finder → vendor → coordinator)
  - Embargo acceptance/rejection scenarios
  - Case participant addition/removal
  - Edge cases (duplicate invitations, invalid state transitions)

**Success Criteria**:

- ✅ Case creation, actor invitations, participant management work via BTs
- ✅ Embargo creation, acceptance, timeline management work via BTs
- ✅ Complex workflows (multi-actor coordination) function correctly
- ✅ Demo scripts show end-to-end case/embargo workflows
- ✅ Integration tests cover multi-party scenarios

**Deliverable**: Full case/embargo workflow support with BT logic (35+ handlers implemented)

**Challenges**:

- **Human-in-Loop**: Some BT nodes require human decisions (e.g., accept/reject embargo)
  - Phase 3 approach: Use configurable default policies + logging for review
  - Future: Async workflows with pause/resume for human input
-  **Multi-Actor Coordination**: BT blackboard is per-actor; cross-actor state must sync
  via data layer
-  **Complex State Machines**: EM/CS interactions are more complex than RM; need careful
  testing

**Dependencies**:

- Phase 2 completion (RM message handling)
- Case/embargo BT documentation review
- Multi-actor test fixtures and data

---

### Phase 4: Production Hardening and Documentation

**Goal**: Harden BT integration for production use and create comprehensive documentation

**Scope**: Error handling, observability, performance, documentation, specification updates

**Tasks**:

- [ ] 4.1: Error handling and recovery:
  - Add exception handling in `execute_bt_for_handler()` with proper error types
  - Implement BT timeout detection (max_ticks exceeded)
  - Add retry logic for transient failures (optional)
  - Ensure blackboard rollback on BT failure (no partial state)
  - Map BT failures to HTTP error responses where appropriate

- [ ] 4.2: Structured logging and observability:
  - Add structured logging per `specs/structured-logging.md`:
    - INFO: BT execution start/end, state transitions
    - DEBUG: Node tick details, blackboard state snapshots
    - ERROR: BT failures, timeouts, exceptions
  - Include correlation IDs (activity_id, actor_id) in all logs
  - Add logging for blackboard commit/rollback events
  - Implement audit trail for state machine transitions

- [ ] 4.3: Performance optimization and monitoring:
  - Profile BT execution overhead (baseline vs. procedural handlers)
  - Set and enforce performance SLOs (<100ms P99 for typical workflows)
  - Add metrics collection:
    - BT execution time per handler
    - Tick count per execution
    - Blackboard commit time
    - Cache hit rates (if BT structure caching added)
  - Identify and optimize bottlenecks

- [ ] 4.4: Documentation:
  - Update `AGENTS.md` with BT integration patterns
  - Create `docs/topics/bt_integration.md` guide:
    - When to use BT vs. procedural handlers
    - How to implement production nodes
    - How to test BT-powered handlers
    - Blackboard key conventions
  - Update handler implementation examples in specs
  - Document migration checklist for converting handlers to BT

- [ ] 4.5: Specification updates:
  - Create `specs/bt-integration.md` with testable requirements:
    - BT-01-*: Bridge layer requirements
    - BT-02-*: Blackboard persistence requirements
    - BT-03-*: Production node requirements
    - BT-04-*: Message mapping requirements
  - Update `specs/handler-protocol.md` to include BT execution option
  - Cross-reference BT integration from relevant specs

- [ ] 4.6: Architecture Decision Record:
  - Create `docs/adr/0008-integrate-behavior-trees-with-handlers.md`
  - Document design decisions, alternatives considered, tradeoffs
  - Link to related ADRs (ADR-0002, ADR-0007)

- [ ] 4.7: Testing and validation:
  - Achieve 80%+ line coverage for BT bridge code
  - Add property-based tests for blackboard commit logic
  - Add chaos testing for BT timeouts and failures
  - Validate against all specifications in `specs/`

**Success Criteria**:

- ✅ BT execution errors are caught and logged with full context
- ✅ Performance acceptable (P99 < 100ms for typical workflows)
- ✅ Structured logging meets `specs/structured-logging.md` requirements
- ✅ Documentation complete (AGENTS.md, docs, specs, ADR)
- ✅ Test coverage ≥80% for BT integration code
- ✅ All Phase 1-3 handlers validated in production-like scenarios

**Deliverable**: Production-ready BT integration system with comprehensive documentation

**Validation Checklist**:

- [ ] All specs requirements satisfied (testability verification)
- [ ] ADR peer-reviewed and accepted
- [ ] Performance benchmarks meet SLOs
- [ ] Error handling tested with fault injection
- [ ] Documentation reviewed by maintainers
- [ ] Migration guide validated with real handler conversions

---

## Design Decisions

### 1. Handler-Orchestrated vs. BT-First

**Decision**: Handlers orchestrate BT execution (handler-first)

**Rationale**:

- ✅ Preserves existing semantic extraction and dispatch infrastructure
- ✅ Allows gradual migration (handler-by-handler)
- ✅ Keeps ActivityStreams as the API surface (no BT details leak out)
- ✅ Easier to test (can test handlers with/without BT)

**Alternative Considered**: BT-first (BTs directly consume ActivityStreams)

- ❌ Would require rewriting semantic extraction in BT terms
- ❌ Harder to migrate incrementally
- ❌ Tighter coupling between BT and ActivityStreams

---

### 2. Blackboard Persistence Strategy

**Decision**: Write-through with explicit commit

**Rationale**:

- ✅ BT execution is transactional (commit on success, rollback on failure)
- ✅ Allows inspection of changes before persistence
- ✅ Simplifies testing (can check blackboard state without DB)

**Alternative Considered**: Immediate write-through on every change

- ❌ No transaction semantics
- ❌ Partial failures leave inconsistent state
- ❌ Harder to test and debug

---

### 3. Fuzzer Node Replacement

**Decision**: Create parallel production nodes (don't modify existing fuzzers)

**Rationale**:

- ✅ Preserves simulation capability for testing
- ✅ Clear separation between simulation and production code
- ✅ Allows running same BT structure with different node implementations

**Implementation**:

```python
# Directory structure:
vultron/bt/report_management/
    fuzzer/
        validate_report.py  # Stochastic simulation nodes
    production/  # NEW
        validate_report.py  # Real implementations
```

**Alternative Considered**: Modify fuzzer nodes to detect production mode

- ❌ Mixes concerns (simulation + production in same class)
- ❌ Harder to test each mode independently
- ❌ Risk of production code accidentally using fuzzer logic

---

### 4. BT Execution Model

**Decision**: Single-shot execution (not tick-based loop)

**Rationale**:

- ✅ Handlers are event-driven (one activity → one execution)
- ✅ Simpler failure handling (no need to pause/resume)
- ✅ Matches HTTP request/response model (synchronous)

**Implementation**:

```python
def execute_bt_for_handler(...):
    # Execute BT to completion (or max iterations)
    max_ticks = 100
    for _ in range(max_ticks):
        result = bt_node.tick()
        if result in (NodeStatus.SUCCESS, NodeStatus.FAILURE):
            break
    return result
```

**Alternative Considered**: Async tick-based execution with pause/resume

- ❌ Requires state persistence between ticks
- ❌ More complex error handling
- ❌ Doesn't match current handler model

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
- [ ] Implement production versions of fuzzer nodes
- [ ] Create test data for BT execution
- [ ] Modify handler to use BT bridge
- [ ] Update handler tests to verify BT execution
- [ ] Update integration tests if needed

---

## Testing Strategy

### 1. Unit Tests for BT Nodes

Test individual production nodes in isolation:

```python
def test_evaluate_report_validity_in_scope():
    """Test EvaluateReportValidity returns SUCCESS for in-scope reports"""
    bb = DataLayerBackedBlackboard(datalayer, "test-actor")
    bb.current_report = create_test_report(in_scope=True)
    
    node = EvaluateReportValidity()
    node.bb = bb
    
    result = node.tick()
    
    assert result == NodeStatus.SUCCESS
```

### 2. Integration Tests for BT Execution

Test full BT execution via bridge:

```python
def test_submit_report_executes_bt(datalayer):
    """Test submit_report handler executes _HandleRs BT"""
    activity = as_Offer(
        actor="reporter",
        object=VulnerabilityReport(name="TEST-001", ...),
        target="vendor",
    )
    
    dispatchable = DispatchActivity(
        semantic_type=MessageSemantics.SUBMIT_REPORT,
        payload=activity,
        actor_id="vendor",
    )
    
    # Execute handler (should trigger BT)
    submit_report(dispatchable)
    
    # Verify state changes from BT
    actor = datalayer.read("vendor")
    assert actor.rm_state == RMState.RECEIVED
    
    # Verify BT execution was logged
    assert "Executing BT: _HandleRs" in caplog.text
```

### 3. Simulation Tests (Existing)

Keep existing simulation tests to verify process logic:

```python
def test_rm_message_handling_simulation():
    """Test RM message handling BT in simulation mode"""
    with CvdProtocolBt() as tree:
        # Use fuzzer nodes for stochastic testing
        for _ in range(100):
            tree.tick()
            # Verify probabilistic properties
```

---

## Open Questions and Design Decisions

### 1. State Synchronization Strategy

**Question**: How do we keep BT blackboard state in sync with data layer during multi-step workflows?

**Context**: Current architecture uses event-driven processing. Each activity → one handler invocation → one BT execution. Question is whether to persist BT state across invocations.

**Analysis**:

The existing inbox handler architecture uses **BackgroundTasks** for async processing
(per `specs/inbox-endpoint.md` IE-06-001). Each activity is processed independently:

```python
@router.post("/{actor_id}/inbox")
async def inbox(actor_id: str, activity: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(inbox_handler, actor_id, activity)
    return Response(status_code=202)  # HTTP 202 within 100ms
```

This means:
- Activities processed in parallel (no guaranteed ordering)
- Each handler invocation is stateless from request perspective
- Actor state must be loaded from data layer each time

**Options**:

-  (A) **Fresh load per execution** (RECOMMENDED): Each BT execution loads actor state
  from data layer, executes, commits changes
  - ✅ Stateless, idempotent (per HP-07-001)
  - ✅ Handles concurrent activity processing
  - ✅ Simplest to implement and test
  - ❌ Higher data layer read overhead
  
-  (B) **Cached blackboard with invalidation**: Keep blackboard in memory, invalidate on
  data layer changes
  - ✅ Lower read overhead
  - ❌ Complex cache invalidation logic
  - ❌ Doesn't match event-driven architecture
  - ❌ Harder to test and debug
  
- (C) **Persistent BT state**: Store blackboard in data layer between ticks
  - ❌ Requires tick persistence (conflicts with single-shot execution model)
  - ❌ Doesn't match HTTP request/response semantics
  - ❌ Not needed for current architecture

**Decision**: Use option (A) - fresh load per execution

**Rationale**: Matches event-driven architecture, preserves idempotency, simplifies implementation. Performance impact can be measured in Phase 1 and optimized if needed.

---

### 2. Message Emission and Outbox Integration

**Question**: How do we integrate BT message emission with ActivityStreams outbox processing?

**Context**: 

- BT model: Nodes like `EmitRV` add messages to `bb.msgs_emitted_this_tick`
- Handler model: Activities added to `actor.outbox.orderedItems` via data layer
- Outbox processing: Not yet implemented (future work per `IMPLEMENTATION_PLAN.md`)

**Options**:

- (A) **BT → blackboard → bridge → outbox** (RECOMMENDED): 
  - BT nodes emit to `bb.msgs_emitted_this_tick`
  - `DataLayerBackedBlackboard.commit()` translates to ActivityStreams
  - Append activities to actor outbox via data layer
  - ✅ Preserves BT abstraction
  - ✅ BT nodes don't need ActivityStreams knowledge
  - ✅ Translation logic centralized in bridge
  
- (B) **Direct outbox writes from BT nodes**:
  - Production nodes directly write to actor outbox
  - ❌ Tight coupling to ActivityStreams
  - ❌ Breaks BT simulation compatibility
  - ❌ Harder to test in isolation
  
- (C) **Hybrid: Intent + handler translation**:
  - BT emits high-level intent (e.g., "validate_report")
  - Handler translates to specific ActivityStreams activity
  - ✅ Flexible for different activity structures
  - ❌ Duplicates translation logic across handlers
  - ❌ Unclear separation of concerns

**Decision**: Use option (A) - BT emits to blackboard, bridge translates

**Implementation**:

```python
# In DataLayerBackedBlackboard.commit():
def _emit_messages(self):
    """Translate BT messages to ActivityStreams activities"""
    messages = self.get("msgs_emitted_this_tick", [])
    for bt_msg in messages:
        # Use bt_message_to_activity() from bt_messages.py
        activity = bt_message_to_activity(bt_msg)
        actor.outbox.orderedItems.append(activity)
    self._datalayer.update(actor.as_id, object_to_record(actor))
```

**Rationale**: Keeps BT logic decoupled from ActivityStreams, enables testing with different message formats, centralizes translation in one place.

---

### 3. Human-in-the-Loop Decision Handling

**Question**: How do we handle BT nodes that require human decisions (e.g., `EvaluateReportCredibility`)?

**Context**: Many fuzzer nodes represent decisions that might require human judgment in production (validation, embargo acceptance, etc.).

**Analysis**:

Current fuzzer nodes (e.g., `AlmostAlwaysSucceed`, `ProbablySucceed`) simulate
stochastic decisions. Production implementations need to either:
1. Automate the decision (heuristics, rules, ML)
2. Defer to human operator
3. Use configurable policy (org-specific rules)

**Options**:

- (A) **Async workflow with pause/resume**:
  - BT execution pauses at human decision node
  - Handler returns "pending" status, stores BT state
  - Human provides input via separate endpoint
  - BT resumes from paused state
  - ❌ Requires tick persistence (conflicts with single-shot model)
  - ❌ Complex state management
  - ❌ Doesn't match HTTP semantics
  
- (B) **Default policy + audit log** (RECOMMENDED for Phase 1-3):
  - Production node uses configurable default policy
  - Decision logged at INFO level for human review
  - Humans can override via separate action (e.g., invalidate report)
  - ✅ Simple to implement
  - ✅ Matches single-shot execution model
  - ✅ Enables learning from decisions (future ML)
  - ❌ May make incorrect decisions (requires monitoring)
  
- (C) **Skip BT for human-decision flows**:
  - Use procedural handlers for flows requiring human input
  - Use BT only for fully automated flows
  - ✅ Avoids BT complexity for unclear cases
  - ❌ Loses BT modeling benefits
  - ❌ Inconsistent handler architecture

**Decision**: Use option (B) for Phase 1-3 (default policy + audit log)

**Phase 1-3 Implementation**:

```python
class EvaluateReportCredibility(ActionNode):
    """
    Evaluate report credibility using configurable policy.
    
    Default policy: Check for minimum information (description, affected versions).
    Future: Pluggable policy engine, ML scoring, etc.
    """
    def _tick(self, depth=0):
        report = self.bb["current_report"]
        policy = self.bb.get("credibility_policy", "default")
        
        # Apply policy (heuristics for Phase 1)
        is_credible = self._apply_policy(policy, report)
        
        # Audit log for human review
        logger.info(
            f"Report {report.as_id} credibility assessment: {is_credible} "
            f"(policy: {policy}, needs_review: {not is_credible})"
        )
        
        return NodeStatus.SUCCESS if is_credible else NodeStatus.FAILURE
```

**Phase 4+ Enhancement**: Explore async workflows with external decision services (webhook, queue, etc.) for complex human-in-loop scenarios.

**Rationale**: Pragmatic approach that enables progress while acknowledging limitations. Audit logging enables learning and improvement. Future async support is additive (doesn't require redesign).

---

### 4. Performance Impact and Optimization

**Question**: What is the performance overhead of BT execution vs. procedural handler logic?

**Concern**: BT adds indirection (node instantiation, tick loop, blackboard lookups, commit overhead).

**Baseline Measurement Plan (Phase 1)**:

```python
# Measure in integration tests
import time

def test_handler_performance_baseline():
    """Measure procedural handler execution time"""
    activity = create_test_activity()
    
    start = time.perf_counter()
    submit_report_procedural(activity)  # Old implementation
    end = time.perf_counter()
    
    procedural_time = (end - start) * 1000  # ms
    assert procedural_time < 50  # Baseline SLO

def test_handler_performance_bt():
    """Measure BT-powered handler execution time"""
    activity = create_test_activity()
    
    start = time.perf_counter()
    submit_report_bt(activity)  # New BT implementation
    end = time.perf_counter()
    
    bt_time = (end - start) * 1000  # ms
    overhead = bt_time - procedural_time
    
    assert bt_time < 100  # Phase 1 SLO
    assert overhead < 50  # Maximum acceptable overhead
```

**Expected Overhead Sources**:

1. **BT node instantiation**: ~1-5ms (can be cached)
2. **Blackboard lookups**: ~0.1ms per access (negligible)
3. **Tick loop iterations**: ~0.5ms per tick (depends on tree depth)
4. **Data layer read/commit**: ~5-10ms (dominant cost, same as procedural)

**Optimization Strategies**:

- **Phase 1**: Accept baseline overhead, measure and document
- **Phase 2**: Cache BT structure (instantiate once, reuse across invocations)
- **Phase 3**: Optimize data layer reads (batch loading, caching)
- **Phase 4**: Profile hot paths, optimize critical nodes

**Acceptance Criteria**:

- P50 latency: <50ms (same as procedural)
- P99 latency: <100ms (acceptable overhead for typical workflows)
- P99.9 latency: <500ms (complex multi-actor workflows)

**Monitoring**:

```python
# Add to execute_bt_for_handler()
metrics.histogram("bt_execution_time_ms", duration_ms, tags={
    "handler": handler_name,
    "semantic": semantic_type,
    "result": result.status,
})
metrics.counter("bt_tick_count", tick_count, tags={"handler": handler_name})
```

**Rationale**: Measure first, optimize later. Prioritize correctness and maintainability in Phase 1, address performance if it becomes a problem. BT modeling benefits (composability, testability, documentation) justify modest overhead.

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

### Phase 4 (Production)

- [ ] Error handling complete
- [ ] Performance acceptable (<100ms P99)
- [ ] Documentation complete
- [ ] ADR written

---

## Specification Alignment

### Handler Protocol Compliance

BT integration MUST comply with all handler protocol requirements
(`specs/handler-protocol.md`):

-  **HP-01-001/HP-01-002**: Handler signature (BT bridge called from handler, not
  replacing it)
-  **HP-02-001/HP-02-002**: Semantic verification (`@verify_semantics` decorator
  required)
-  **HP-03-001/HP-03-002**: Handler registration (BT-powered handlers still in
  `SEMANTIC_HANDLER_MAP`)
-  **HP-04-001/HP-04-002**: Payload access (via `dispatchable.payload`, passed to BT
  bridge)
-  **HP-05-001/HP-05-002**: Error handling (BT exceptions caught in bridge, logged
  appropriately)
-  **HP-06-001/HP-06-002/HP-06-003**: Logging (BT execution logged per structured
  logging requirements)
-  **HP-07-001/HP-07-002**: Idempotency (BT execution idempotent by design, blackboard
  fresh load)
-  **HP-08-001/HP-08-002/HP-08-003**: Data model persistence (blackboard uses
  `object_to_record()`, correct signatures)

### Dispatch Routing Compliance

BT integration MUST comply with dispatcher requirements (`specs/dispatch-routing.md`):

-  **DR-01-001/DR-01-002/DR-01-003**: Dispatcher protocol (handlers invoked via
  dispatcher, not BT-first)
- **DR-02-001/DR-02-002**: Handler lookup (semantic type → handler lookup unchanged)
-  **DR-03-001/DR-03-002**: Direct dispatch (BT executed synchronously within handler,
  exceptions logged)

### Inbox Endpoint Compliance

BT integration MUST comply with inbox endpoint requirements (`specs/inbox-endpoint.md`):

- **IE-02-001**: HTTP 202 response (BT execution via BackgroundTasks, not blocking)
- **IE-05-001**: Activity rehydration (activities rehydrated before dispatch to BT)
- **IE-06-001**: Background processing (BT executes asynchronously after 202 response)
-  **IE-10-001**: Idempotency (BT fresh load per execution supports idempotent
  processing)

### New Specification Required

Phase 4 will create `specs/bt-integration.md` with testable requirements:

-  **BT-01-***: Bridge layer requirements (execute_bt_for_handler interface, result
  format)
- **BT-02-***: Blackboard persistence (load, commit, rollback, dirty tracking)
- **BT-03-***: Production node requirements (interface, logging, error handling)
- **BT-04-***: Message mapping requirements (ActivityStreams ↔ BT message types)
- **BT-05-***: Performance requirements (latency SLOs, timeout handling)

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

-  **ADR-0002**: Use Behavior Trees for modeling CVD processes (rationale for BT
  approach)
-  **ADR-0007**: Use Behavior Dispatcher for semantic routing (establishes handler
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
- `vultron/bt/messaging/inbound/_behaviors/rm_messages.py` - RM message handling BT
- `vultron/bt/report_management/_behaviors/validate_report.py` - Report validation BT
- `vultron/bt/report_management/fuzzer/` - Stochastic simulation nodes
- `vultron/bt/embargo_management/behaviors.py` - Embargo management BT structure

#### Handler System
- `vultron/api/v2/backend/handlers.py` - Handler implementations (6/47 complete)
- `vultron/api/v2/backend/inbox_handler.py` - Inbox processing entry point
- `vultron/behavior_dispatcher.py` - Dispatcher interface and DirectActivityDispatcher
- `vultron/semantic_map.py` - Semantic extraction (pattern matching)
- `vultron/semantic_handler_map.py` - Handler registry (MessageSemantics → handler)
- `vultron/api/v2/datalayer/` - Data layer abstraction and TinyDB backend
- `vultron/api/v2/routers/actors.py` - FastAPI inbox endpoint

#### Integration Points (to be created)
- `vultron/api/v2/bt_bridge.py` - BT execution bridge (Phase 1)
- `vultron/api/v2/bt_blackboard.py` - DataLayer-backed blackboard (Phase 1)
- `vultron/api/v2/bt_messages.py` - ActivityStreams ↔ BT message mapping (Phase 1)
- `vultron/bt/production/` - Production node implementations (Phase 1-3)

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
- `specs/bt-integration.md` - BT integration requirements (to be created in Phase 4)

---

## Next Steps

1. **Review and Refine**: Discuss this plan with maintainers, gather feedback
2. **Prototype Phase 1**: Build minimal POC with one handler
3. **Evaluate**: Measure performance, validate approach, adjust plan if needed
4. **Iterate**: Proceed with Phases 2-4 based on learnings

---

## Appendix A: Node Type Mapping

| BT Node Type | Simulation | Production | Notes |
|-------------|-----------|-----------|-------|
| IsMsgTypeRS | Fuzzer | Check `activity.type` and `object.type` | Simple condition |
| q_rm_to_R | Fuzzer | Read RM state, transition S→R, persist | State transition |
| EvaluateReportValidity | AlmostAlwaysSucceed (90%) | Real validation logic | Complex decision |
| EmitRV | Fuzzer | Add activity to outbox | Message emission |
| GatherValidationInfo | Fuzzer | Query external sources or wait | Async operation |

---

## Appendix B: Example Full Integration

**File**: `vultron/api/v2/bt_bridge.py` (skeleton)

```python
"""
Bridge layer between ActivityStreams handlers and Behavior Tree execution.
"""

import logging
from typing import Any, Optional

from vultron.api.v2.bt_blackboard import DataLayerBackedBlackboard
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.as_vocab.activities import Activity
from vultron.bt.base.bt import BehaviorTree
from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)


class BTExecutionResult:
    """Result of BT execution."""
    
    def __init__(
        self,
        status: NodeStatus,
        blackboard: dict,
        errors: Optional[list[str]] = None,
    ):
        self.status = status
        self.blackboard = blackboard
        self.errors = errors or []
    
    @property
    def succeeded(self) -> bool:
        return self.status == NodeStatus.SUCCESS
    
    @property
    def failed(self) -> bool:
        return self.status == NodeStatus.FAILURE


def execute_bt_for_handler(
    bt_node: type[BtNode],
    activity: Activity,
    actor_id: str,
    datalayer: Optional[DataLayer] = None,
    max_ticks: int = 100,
) -> BTExecutionResult:
    """
    Execute a behavior tree in handler context.
    
    Args:
        bt_node: BT node class to execute (e.g., ProcessRMMessagesBt)
        activity: ActivityStreams activity that triggered handler
        actor_id: ID of actor processing the activity
        datalayer: Data layer for persistence (default: get_datalayer())
        max_ticks: Maximum BT ticks before timeout
    
    Returns:
        BTExecutionResult with status and side effects
    """
    if datalayer is None:
        from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
        datalayer = get_datalayer()
    
    # 1. Create blackboard with data layer integration
    bb = DataLayerBackedBlackboard(datalayer, actor_id)
    
    # 2. Populate blackboard from activity
    bb["current_activity"] = activity
    bb["current_message"] = activity_to_bt_message(activity)
    
    # 3. Load actor state from data layer
    actor = datalayer.read(actor_id)
    bb["rm_state"] = actor.rm_state  # Assuming actor has these fields
    bb["cs_state"] = actor.cs_state
    bb["em_state"] = actor.em_state
    
    # 4. Instantiate and setup BT
    logger.info(f"Executing BT: {bt_node.__name__} for activity {activity.as_id}")
    tree = BehaviorTree(bt_node)
    tree.bb = bb
    tree.setup()
    
    # 5. Execute BT (tick loop)
    result_status = NodeStatus.RUNNING
    for tick_count in range(max_ticks):
        result_status = tree.tick()
        
        if result_status in (NodeStatus.SUCCESS, NodeStatus.FAILURE):
            break
        
        if result_status == NodeStatus.RUNNING and tick_count == max_ticks - 1:
            logger.error(f"BT execution timeout after {max_ticks} ticks")
            result_status = NodeStatus.FAILURE
    
    # 6. Persist changes (commit blackboard to data layer)
    if result_status == NodeStatus.SUCCESS:
        bb.commit()
        logger.info(f"BT execution succeeded, changes committed")
    else:
        logger.warning(f"BT execution failed, changes NOT committed")
    
    # 7. Return result
    return BTExecutionResult(
        status=result_status,
        blackboard=dict(bb),
        errors=bb.get("errors", []),
    )


def activity_to_bt_message(activity: Activity) -> dict[str, Any]:
    """
    Convert ActivityStreams activity to BT message format.
    
    Maps semantic types to BT message type codes (RS, RV, etc.)
    """
    from vultron.semantic_map import find_matching_semantics
    from vultron.enums import MessageSemantics
    
    semantic = find_matching_semantics(activity)
    
    # Map MessageSemantics to BT message types
    semantic_to_bt = {
        MessageSemantics.SUBMIT_REPORT: "RS",
        MessageSemantics.VALIDATE_REPORT: "RV",
        MessageSemantics.INVALIDATE_REPORT: "RI",
        MessageSemantics.CLOSE_REPORT: "RC",
        MessageSemantics.ACK_REPORT: "RK",
        # ... more mappings
    }
    
    bt_msg_type = semantic_to_bt.get(semantic, "UNKNOWN")
    
    return {
        "type": bt_msg_type,
        "payload": activity,
        "sender": activity.actor,
    }
```

---

**File**: `vultron/api/v2/backend/handlers.py` (modified `submit_report`)

```python
@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchActivity) -> None:
    """
    Process a SubmitReport activity (Offer(VulnerabilityReport)).
    
    NEW: Uses behavior tree execution via bt_bridge.
    """
    from vultron.api.v2.bt_bridge import execute_bt_for_handler
    from vultron.bt.messaging.inbound._behaviors.rm_messages import ProcessRMMessagesBt
    
    activity = dispatchable.payload
    actor_id = dispatchable.actor_id or activity.target
    
    logger.info(
        "Actor '%s' receives report submission from '%s'",
        actor_id,
        activity.actor,
    )
    
    # Execute behavior tree
    result = execute_bt_for_handler(
        bt_node=ProcessRMMessagesBt,
        activity=activity,
        actor_id=actor_id,
    )
    
    if result.succeeded:
        logger.info("Report submission processed successfully via BT")
    else:
        logger.error("Report submission processing failed: %s", result.errors)
        # Optionally raise exception for error handling
```

---

## Appendix C: Glossary

- **BT**: Behavior Tree - hierarchical decision/action structure for modeling processes
- **Node**: Single unit in a behavior tree (condition, action, composite)
- **Blackboard**: Shared state dictionary accessible to all BT nodes (dict subclass)
- **Tick**: Single execution step of a BT node (returns SUCCESS/FAILURE/RUNNING)
- **Fuzzer Node**: Stochastic node used for simulation (returns random success/failure)
-  **Production Node**: Deterministic node with real business logic (replaces fuzzer in
  production)
- **Handler**: Python function that processes a specific ActivityStreams semantic type
-  **Semantic Extraction**: Pattern matching to determine message meaning from activity
  structure
- **Data Layer**: Persistence abstraction (Protocol with TinyDB implementation)
- **Dispatcher**: Routes activities to appropriate handlers based on semantic type
- **Bridge Layer**: Translation layer between handlers and BT execution (bt_bridge.py)
-  **Single-Shot Execution**: BT executes to completion in one handler invocation (vs.
  tick-based loop)
- **Commit**: Persist blackboard changes to data layer (transaction-like semantics)
- **Rehydration**: Expanding URI references to full objects before processing

---

## Summary

This plan outlines a **hybrid architecture** where handlers orchestrate BT execution:

- **Handlers remain entry points** with `@verify_semantics` and dispatcher routing
- **BTs provide process logic** with hierarchical, composable structure
- **Bridge layer translates** between ActivityStreams context and BT execution
- **Data layer provides persistence** via blackboard adapter with commit/rollback

### Key Design Principles

1. **Preserve Handler Protocol**: BT integration does NOT bypass existing infrastructure
2.  **Single-Shot Execution**: BTs execute to completion per handler invocation
   (event-driven)
3.  **Parallel Implementations**: Production nodes coexist with fuzzer nodes (simulation
   preserved)
4. **Data Layer as Source of Truth**: Blackboard loads fresh state, commits on success
5. **Gradual Migration**: Implement handler-by-handler, starting with RM messages

### Implementation Roadmap

- **Phase 1** (POC): One BT-powered handler (submit_report), foundation infrastructure
- **Phase 2** (RM): All 6 report handlers use BT logic, message emission working
-  **Phase 3** (Case/Embargo): 35+ handlers for complex workflows, multi-actor
  coordination
-  **Phase 4** (Production): Error handling, observability, documentation, ADR,
  specifications

### Success Criteria

- ✅ BT execution from handlers with state persistence
- ✅ Process logic matches BT documentation
- ✅ No regressions in existing handlers
- ✅ Performance acceptable (P99 < 100ms)
- ✅ Comprehensive documentation and specifications

### Next Actions

1. **Review and Feedback**: Discuss this refined plan with maintainers
2. **Prototype Phase 1**: Build minimal POC with submit_report handler
3. **Evaluate and Iterate**: Measure performance, validate approach, refine as needed
4. **Execute Phases 2-4**: Proceed based on learnings from Phase 1

---

**Document Status**: REFINED (2026-02-18)  
**Ready for**: Maintainer review and Phase 1 prototyping  
**Contact**: See `CONTRIBUTING.md` for discussion channels
