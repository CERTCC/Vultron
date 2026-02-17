# Behavior Tree Integration Plan

**Created**: 2026-02-17  
**Status**: Planning  
**Related**: ADR-0002 (Use Behavior Trees), ADR-0007 (Semantic Extraction)

---

## Executive Summary

This document outlines a plan to integrate the existing Vultron Behavior Tree (BT) logic from `vultron/bt/` with the newly implemented ActivityStreams-based inbox handler system in `vultron/api/v2/`. The goal is to leverage the process logic encoded in behavior trees while transitioning from stochastic simulation to deterministic real-world execution.

**Key Challenge**: The existing BT system is designed for **simulation** (using fuzzer nodes for stochastic testing), while the handler system is designed for **production** (processing real ActivityStreams messages with persistence). We need a bridge that preserves the BT modeling advantages while enabling concrete execution.

---

## Background

### Current Architecture: Two Parallel Systems

#### 1. Behavior Tree System (`vultron/bt/`)

**Purpose**: Model CVD process logic as composable hierarchical behaviors

**Key Components**:
- **BT Nodes**: Base classes in `vultron/bt/base/` (BtNode, composites, decorators)
- **Blackboard**: Shared state dictionary (`vultron/bt/base/blackboard.py`)
- **Process Models**: Report Management, Embargo Management, Case State transitions
- **Message Handling**: Inbound/outbound message behaviors (`vultron/bt/messaging/`)
- **Fuzzer Nodes**: Stochastic simulation nodes (e.g., `AlmostAlwaysSucceed`, `ProbablySucceed`)

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
- **Semantic Extraction**: Maps (Activity Type, Object Type) → MessageSemantics
- **Handler Functions**: Business logic for each semantic type
- **Data Layer**: TinyDB persistence with Protocol abstraction
- **Dispatcher**: Routes activities to appropriate handlers

**Example Handler**: `validate_report`
```python
@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    # 1. Rehydrate objects from data layer
    # 2. Validate business rules
    # 3. Update status (offer→ACCEPTED, report→VALID)
    # 4. Create VulnerabilityCase
    # 5. Add CreateCase activity to actor outbox
    # 6. Persist changes
    # 7. Log state transitions
```

**Strengths**:
- ✅ Real ActivityStreams message processing
- ✅ Persistent state in data layer
- ✅ Type-safe with Pydantic models
- ✅ Semantic extraction matching BT message types

**Limitations**:
- ❌ Business logic is procedural (not hierarchical)
- ❌ State transitions are implicit in code
- ❌ No composability or reusability
- ❌ Process flow not visible in structure

---

## Integration Goals

### Primary Objectives

1. **Process Logic Reuse**: Leverage existing BT models for state transitions and decision flow
2. **Deterministic Execution**: Replace fuzzer nodes with real implementations
3. **Data Layer Integration**: Connect BT blackboard to TinyDB persistence
4. **ActivityStreams Compatibility**: Bridge BT message types with AS2 vocabulary
5. **Maintainability**: Keep BT models as high-level process documentation

### Non-Goals

- ❌ **Not** replacing the handler system entirely with BTs
- ❌ **Not** porting all fuzzer nodes to production immediately
- ❌ **Not** changing the ActivityStreams-based API surface
- ❌ **Not** introducing tick-based simulation into production

---

## Proposed Architecture

### Hybrid Approach: Handlers Orchestrate BTs

**Key Insight**: Handlers act as **entry points** that set up BT context and trigger execution.

```
┌─────────────────────────────────────────────────────────┐
│ FastAPI Inbox Endpoint                                  │
│ POST /actors/{actor_id}/inbox                           │
└─────────────────────┬───────────────────────────────────┘
                      │ (ActivityStreams Activity)
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Semantic Extraction (semantic_map.py)                   │
│ Pattern Matching: (Activity Type, Object Type)          │
│                   → MessageSemantics.SUBMIT_REPORT      │
└─────────────────────┬───────────────────────────────────┘
                      │ (DispatchActivity)
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Behavior Dispatcher (behavior_dispatcher.py)            │
│ Route to handler based on MessageSemantics              │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Handler Function (handlers.py)                          │
│ @verify_semantics(MessageSemantics.SUBMIT_REPORT)      │
│ def submit_report(dispatchable):                        │
│     # NEW: Invoke BT execution                          │
│     result = execute_bt_for_handler(                    │
│         bt_node=ProcessRMMessagesBt,                    │
│         activity=dispatchable.payload,                  │
│         actor_id=dispatchable.actor_id,                 │
│     )                                                   │
│     return result                                       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ BT Bridge Layer (NEW: bt_bridge.py)                    │
│                                                         │
│ 1. Create BT-compatible blackboard from activity        │
│ 2. Inject data layer adapter into blackboard            │
│ 3. Replace fuzzer nodes with real implementations       │
│ 4. Execute BT and capture state changes                 │
│ 5. Translate BT results back to handler return values   │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │                           │
        ▼                           ▼
┌──────────────────┐      ┌──────────────────────┐
│ Behavior Tree    │      │ Data Layer           │
│ Execution        │◄────►│ (TinyDB)             │
│ (vultron/bt/)    │      │ Persist state changes│
└──────────────────┘      └──────────────────────┘
```

### Key Components to Build

#### 1. BT Bridge Module (`vultron/api/v2/bt_bridge.py`)

**Purpose**: Translate between handler context and BT execution context

```python
# Pseudocode
def execute_bt_for_handler(
    bt_node: BtNode,
    activity: Activity,
    actor_id: str,
    datalayer: DataLayer,
) -> BTExecutionResult:
    """
    Execute a behavior tree in the context of a handler.
    
    Steps:
    1. Create blackboard from activity + data layer state
    2. Inject real implementations for fuzzer nodes
    3. Set up BT with blackboard
    4. Execute BT (tick until complete or max iterations)
    5. Extract state changes from blackboard
    6. Persist changes to data layer
    7. Return result (success/failure + side effects)
    """
    pass
```

**Responsibilities**:
- Blackboard initialization from ActivityStreams activities
- Data layer adapter (blackboard ↔ TinyDB)
- Fuzzer node replacement with real implementations
- Result extraction and logging

#### 2. Production Node Implementations (`vultron/api/v2/bt_nodes/`)

**Purpose**: Replace fuzzer nodes with real logic for production use

**Example**: `EvaluateReportValidity` (currently `AlmostAlwaysSucceed` fuzzer)

```python
# Current (simulation):
EvaluateReportValidity = fuzzer(
    AlmostAlwaysSucceed,  # 90% success probability
    "EvaluateReportValidity",
    "..."
)

# Production (real implementation):
class EvaluateReportValidity(BtNode):
    """
    Evaluate report validity based on organizational criteria.
    
    Checks:
    - Report is credible (see EvaluateReportCredibility)
    - Report is in scope for organization
    - Report meets minimum quality standards
    - Report contains actionable information
    
    Returns:
    - SUCCESS if report is valid
    - FAILURE if report is invalid
    """
    def tick(self):
        report = self.bb.current_report
        
        # Check organizational scope rules
        if not self._is_in_scope(report):
            return NodeStatus.FAILURE
        
        # Check quality standards
        if not self._meets_quality_standards(report):
            return NodeStatus.FAILURE
        
        return NodeStatus.SUCCESS
    
    def _is_in_scope(self, report):
        # Real business logic here
        pass
```

**Categories of Nodes to Implement**:
- **Conditions**: Check state, validate data, verify preconditions
- **Actions**: Mutate state, persist data, emit messages
- **Composite Replacements**: Replace fuzzer-based sequences with deterministic logic

#### 3. Blackboard-DataLayer Adapter (`vultron/api/v2/bt_blackboard.py`)

**Purpose**: Sync BT blackboard state with persistent data layer

```python
class DataLayerBackedBlackboard(Blackboard):
    """
    Blackboard that persists state to data layer.
    
    - Reads initial state from data layer on setup
    - Tracks mutations during BT execution
    - Writes changes back to data layer on commit
    """
    
    def __init__(self, datalayer: DataLayer, actor_id: str):
        super().__init__()
        self._datalayer = datalayer
        self._actor_id = actor_id
        self._dirty = set()  # Track modified keys
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._dirty.add(key)
    
    def commit(self):
        """Persist dirty state to data layer"""
        for key in self._dirty:
            self._persist_key(key)
        self._dirty.clear()
    
    def _persist_key(self, key):
        # Map blackboard keys to data layer operations
        pass
```

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

**Tasks**:
- [ ] 1.1: Create `vultron/api/v2/bt_bridge.py` with basic `execute_bt_for_handler()`
- [ ] 1.2: Create `DataLayerBackedBlackboard` in `vultron/api/v2/bt_blackboard.py`
- [ ] 1.3: Implement production version of `_HandleRs` behavior tree
  - Replace `IsMsgTypeRS` fuzzer with real condition check
  - Replace `q_rm_to_R` fuzzer with real state transition + persistence
- [ ] 1.4: Modify `submit_report` handler to invoke BT via bridge
- [ ] 1.5: Add integration test: POST activity → verify BT execution → check data layer

**Success Criteria**:
- `submit_report` successfully triggers `_HandleRs` BT
- RM state transitions from S→R persist to data layer
- Test suite passes (no regressions)

**Deliverable**: Working proof-of-concept with one BT-powered handler

---

### Phase 2: Message Type Expansion

**Goal**: Integrate BT logic for all report management messages

**Tasks**:
- [ ] 2.1: Implement production nodes for RM messages:
  - `_HandleRs` (RS: Report Submitted) - done in Phase 1
  - `_HandleRv` (RV: Report Validated)
  - `_HandleRi` (RI: Report Invalidated)
  - `_HandleRc` (RC: Report Closed)
  - `_HandleRk` (RK: Report Acknowledged)
  - `_HandleRe` (RE: Report Error)
- [ ] 2.2: Update handlers to use BT bridge:
  - `validate_report` → `RMValidateBt`
  - `invalidate_report` → `_InvalidateReport` node
  - `close_report` → RM close behavior
- [ ] 2.3: Create comprehensive message type mapping (AS → BT)
- [ ] 2.4: Add tests for each RM message type with BT execution

**Success Criteria**:
- All 6 report handlers use BT logic
- Demo script (`scripts/receive_report_demo.py`) still passes
- State transitions match BT documentation

**Deliverable**: Complete RM message processing via BTs

---

### Phase 3: Case and Embargo Management

**Goal**: Extend BT integration to case/embargo workflows

**Tasks**:
- [ ] 3.1: Implement production nodes for case management
- [ ] 3.2: Implement production nodes for embargo management
- [ ] 3.3: Update case handlers to use BT bridge
- [ ] 3.4: Update embargo handlers to use BT bridge
- [ ] 3.5: Add demo scripts for case/embargo workflows

**Success Criteria**:
- Case creation, actor invitations, participant management work via BTs
- Embargo creation, timeline management work via BTs
- Complex workflows (multi-actor coordination) function correctly

**Deliverable**: Full case/embargo workflow support with BT logic

---

### Phase 4: Production Readiness

**Goal**: Harden BT integration for production use

**Tasks**:
- [ ] 4.1: Add error handling and recovery in BT bridge
- [ ] 4.2: Add structured logging for BT execution (start, end, state changes)
- [ ] 4.3: Add metrics/observability for BT performance
- [ ] 4.4: Document BT integration patterns for future handlers
- [ ] 4.5: Add ADR documenting BT integration decisions

**Success Criteria**:
- BT execution errors are caught and logged appropriately
- Performance is acceptable (no significant latency increase)
- Documentation is complete and clear

**Deliverable**: Production-ready BT integration system

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

## Open Questions

### 1. State Synchronization

**Question**: How do we keep BT blackboard state in sync with data layer during multi-step workflows?

**Example**: Actor processes multiple messages in sequence. After message 1, should we:
- (A) Commit blackboard changes to data layer, then reload for message 2?
- (B) Keep blackboard in memory across messages within same request?
- (C) Use data layer as source of truth, read fresh for each BT execution?

**Recommendation**: Start with (C) for simplicity, consider (A) for optimization later.

---

### 2. Message Queue Integration

**Question**: How do we integrate BT message emission with outbox processing?

**Current BT Model**: Nodes like `EmitRV` add messages to `bb.outbound_messages` queue

**Handler Model**: Handlers add activities to actor outbox via data layer

**Options**:
- (A) BT emits to blackboard queue, bridge translates to outbox activities
- (B) Replace BT emit nodes with direct outbox writes
- (C) Hybrid: BT emits intent, handler translates to ActivityStreams

**Recommendation**: Start with (A) to preserve BT abstraction.

---

### 3. Human-in-the-Loop Decisions

**Question**: How do we handle BT nodes that require human decisions (e.g., `EvaluateReportCredibility`)?

**Options**:
- (A) Block BT execution, return "pending" status, resume later
- (B) Use default/conservative decision, log for human review
- (C) Skip BT for these cases, handle in procedural code

**Recommendation**: Phase 1-3 use (B) with configurable policies. Phase 4+ explore async workflows.

---

### 4. Performance Impact

**Question**: What is the performance overhead of BT execution vs. direct handler logic?

**Concern**: BT adds indirection (node instantiation, tick loop, blackboard lookups)

**Mitigation**:
- Profile BT execution in Phase 1
- Set max tick limit (e.g., 100 ticks = timeout/error)
- Cache BT structure if possible (avoid re-instantiation)

**Acceptance Criteria**: <100ms P99 latency for typical workflows

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

## References

### Documentation
- `docs/topics/behavior_logic/index.md` - BT overview and motivation
- `docs/topics/behavior_logic/msg_rm_bt.md` - RM message processing BT
- `docs/topics/behavior_logic/rm_bt.md` - Report Management BT
- ADR-0002: Use Behavior Trees for modeling CVD processes
- ADR-0007: Semantic extraction and dispatch routing

### Code
- `vultron/bt/base/` - BT base classes and utilities
- `vultron/bt/messaging/inbound/_behaviors/rm_messages.py` - RM message handling BT
- `vultron/bt/report_management/_behaviors/validate_report.py` - Report validation BT
- `vultron/api/v2/backend/handlers.py` - Current handler implementations
- `vultron/behavior_dispatcher.py` - Activity dispatcher
- `vultron/demo/vultrabot.py` - Simulation example using BTs

### Specifications
- `specs/handler-protocol.md` - Handler function requirements
- `specs/semantic-extraction.md` - Pattern matching and semantic types
- `specs/dispatch-routing.md` - Dispatcher requirements

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

- **BT**: Behavior Tree - hierarchical decision/action structure
- **Node**: Single unit in a behavior tree (condition, action, composite)
- **Blackboard**: Shared state dictionary accessible to all BT nodes
- **Tick**: Single execution step of a BT node
- **Fuzzer Node**: Stochastic node used for simulation (returns random success/failure)
- **Production Node**: Deterministic node with real business logic
- **Handler**: Python function that processes a specific ActivityStreams semantic type
- **Semantic Extraction**: Pattern matching to determine message meaning from activity structure
- **Data Layer**: Persistence abstraction (Protocol with TinyDB implementation)
- **Dispatcher**: Routes activities to appropriate handlers based on semantic type
