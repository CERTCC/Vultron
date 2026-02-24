# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-24 (BT-7 complete: suggest_actor + ownership transfer handlers + demo scripts)

## Overview

This implementation plan tracks the development of the Vultron API v2 inbox handler system against the detailed specifications in `specs/*`. **Per PRIORITIES.md, the top priority is Behavior Tree (BT) integration** as outlined in `specs/behavior-tree-integration.md`. This supersedes previous demo completion priorities.

### Current Status Summary

**Phase 0 & 0A: COMPLETE** ✅

- [x] All 6 report handlers implemented with full business logic
- [x] Demo script refactored into three separate workflow demonstrations
- [x] All demo tests passing (1/1 test, 454 total tests in suite, 2 xfailed)
- [x] Rehydration system handles nested objects and full URI lookups
- [x] Status tracking working (OfferStatus, ReportStatus)
- [x] Outbox processing working (CreateCase activities added to actor outbox)
- [x] Actor ID resolution working (short IDs like "vendorco" resolve to full URIs)
- [x] All handler tests passing (9/9 handler-specific tests)

**BT Integration Status (BT-1 ✅, BT-2.0 ✅, BT-2.1 ✅, BT-3 ✅, BT-4.1 ✅, BT-4.2 ✅, BT-4.3 ✅, BT-5 ✅)**:

- ✅ py_trees library added to dependencies (v2.2.0+)
- ✅ BT bridge layer (`vultron/behaviors/bridge.py`)
- ✅ DataLayer-aware helper nodes (`vultron/behaviors/helpers.py`)
- ✅ Report BT nodes + trees (`vultron/behaviors/report/`)
- ✅ Default validation policy (`vultron/behaviors/report/policy.py`)
- ✅ `validate_report` handler BT-powered; ADR-0008 documenting py_trees choice
- ✅ Phase BT-2.0 COMPLETE: CM-04/ID-04-004 compliance audit for engage/defer
- ✅ Phase BT-2.1 COMPLETE: `engage_case` + `defer_case` BT trees + handlers
- ✅ Phase BT-3 COMPLETE: `create_case` BT + `add_report_to_case` + `close_case`
  handlers + `initialize_case_demo.py` script
- ✅ Phase BT-4.1 COMPLETE: `invite_actor_to_case`, `accept_invite_actor_to_case`,
  `reject_invite_actor_to_case`, `remove_case_participant_from_case` handlers
- ✅ Phase BT-4.2 COMPLETE: `create_case_participant` + `add_case_participant_to_case`
  handlers (procedural, part of BT-3.5/demo setup)
- ✅ Phase BT-4.3 COMPLETE: `invite_actor_demo.py` (accept + reject paths)
- ✅ Phase BT-5 COMPLETE: All 7 embargo handlers + `establish_embargo_demo.py`
- ✅ All xfailed tests resolved; 507 passing total

**Next Priority**: Per PRIORITIES.md, all BT handler phases (BT-1 through BT-7)
are complete. Next focus is **Phase BT-2.2/2.3** (optional `close_report` +
`invalidate_report` BT refactors) or production readiness work.

**Completed Infrastructure:**

- [x] Core dispatcher architecture (`behavior_dispatcher.py`) with `DirectActivityDispatcher`
- [x] Semantic extraction system (`semantic_map.py`, `activity_patterns.py`) with 36 patterns
- [x] All 36 MessageSemantics handlers registered in `semantic_handler_map.py`
- [x] Basic inbox endpoint at `POST /actors/{actor_id}/inbox/` with 202 response
- [x] Background task processing infrastructure via FastAPI BackgroundTasks
- [x] Unit tests for dispatcher and semantic matching (486 total passing; 0 xfailed)
- [x] Error hierarchy base (`VultronError` → `VultronApiError` → specific errors)
- [x] TinyDB data layer implementation with Protocol abstraction
- [x] Handler protocol with `@verify_semantics` decorator
- [x] ActivityStreams 2.0 Pydantic models (vocabulary implementation)
- [x] Rehydration system for expanding URI references to full objects

**Handler Business Logic Status:**

- ✅ Report + case + embargo + notes + status handlers complete (31/37):
  create_report, submit_report, validate_report (BT), invalidate_report,
  ack_report, close_report, engage_case (BT), defer_case (BT), create_case
  (BT), add_report_to_case, close_case, create_case_participant,
  add_case_participant_to_case, invite_actor_to_case,
  accept_invite_actor_to_case, reject_invite_actor_to_case,
  remove_case_participant_from_case, create_embargo_event,
  add_embargo_event_to_case, remove_embargo_event_from_case,
  announce_embargo_event_to_case, invite_to_embargo_on_case,
  accept_invite_to_embargo_on_case, reject_invite_to_embargo_on_case,
  create_note, add_note_to_case, remove_note_from_case,
  create_case_status, add_case_status_to_case, create_participant_status,
  add_participant_status_to_participant
- ✅ 0 stub handlers remain (all 37 handlers fully implemented)

**Production Readiness Features (Lower Priority per PRIORITIES.md):**

- [ ] Request validation (Content-Type, 1MB size limit, URI validation) - See Phase 1.1
- [ ] Standardized HTTP error responses (status, error, message, activity_id) - See Phase 1.2
- [ ] Health check endpoints (`/health/live`, `/health/ready`) - See Phase 1.3
- [ ] Structured logging with correlation IDs - See Phase 2.1
- [ ] Idempotency/duplicate detection - See Phase 2.2
- [ ] Test coverage enforcement (80%+ overall, 100% critical paths) - See Phase 3.1

**Deferred (Lowest Priority):**

- [ ] Response generation (Accept/Reject/TentativeReject responses back to submitter) - See Phase 5
- [ ] Async dispatcher optimization (FastAPI async processing already in place)
- [ ] agentic-readiness.md spec cleanup (see Priority 1000 in PRIORITIES.md)

## Prioritized Task List (Per PRIORITIES.md and Gap Analysis)

**Gap Analysis Summary (2026-02-24 refresh #5)**:

**✅ Completed Work:**

- ✅ **Phase 0 & 0A complete**: Report handlers (8 report) with full business logic
- ✅ **BT Phase BT-1 complete**: BT infrastructure + `validate_report` BT handler
- ✅ **BT Phase BT-2.0 complete**: CM-04/ID-04-004 compliance audit
- ✅ **BT Phase BT-2.1 complete**: `engage_case` + `defer_case` BT handlers
- ✅ **BT Phase BT-3 complete**: `create_case` (BT), `add_report_to_case`,
  `close_case` handlers + `initialize_case_demo.py`
- ✅ **BT Phase BT-4.1 complete**: `invite_actor_to_case`, `accept_invite_actor_to_case`,
  `reject_invite_actor_to_case`, `remove_case_participant_from_case`
- ✅ **BT Phase BT-4.2 complete**: `create_case_participant` + `add_case_participant_to_case`
- ✅ **BT Phase BT-4.3 complete**: `invite_actor_demo.py` (accept + reject paths)
- ✅ **BT Phase BT-5 complete**: All 7 embargo handlers + `establish_embargo_demo.py`
- ✅ **BT Phase BT-6 complete**: Notes + status handlers (7/7) + `status_updates_demo.py`
- ✅ **BT Phase BT-7 complete**: `suggest_actor_to_case`, `accept_suggest_actor_to_case`,
  `reject_suggest_actor_to_case`, `offer_case_ownership_transfer`,
  `accept_case_ownership_transfer`, `reject_case_ownership_transfer` + demo scripts
- ✅ **All 37 handlers implemented** (0 stubs remaining)
- ✅ **Demo scripts complete**: `receive_report_demo.py` + `initialize_case_demo.py` +
  `invite_actor_demo.py` + `establish_embargo_demo.py` + `status_updates_demo.py` +
  `suggest_actor_demo.py` + `transfer_ownership_demo.py`
- ✅ **525 tests passing**, 0 xfailed
- ✅ **Model fix**: `AcceptActorRecommendation`/`RejectActorRecommendation` now wrap
  the `RecommendActor` Offer as their `object` (consistent with all other Accept/Reject pairs)
- ✅ **Bug fixed**: `match_field` in `activity_patterns.py` handles string URI refs
  before `ActivityPattern` check (prevents crash)

**📊 Specification Compliance Status**:

- **BT Requirements**: BT-01 through BT-11 all implemented (BT-08 MAY, low priority)
- **Case Management (specs/case-management.md)**:
  - CM-01: ✅ Actor isolation implemented
  - CM-02: ✅ CaseActor lifecycle (create_case BT creates CaseActor)
  - CM-03: ✅ Data model correct (CaseStatus, ParticipantStatus)
  - CM-04: ✅ State transition scoping verified (BT-2.0 audit)
- **Idempotency (specs/idempotency.md)**:
  - ID-01/ID-04: ✅ Activity IDs and handler idempotency
  - ID-02/ID-03/ID-05: ❌ HTTP-layer duplicate detection not implemented (lower priority)

**❌ Remaining Gaps (prioritized per PRIORITIES.md)**:

- ❌ **Phase BT-2.2/2.3**: Optional `close_report` + `invalidate_report` BT refactors
- ❌ **Production readiness**: Request validation, error responses, health checks,
  structured logging, HTTP-layer idempotency (all `PROD_ONLY` or lower priority)

**🎯 Next Actions (ordered by PRIORITIES.md):**

1. **Phase BT-2.2/2.3** — Optional `close_report` + `invalidate_report` BT refactors

---

### ✅ COMPLETE: Phase 0A - receive_report_demo.py

**Goal**: Finish the demo script to properly demonstrate the report submission workflow from `docs/howto/activitypub/activities/report_vulnerability.md`.

**Status**: COMPLETE as of 2026-02-13

All Phase 0A tasks have been completed:

- ✅ 0A.1: Refactored demo into three separate workflow functions (demo_validate_report, demo_invalidate_report, demo_invalidate_and_close_report)
- ✅ 0A.2: Implemented missing workflow steps (all critical handlers working)
- ✅ 0A.4: Fixed endpoint issues (outbox retrieval, actor persistence, async timing)
- ✅ Demo test passing: `test/scripts/test_receive_report_demo.py::test_main_executes_without_raising`

**Commits:**

- a2fc317: "Refactor receive_report_demo.py into three separate workflow demonstrations"
- 17457e7: "zero out implementation notes after lessons learned"
- Multiple fixes for timing, persistence, and rehydration issues

---

### ✅ RESOLVED: Phase 0.5 - Test Infrastructure (FIXED)

**Priority**: WAS CRITICAL - Now resolved

**Issue**: Router tests were failing due to separate data layer instances in fixtures. ~~11 tests failing.~~

**Status**: RESOLVED - All router tests now passing (18/18 tests in `test/api/v2/routers/`)

**Resolution**: Test infrastructure appears to have been fixed. All router tests passing as of 2026-02-18.

**Tasks**:

- [x] **0.5.1**: Fixed `client_actors` fixture - dependency override working
- [x] **0.5.2**: Fixed `client_datalayer` fixture - dependency override working  
- [x] **0.5.3**: Verified all 18 router tests pass (no longer 11 failing)
  - `test/api/v2/routers/test_actors.py`: All passing
  - `test/api/v2/routers/test_datalayer.py`: All passing
  - `test/api/v2/test_v2_api.py`: All passing

---

### 🔴 TOP PRIORITY: Phase BT-1 - Behavior Tree Integration POC (IN PROGRESS)

**Status**: Phase BT-1 COMPLETE ✅ (BT-1.1 through BT-1.6)  
**Priority**: CRITICAL per PRIORITIES.md  
**Goal**: Integrate py_trees behavior tree execution with handler system  
**Reference**: `specs/behavior-tree-integration.md`,
`plan/IMPLEMENTATION_NOTES.md`

**Current Progress**: Infrastructure complete (bridge, helpers, validation tree). Next step is handler refactoring to use BT execution.

This phase implements a proof-of-concept for BT integration by refactoring one complex handler (`validate_report`) to use behavior trees. Success here validates the BT integration approach before expanding to other handlers.

#### BT-1.1: Infrastructure Setup

- [x] **BT-1.1.1**: Add `py_trees` to project dependencies
  - Update `pyproject.toml` with `py_trees = "^2.2.0"` (or latest stable)
  - Run `uv sync` to install
  - Verify import works: `python -c "import py_trees; print(py_trees.__version__)"`
  
- [x] **BT-1.1.2**: Create behavior tree directory structure
  - Create `vultron/behaviors/` directory
  - Create `vultron/behaviors/__init__.py`
  - Create `vultron/behaviors/report/` subdirectory
  - Create `test/behaviors/` directory structure
  
- [x] **BT-1.1.3**: Implement BT bridge layer
  - Created `vultron/behaviors/bridge.py`
  - Implemented `BTBridge` class:
    - `setup_tree(tree, actor_id, activity, **context_data)` - Sets up BehaviourTree with blackboard
    - `execute_tree(bt, max_iterations)` - Single-shot BT execution to completion
    - `execute_with_setup(...)` - Convenience method combining setup and execution
    - Blackboard setup with DataLayer injection and actor state
    - Error handling and logging
  - Comprehensive unit tests in `test/behaviors/test_bridge.py` (16 tests, all passing)
  - All 394 tests passing (including new BT tests)

#### BT-1.2: DataLayer-Aware BT Nodes

- [x] **BT-1.2.1**: Create DataLayer helper nodes
  - Created `vultron/behaviors/helpers.py` with base classes and common nodes:
    - `DataLayerCondition(py_trees.behaviour.Behaviour)`: Check state from DataLayer
    - `DataLayerAction(py_trees.behaviour.Behaviour)`: Modify state in DataLayer
    - `ReadObject(table, object_id)`: Read object from DataLayer and store in blackboard
    - `UpdateObject(object_id, updates)`: Update object in DataLayer with new values
    - `CreateObject(table, object_data)`: Create new object in DataLayer
  - Comprehensive unit tests in `test/behaviors/test_helpers.py` (18 tests, all passing)
  - All 412 tests passing (including new BT tests)

#### BT-1.3: Report Validation BT Implementation

- [x] **BT-1.3.1**: Analyze existing `validate_report` handler
  - Documented 6-phase procedural flow (rehydration, status updates, case creation, addressee collection, activity generation, outbox update)
  - Identified decision points and condition nodes for BT implementation
  - Compared against simulation BT structure
  - Created detailed analysis: `~/.copilot/session-state/.../files/validate_report_analysis.md`
  - Mapped proposed BT structure (Phase 1: minimal match, Phase 2: policy evaluation)
  - See IMPLEMENTATION_NOTES.md (2026-02-18) for details

- [x] **BT-1.3.2**: Implement report validation BT nodes
  - Created `vultron/behaviors/report/nodes.py` (724 lines, 10 node classes)
  - Implemented condition nodes: `CheckRMStateValid`, `CheckRMStateReceivedOrInvalid`
  - Implemented action nodes: `TransitionRMtoValid`, `TransitionRMtoInvalid`, `CreateCaseNode`, `CreateCaseActivity`, `UpdateActorOutbox`
  - Implemented policy stubs: `EvaluateReportCredibility`, `EvaluateReportValidity` (always SUCCESS)
  - Created comprehensive unit tests in `test/behaviors/report/test_nodes.py` (398 lines, 18 tests)
  - All nodes inherit from DataLayerCondition/DataLayerAction base classes
  - Blackboard key passing: case_id → CreateCaseActivity → activity_id → UpdateActorOutbox
  - Status updates via `set_status()`, DataLayer persistence
  - All 430 tests passing (412 base + 18 new)
  - See IMPLEMENTATION_NOTES.md (2026-02-18) for details
  - Note: Did not implement `CreateCaseActor` (deferred - not needed for minimal POC)

- [x] **BT-1.3.3**: Compose validation behavior tree
  - Created `vultron/behaviors/report/validate_tree.py` (139 lines)
  - Implemented `create_validate_report_tree(report_id, offer_id)` factory function
  - Tree structure (Phase 1 - Minimal):
    - Root: `Selector` (early exit OR full validation)
    - Child 1: `CheckRMStateValid` (short-circuit if already valid)
    - Child 2: `ValidationFlow` sequence:
      - `CheckRMStateReceivedOrInvalid` (precondition)
      - `EvaluateReportCredibility` (policy stub)
      - `EvaluateReportValidity` (policy stub)
      - `ValidationActions` sequence:
        - `TransitionRMtoValid` (status updates)
        - `CreateCaseNode` (case creation)
        - `CreateCaseActivity` (activity generation)
        - `UpdateActorOutbox` (outbox update)
  - Fixed blackboard key registration in nodes:
    - Added `setup()` override in `CreateCaseActivity` to register `case_id` READ access
    - Added `setup()` override in `UpdateActorOutbox` to register `activity_id` READ access
  - Created comprehensive integration tests in `test/behaviors/report/test_validate_tree.py` (12 tests, 502 lines)
  - Test coverage:
    - Tree creation and structure verification
    - Execution with different report states (RECEIVED, INVALID, VALID, no status)
    - Early exit optimization
    - Policy stub behavior
    - Error handling (missing DataLayer, actor_id, report)
    - Idempotency
    - Actor isolation
  - Fixed test_nodes.py to handle new blackboard key registrations (2 tests updated)
  - All 442 tests passing (430 base + 12 new)
  - Black formatting applied to all new/modified files

- [x] **BT-1.3.4**: Create default policy implementation
  - Created `vultron/behaviors/report/policy.py` with ValidationPolicy base class and AlwaysAcceptPolicy
  - Implemented `AlwaysAcceptPolicy`:
    - `is_credible(report) -> True` (prototype simplification)
    - `is_valid(report) -> True`
    - Log policy decisions at INFO level
  - Documented extension points for custom policies
  - Created comprehensive unit tests in `test/behaviors/report/test_policy.py` (12 tests)
  - All 454 tests passing (442 base + 12 new)
  - Black formatting applied

#### BT-1.4: Handler Refactoring

- [x] **BT-1.4.1**: Refactor `validate_report` handler to use BT
  - Modified `vultron/api/v2/backend/handlers.py:validate_report()`
  - Extract activity context (actor_id, report_id, offer_id)
  - Created `validate_report_tree` and executed via `BTBridge`
  - Handle BT execution results (SUCCESS/FAILURE/RUNNING)
  - Preserved `@verify_semantics` decorator and error handling
  - All 454 tests passing (including 5 reporting workflow tests)
  
- [x] **BT-1.4.2**: Update handler tests
  - Verified BT integration doesn't break existing tests
  - All tests in `test/api/v2/backend/test_handlers.py` passing
  - All tests in `test/api/test_reporting_workflow.py` passing (5 passed, 2 xfailed)
  - Demo test in `test/scripts/test_receive_report_demo.py` passing
  - State transitions match expected behavior
  - Case creation working correctly

#### BT-1.5: Demo and Validation

- [x] **BT-1.5.1**: Update demo script for BT validation
  - ✅ Demo script uses BT-enabled handler (validate_report refactored in BT-1.4)
  - ✅ All three workflows verified working (validate, invalidate, reject+close)
  - ✅ Added BT execution logging output (tree visualization, status, feedback)
  - ✅ Enhanced bridge logging with tree structure visualization at DEBUG level
  - ✅ Enhanced handler logging with detailed BT execution results
  - ✅ Updated demo script docstring with BT logging guidance
  
- [x] **BT-1.5.2**: Run full test suite
  - ✅ All 456 tests pass (no regressions)
  - ✅ Includes 76 BT tests + 2 new performance tests
  - ✅ Test coverage goal met for BT code
  
- [x] **BT-1.5.3**: Performance baseline
  - ✅ Measured BT execution performance via test/behaviors/test_performance.py
  - ✅ Performance results (100 runs): P50=0.44ms, P95=0.69ms, P99=0.84ms
  - ✅ Well within 100ms target (P99 < 1ms!)
  - ✅ No performance regression from BT integration

#### BT-1.6: Documentation

- [x] **BT-1.6.1**: Update specifications
  - Mark BT-01 through BT-10 requirements as implemented in `specs/behavior-tree-integration.md`
  - Add verification notes for completed requirements
  - Document any deviations from spec
  
- [x] **BT-1.6.2**: Create implementation notes
  - Document lessons learned in `plan/IMPLEMENTATION_NOTES.md`
  - Note any challenges with py_trees integration
  - Identify improvements for Phase BT-2

**Estimated Effort**: 3-5 days for experienced developer

**Success Criteria**:

- ✅ py_trees integrated and working
- ✅ `validate_report` handler uses BT execution
- ✅ All existing tests pass
- ✅ Demo script works with BT-enabled handler
- ✅ CaseActor creation fixed (BT-10-002 gap)
- ✅ Performance acceptable (P99 < 100ms)

**Deliverable**: Working POC demonstrating BT integration value

---

### 🔴 TOP PRIORITY: Phase BT-2 — Remaining Report Handler BTs

**Goal**: Extend BT integration to remaining complex report handlers, completing
the report management workflow with BT-powered logic throughout.

**Reference simulation trees**: `vultron/bt/report_management/_behaviors/`

**Decision guide** (from IMPLEMENTATION_NOTES.md):

- Use BTs for complex handlers with multiple branches/state transitions
- Keep procedural for simple CRUD-style handlers (create_report, ack_report)

#### BT-2.0: CM-04 + ID-04-004 Compliance Audit (NEW — 2026-02-20)

New specs `case-management.md` (CM-04) and `idempotency.md` (ID-04-004) require
state-changing handlers to scope state updates correctly and to be idempotent.
The completed `engage_case` and `defer_case` handlers need explicit verification.

- [x] **BT-2.0.1**: Verify `engage_case` updates `ParticipantStatus.rm_state`
  (participant-specific RM — CM-04-001) and NOT `CaseStatus`
- [x] **BT-2.0.2**: Verify `defer_case` updates `ParticipantStatus.rm_state`
  (CM-04-001) and NOT `CaseStatus`
- [x] **BT-2.0.3**: Add idempotency guard to `engage_case` BT tree — if participant
  RM is already ACCEPTED, log at INFO and return (ID-04-004 MUST)
- [x] **BT-2.0.4**: Add idempotency guard to `defer_case` BT tree — if participant
  RM is already DEFERRED, log at INFO and return (ID-04-004 MUST)
- [x] **BT-2.0.5**: Update tests to verify idempotent re-execution behavior
  (same input twice → same state, no error)

#### BT-2.1: `engage_case` / `defer_case` BTs (was "prioritize_report") ✅ COMPLETE

The original plan called this "prioritize_report" but the correct framing is
case-level: RM is a **participant-specific** state machine. Each
`CaseParticipant` carries its own RM state in `participant_status[].rm_state`.
The simulation BT `RMPrioritizeBt` corresponds to the receive-side of
`RmEngageCase` and `RmDeferCase` activities.

- [x] Added `ENGAGE_CASE` and `DEFER_CASE` to `MessageSemantics` in `enums.py`
- [x] Added `EngageCase` (Join(VulnerabilityCase)) and `DeferCase`
  (Ignore(VulnerabilityCase)) patterns to `activity_patterns.py`
- [x] Registered patterns in `semantic_map.py`
- [x] Added `PrioritizationPolicy` and `AlwaysPrioritizePolicy` to
  `vultron/behaviors/report/policy.py`
- [x] Implemented BT nodes in `vultron/behaviors/report/nodes.py`:
  - `CheckParticipantExists`
  - `TransitionParticipantRMtoAccepted`
  - `TransitionParticipantRMtoDeferred`
  - `EvaluateCasePriority` (stub for outgoing direction / future SSVC)
- [x] Implemented `vultron/behaviors/report/prioritize_tree.py` with
  `create_engage_case_tree` and `create_defer_case_tree`
- [x] Added `engage_case` and `defer_case` handlers in `handlers.py`
- [x] Registered handlers in `semantic_handler_map.py`
- [x] Added tests in `test/behaviors/report/test_prioritize_tree.py`
  (11 tests, covering structure, success, failure, and participant isolation)
- [x] Documented SSVC deferral in `specs/prototype-shortcuts.md` PROTO-05-001

#### BT-2.2: `close_report` BT (OPTIONAL — already has procedural logic)

`close_report` already has full procedural business logic (~84 lines). A BT
refactor is valuable but not urgent. Reference:
`vultron/bt/report_management/_behaviors/close_report.py:RMCloseBt`.

- [ ] Implement `vultron/behaviors/report/close_tree.py`
  - Sequence: check preconditions (RM in closeable state) → transition to CLOSED
    → emit RmCloseReport activity → update outbox
- [ ] Refactor `close_report` handler to use BT
- [ ] Update tests

#### BT-2.3: `invalidate_report` BT (OPTIONAL — already has procedural logic)

Already implemented procedurally. Reference: `_InvalidateReport` subtree in
`vultron/bt/report_management/_behaviors/validate_report.py`.

- [ ] Implement `vultron/behaviors/report/invalidate_tree.py`
  - Sequence: check RM state received → transition to INVALID → emit RI activity
    → update outbox
- [ ] Refactor `invalidate_report` handler to use BT
- [ ] Update tests

#### BT-2.4: Assess remaining simple report handlers

- [ ] Evaluate `create_report`, `submit_report`, `ack_report` for BT value
  - These are simple CRUD/state operations; procedural code is likely sufficient
  - Document decision in IMPLEMENTATION_NOTES.md

---

### 🔴 TOP PRIORITY: Phase BT-3 — Case Management Demo

**Goal**: Demonstrate `initialize_case` and `manage_case` ActivityPub workflows
as standalone demo script. Reference:
`docs/howto/activitypub/activities/initialize_case.md`,
`docs/howto/activitypub/activities/manage_case.md`

**Key spec reference**: `specs/case-management.md` CM-02 (CaseActor lifecycle),
CM-03 (state model), CM-04 (state transition correctness). All BT nodes and
handlers in this phase MUST comply with CM-04 scoping rules.

**Workflows to demo**: CreateCase → AddReportToCase → AddParticipantToCase →
(optionally) prioritize → engage/defer → close

**Simulation reference**: `vultron/bt/case_state/` (conditions, transitions),
but note: no `_behaviors/` subdirectory exists for case state — implement
fresh using case_state conditions/transitions as reference.

#### BT-3.1: `create_case` handler (BT-powered) ✅ COMPLETE

- [x] Implement `vultron/behaviors/case/` directory with `__init__.py`
- [x] Implement `vultron/behaviors/case/create_tree.py`
  - Selector: CheckCaseAlreadyExists (idempotency early exit) OR
    CreateCaseFlow Sequence (validate → persist → CaseActor → emit → outbox)
- [x] Implement BT nodes in `vultron/behaviors/case/nodes.py`:
  - `CheckCaseAlreadyExists`: idempotency guard — SUCCESS if case already in DataLayer
  - `ValidateCaseObject`: check required fields on incoming case
  - `PersistCase`: create VulnerabilityCase in DataLayer (CM-02-001)
  - `CreateCaseActorNode`: create CaseActor service in DataLayer (CM-02-001)
  - `EmitCreateCaseActivity`: generate `CreateCase` activity for outbox
  - `UpdateActorOutbox`: append activity to actor outbox
- [x] Refactor `create_case` handler in `handlers.py` to use BT
- [x] Add `test/behaviors/case/test_create_tree.py` (8 tests)

#### BT-3.2: `add_report_to_case` handler (procedural — simpler) ✅ COMPLETE

- [x] Implement `add_report_to_case` handler:
  - Rehydrate case and report from payload
  - Append report ID to `case.vulnerability_reports` list (idempotent check)
  - Persist updated case via `dl.update(case_id, object_to_record(case))`
  - Log state transition at INFO level

#### BT-3.3: `close_case` handler (procedural) ✅ COMPLETE

- [x] Implement `close_case` handler:
  - Rehydrate actor and case from Leave(VulnerabilityCase) payload
  - Create RmCloseCase activity and persist to DataLayer
  - Update actor outbox; idempotent on duplicate activity
  - Log at INFO level

#### BT-3.4: `engage_case` / `defer_case` mapping ✅ COMPLETE (done in BT-2.1)

- [x] `ENGAGE_CASE` / `DEFER_CASE` semantics, patterns, and handlers
  implemented in BT-2.1. See notes there.

#### BT-3.5: `initialize_case` demo script ✅ COMPLETE

- [x] Create `vultron/scripts/initialize_case_demo.py`
  - Setup: create actor, submit report, validate report (reuse receive_report
    workflow as precondition)
  - Demo: create case → add report to case → add participant to case
  - Show case state at each step

---

### 🔴 TOP PRIORITY: Phase BT-4 — Actor Invitation + Participant Demo

**Goal**: Demonstrate `invite_actor`, `initialize_participant`, and
`manage_participants` workflows. Reference:
`docs/howto/activitypub/activities/invite_actor.md`,
`docs/howto/activitypub/activities/initialize_participant.md`,
`docs/howto/activitypub/activities/manage_participants.md`

#### BT-4.1: Actor invitation handlers ✅ COMPLETE (2026-02-23)

**Direction note**: Per `invite_actor.md` sequence diagram, the Case Owner
sends `Invite(object=Case)` to an Actor. The **receiving** Actor's inbox
handler (`invite_actor_to_case`) stores the invite for local decision. The
Case Owner's inbox then handles `Accept(object=Case, inReplyTo=Invite)`
via `accept_invite_actor_to_case`, which creates the CaseParticipant. This
means the *create-participant logic lives in the accept handler*, not the
invite handler.

- [x] Implement `invite_actor_to_case` handler:
  - Store Invite activity in DataLayer; idempotent
- [x] Implement `accept_invite_actor_to_case` handler:
  - Rehydrate invitation; create CaseParticipant; add to case; idempotent
- [x] Implement `reject_invite_actor_to_case` handler:
  - Log rejection at INFO; no state change

#### BT-4.2: Case participant handlers ✅ COMPLETE (done in BT-3.5)

- [x] Implement `create_case_participant` handler:
  - Create `CaseParticipant` object with attributed_to reference and role
  - Persist to DataLayer
- [x] Implement `add_case_participant_to_case` handler:
  - Rehydrate case and participant
  - Add participant ID to `case.case_participants`
  - Persist updated case
- [x] Implement `remove_case_participant_from_case` handler:
  - Remove participant from `case.case_participants`; idempotent; persist

#### BT-4.3: Participant management demo script

- [x] Create `vultron/scripts/invite_actor_demo.py`
  - Setup: initialize case with first actor
  - Demo accept: case owner invites coordinator → coordinator accepts →
    participant added → show updated participant list
  - Demo reject: case owner invites coordinator → coordinator rejects →
    participant list unchanged
  - Fixed `InviteActorToCase` pattern: removed `object_=AOtype.ACTOR`
    (real actors have type "Organization"/"Person", not "Actor")

---

### ✅ COMPLETE: Phase BT-5 — Embargo Management Demo

**Goal**: Demonstrate `establish_embargo` and `manage_embargo` workflows.
Reference: `docs/howto/activitypub/activities/establish_embargo.md`,
`docs/howto/activitypub/activities/manage_embargo.md`

**Status**: COMPLETE as of 2026-02-23

**Simulation reference**: `vultron/bt/embargo_management/` (behaviors.py,
conditions.py, states.py, transitions.py — no `_behaviors/` subdirectory,
translate directly from these files).

**Pre-condition resolved**: Fixed `EmAcceptEmbargo` + `EmRejectEmbargo`
`as_object` type to `EmProposeEmbargoRef` (Accept/Reject target the proposal
activity). Fixed `InviteToEmbargoOnCase`, `AnnounceEmbargoEventToCase`,
`RemoveEmbargoEventFromCase` activity patterns.

**Key spec reference**: `specs/case-management.md` CM-04-003 — EM state
transitions MUST update `CaseStatus.em_state` (participant-agnostic, shared).

#### BT-5.1: Core embargo handlers ✅

- [x] Implement `create_embargo_event` handler:
  - Create `EmbargoEvent` object with timeline/terms; persist to DataLayer
- [x] Implement `add_embargo_event_to_case` / `ActivateEmbargo` handler:
  - Link embargo to case; sets `active_embargo`; transitions EM → PROPOSED; persist
- [x] Implement `remove_embargo_event_from_case` handler:
  - Removes active embargo; transitions EM → NONE; persist
- [x] Implement `announce_embargo_event_to_case` handler:
  - Logs event (cannot write typed activity to `case_activity` due to type limitation)

#### BT-5.2: Embargo negotiation handlers ✅

- [x] Implement `invite_to_embargo_on_case` / `EmProposeEmbargo` handler:
  - Stores invite activity in DataLayer
- [x] Implement `accept_invite_to_embargo_on_case` / `EmAcceptEmbargo` handler:
  - Sets `active_embargo`; transitions EM → ACTIVE via `set_embargo()`
- [x] Implement `reject_invite_to_embargo_on_case` / `EmRejectEmbargo` handler:
  - Stores reject activity; no state change

#### BT-5.3: Embargo demo script ✅

- [x] Create `vultron/scripts/establish_embargo_demo.py`
  - Propose-accept path: case → propose embargo → accept → embargo activated
  - Propose-reject path: case → propose embargo → reject → no embargo
  - Tests: `test/scripts/test_establish_embargo_demo.py` (both paths pass)

---

### 🔴 TOP PRIORITY: Phase BT-6 — Status Updates + Acknowledge Demo

**Goal**: Demonstrate `status_updates` and `acknowledge` workflows. Reference:
`docs/howto/activitypub/activities/status_updates.md`,
`docs/howto/activitypub/activities/acknowledge.md`

#### BT-6.1: Note handlers

- [x] Implement `create_note` handler: create `as:Note` object, persist to DataLayer
- [x] Implement `add_note_to_case` handler: append note ID to `case.notes`, persist
- [x] Implement `remove_note_from_case` handler: remove note from `case.notes`, persist

#### BT-6.2: Status handlers

- [x] Implement `create_case_status` handler: create `CaseStatus` object, persist
- [x] Implement `add_case_status_to_case` handler: set `case.status`, persist
- [x] Implement `create_participant_status` handler: create `ParticipantStatus`, persist
- [x] Implement `add_participant_status_to_participant` handler: set status on
  participant, persist

#### BT-6.3: Acknowledge (`ack_report`) review

- [x] Review `ack_report` handler against `docs/howto/activitypub/activities/acknowledge.md`
- [x] `RmReadReport` is already handled by `ack_report` — verify correctness and
  update if needed

#### BT-6.4: Status updates demo script

- [x] Create `vultron/scripts/status_updates_demo.py`
  - Demo: create note → add to case → create status → add to case → show updated case

---

### ✅ COMPLETE: Phase BT-7 — Ownership Transfer + Suggest Actor

**Goal**: Lower-priority workflows from PRIORITIES.md.

- [x] Implement `suggest_actor_to_case`, `accept_suggest_actor_to_case`,
  `reject_suggest_actor_to_case` handlers
- [x] Implement `offer_case_ownership_transfer`, `accept_case_ownership_transfer`,
  `reject_case_ownership_transfer` handlers
- [x] Create `vultron/scripts/suggest_actor_demo.py`
- [x] Create `vultron/scripts/transfer_ownership_demo.py`

---

If the goal is to harden the current implementation for real-world use, see the
detailed task lists in
[Comprehensive Prioritized Task List](#comprehensive-prioritized-task-list-updated-per-prioritiesmd)
below (Phases 1–7, all deferred).

## Open Questions & Design Decisions

### Resolved Questions

#### Q1: Async Dispatcher Priority

**Question**: Specs `DR-04-001` and `DR-04-002` recommend async queue-based dispatcher for production. Should this be prioritized now or deferred?

**Decision**: DEFERRED. FastAPI BackgroundTasks already provides async processing at the endpoint level. Downstream processing can remain synchronous until we have performance data indicating need for queue-based architecture.

#### Q2: Test Organization

**Question**: Should we separate unit and integration tests into `test/unit/` and `test/integration/` directories per `TB-04-003`, or use pytest markers?

**Decision**: Use pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`). Simpler to implement and maintain. Can reorganize directory structure later if needed.

#### Q3: URI Validation Scope

**Question**: Spec `MV-05-001` requires URI validation. Should this be syntax-only or include reachability checks?

**Decision**: Syntax-only validation using Pydantic validators. Check for well-formed URIs with acceptable schemes (http, https, urn). No reachability/liveness checks required at this stage.

#### Q4: Handler Implementation Order

**Question**: With 47 handlers to implement, should we prioritize by CVD workflow criticality or by semantic grouping?

**Decision**: DEFER all handler business logic to Phase 4. Focus first on infrastructure: request validation, semantic extraction, dispatch routing, error handling. Verify correct handler invocation without implementing business logic.

#### Q5: Authorization System

**Question**: Multiple specs reference authorization (e.g., `HP-05-001`), but no auth system exists. Should this be specified and implemented?

**Decision**: OUT OF SCOPE for initial implementation. Design system to allow easy auth layer integration later. For now, assume all requests are authorized. Focus on message handling functionality.

### Open Questions

#### Q6: Duplicate Detection Storage

**Question**: Should duplicate detection use in-memory cache (simple, fast, non-persistent) or TinyDB (persistent, survives restarts)?

**Options**:

- Option A: In-memory cache with TTL (e.g., Python dict with timestamps or `cachetools`)
  - Pros: Fast, simple implementation
  - Cons: Lost on restart, not shared across processes
- Option B: TinyDB table with activity IDs and timestamps
  - Pros: Persistent, consistent across restarts
  - Cons: Slower, requires cleanup logic

**Recommendation**: Start with Option A for simplicity. Upgrade to Option B if persistence proves necessary.

#### Q7: Structured Logging Format

**Question**: Should structured logs use JSON format (machine-parseable) or enhanced key-value format (human-readable)?

**Options**:

- JSON format: `{"timestamp": "...", "level": "INFO", "component": "...", "message": "..."}`
- Key-value format: `2026-02-13T16:00:00Z [INFO] component=inbox_handler activity_id=... message=...`

**Recommendation**: JSON format for production parsability. Can add console-friendly formatter for development.

#### Q8: Health Check Ready Conditions

**Question**: What should `/health/ready` check beyond data layer connectivity?

**Considerations**:

- Data layer read/write access
- Disk space availability
- Memory usage thresholds
- Queue depth (if async queue implemented)

**Recommendation**: Start with data layer connectivity check only. Add more checks as system complexity grows.

#### Q9: Test Coverage Enforcement

**Question**: Should coverage enforcement be strict (fail build on any decrease) or threshold-based (fail only below 80%)?

**Recommendation**: Threshold-based initially (80% overall, 100% critical paths). Can tighten to strict enforcement once stable.

#### Q10: Response Generation Timing

**Question**: When Phase 5 is implemented, should response generation be synchronous (blocking handler) or async (queued after handler returns)?

**Consideration**: Affects handler protocol design and testing approach.

**Recommendation**: Defer decision until Phase 4 handler logic is better understood. Likely async to maintain fast handler execution.

---

## Notes

**Research Prototype Context**: This is a research project exploring federated CVD protocol design. The focus is on:

- Demonstrating protocol feasibility
- Validating behavior tree modeling approach
- Establishing ActivityStreams vocabulary for CVD
- Building foundation for future interoperability

Performance optimization and production hardening are explicitly **not priorities** at this stage. The goal is correctness and specification compliance, not scale.

---

## Comprehensive Prioritized Task List (Updated per PRIORITIES.md)

### Status Legend

- ✅ Complete
- 🔄 In Progress
- ⏸️ Blocked/Waiting
- ❌ Not Started (Deferred)

---

### TOP PRIORITY: Phase 0A - Complete Demo Script ✅ COMPLETE

See detailed tasks in Phase 0A section above.

---

### DEFERRED: Production Readiness Phases

All remaining phases (1-7) are deferred per PRIORITIES.md. Below is the detailed breakdown for reference.

### DEFERRED: Phase 1 - Critical Infrastructure ❌

#### 1.1 Request Validation Middleware ❌

- [ ] Create `vultron/api/v2/middleware/validation.py` module
- [ ] Implement Content-Type validation middleware
  - [ ] Accept `application/activity+json` (HP-01-001)
  - [ ] Accept `application/ld+json; profile="..."` (HP-01-002)
  - [ ] Return HTTP 415 for invalid Content-Type (HP-01-003)
- [ ] Implement payload size limit middleware
  - [ ] Check Content-Length header
  - [ ] Return HTTP 413 for requests > 1MB (HP-02-001)
  - [ ] Log oversized requests at WARNING level
- [ ] Add URI validation to Pydantic models
  - [ ] Create custom validator for `as_id` fields
  - [ ] Validate URI schemes (http, https, urn) (MV-05-001)
  - [ ] Syntax-only check (no reachability)
- [ ] Register middleware in FastAPI app
- [ ] Add unit tests for middleware
  - [ ] Test Content-Type acceptance/rejection
  - [ ] Test payload size limits
  - [ ] Test URI validation
- [ ] Add integration tests
  - [ ] Test invalid Content-Type → 415
  - [ ] Test oversized payload → 413
  - [ ] Test invalid URIs → 422
- **Specs**: HP-01-001/002/003, HP-02-001, MV-05-001, IE-03-001/002
- **Estimated Effort**: 1-2 days

#### 1.2 Standardized HTTP Error Responses ❌

- [ ] Create `vultron/api/v2/exception_handlers.py` module
- [ ] Define custom exception handler function
  - [ ] Match on `VultronError` base class
  - [ ] Extract HTTP status code from exception type
  - [ ] Build JSON response with fields: status, error, message, activity_id
- [ ] Update exception classes
  - [ ] Add `activity_id: str | None` attribute to VultronError
  - [ ] Add `actor_id: str | None` attribute to VultronError
  - [ ] Add `original_exception: Exception | None` for wrapping
  - [ ] Add `http_status_code: int` class attribute to all exceptions
- [ ] Define status code mapping
  - [ ] ValidationError → 422
  - [ ] ProtocolError → 400
  - [ ] NotFoundError → 404
  - [ ] SystemError → 500
  - [ ] (Create specific exception types as needed)
- [ ] Implement error logging
  - [ ] Log 4xx errors at WARNING level
  - [ ] Log 5xx errors at ERROR level with stack trace
- [ ] Register exception handler in `app.py`
- [ ] Add unit tests
  - [ ] Test each exception type → correct status code
  - [ ] Test JSON response format
  - [ ] Test context attributes included
- [ ] Add integration tests
  - [ ] Test validation error → 422 with details
  - [ ] Test system error → 500 with message
  - [ ] Test error logging levels
- **Specs**: EH-04-001, EH-05-001, EH-06-001
- **Estimated Effort**: 1-2 days

#### 1.3 Health Check Endpoints ❌

- [ ] Create `vultron/api/v2/routers/health.py` module
- [ ] Implement `/health/live` endpoint
  - [ ] Return 200 if process running
  - [ ] Minimal logic (just proves process alive)
  - [ ] Response: `{"status": "ok"}`
- [ ] Implement `/health/ready` endpoint
  - [ ] Check data layer connectivity
  - [ ] Try simple read operation from data layer
  - [ ] Return 200 if ready, 503 if not
  - [ ] Response: `{"status": "ready", "checks": {"datalayer": "ok"}}`
- [ ] Register health router in `app.py`
- [ ] Add integration tests
  - [ ] Test `/health/live` returns 200
  - [ ] Test `/health/ready` returns 200 when data layer available
  - [ ] Test `/health/ready` returns 503 when data layer unavailable (mock failure)
- **Specs**: OB-05-001, OB-05-002
- **Estimated Effort**: 0.5 days

---

### DEFERRED: Phase 2 - Observability & Reliability ❌

#### 2.1 Structured Logging Implementation ❌

- [ ] Create `vultron/api/v2/logging_config.py` module
- [ ] Define structured log format
  - [ ] Choose format: JSON (recommended) or key-value
  - [ ] Include fields: timestamp (ISO 8601), level, component, activity_id, actor_id, message
  - [ ] Create formatter class
- [ ] Implement correlation ID context manager
  - [ ] Use contextvars to store correlation_id
  - [ ] Extract activity_id as correlation ID
  - [ ] Propagate through all log entries
  - [ ] Create decorator for automatic correlation ID injection
- [ ] Add lifecycle logging at INFO level
  - [ ] Activity received (with activity_id, actor_id)
  - [ ] Activity validated (with semantic type)
  - [ ] Activity queued for processing
  - [ ] Handler invoked (with handler name)
  - [ ] State transitions (before → after)
  - [ ] Processing completed (with result)
- [ ] Implement consistent log level usage
  - [ ] DEBUG: Diagnostic details, payload contents
  - [ ] INFO: Lifecycle events, state changes
  - [ ] WARNING: Recoverable issues, validation warnings, 4xx errors
  - [ ] ERROR: Unrecoverable failures, handler exceptions, 5xx errors
  - [ ] CRITICAL: System-level failures (currently unused)
- [ ] Add audit trail logging
  - [ ] State transition logs (case states, embargo states)
  - [ ] Data access operations (at DEBUG level)
- [ ] Update all handlers to use structured logging
- [ ] Add unit tests (use caplog fixture)
  - [ ] Test log format includes required fields
  - [ ] Test correlation ID propagation
  - [ ] Test log levels used correctly
- [ ] Add integration tests
  - [ ] Test end-to-end logging for activity flow
  - [ ] Test all logs for an activity share activity_id
- **Specs**: OB-01-001, OB-02-001, OB-03-001, OB-04-001, OB-06-001/002/003
- **Estimated Effort**: 2-3 days

#### 2.2 Idempotency and Duplicate Detection ❌

- [ ] Design activity ID tracking mechanism
  - [ ] Choose storage: In-memory cache (Option A) or TinyDB (Option B)
  - [ ] Recommendation: Start with Option A (Python dict with timestamps)
- [ ] Create `vultron/api/v2/deduplication.py` module
- [ ] Implement ActivityCache class
  - [ ] Store activity IDs with timestamps
  - [ ] Check if activity ID already processed
  - [ ] Add TTL-based expiration (24 hours)
  - [ ] Thread-safe access (use locks)
- [ ] Integrate duplicate detection into inbox endpoint
  - [ ] Check activity ID before processing
  - [ ] Return HTTP 202 immediately for duplicates (no reprocessing)
  - [ ] Log duplicate detection at INFO level
- [ ] Add background cleanup task
  - [ ] Remove expired activity IDs periodically
  - [ ] Run every hour or on schedule
- [ ] Handle edge cases
  - [ ] Different activities with same ID (log warning)
  - [ ] Concurrent submissions (lock-based protection)
- [ ] Add unit tests
  - [ ] Test cache stores and retrieves activity IDs
  - [ ] Test TTL expiration works correctly
  - [ ] Test thread-safe access
- [ ] Add integration tests
  - [ ] Submit same activity twice → second returns 202 without reprocessing
  - [ ] Verify logs show duplicate detection
  - [ ] Test cleanup after TTL expiration
- **Specs**: IE-10-001, IE-10-002, MV-08-001
- **Estimated Effort**: 1-2 days

---

### DEFERRED: Phase 3 - Testing Infrastructure & Coverage ❌

#### 3.1 Configure Test Coverage Enforcement ❌

- [ ] Add pytest-cov to dependencies (if not present)
- [ ] Configure pytest-cov in `pyproject.toml`
  - [ ] Set `--cov=vultron` flag
  - [ ] Set minimum coverage threshold: 80% overall
  - [ ] Configure fail_under for critical modules: 100%
  - [ ] Set report formats: term-missing, html, xml
  - [ ] Add coverage omit patterns (tests, **init**.py files)
- [ ] Run baseline coverage measurement
  - [ ] Execute: `pytest --cov=vultron --cov-report=term-missing --cov-report=html`
  - [ ] Document current coverage percentages in IMPLEMENTATION_NOTES.md
  - [ ] Identify low-coverage modules
- [ ] Add coverage badge to README (optional)
- [ ] Add coverage checks to CI pipeline (if using CI)
  - [ ] Fail build if coverage drops below 80%
  - [ ] Fail build if critical paths below 100%
  - [ ] Generate and publish HTML coverage reports
- **Specs**: TB-02-001, TB-02-002
- **Estimated Effort**: 0.5 days

#### 3.2 Create Integration Test Suite ❌

- [ ] Create `test/api/v2/integration/` directory structure
- [ ] Add pytest markers to `pyproject.toml`
  - [ ] Define `unit` marker for isolated tests
  - [ ] Define `integration` marker for full-stack tests
- [ ] Implement end-to-end inbox flow tests
  - [ ] Test: Valid activity → 202 → handler invoked
  - [ ] Test: Invalid Content-Type → 415
  - [ ] Test: Oversized payload → 413
  - [ ] Test: Malformed activity → 422
  - [ ] Test: Unknown actor → 404
  - [ ] Test: Duplicate activity → 202 (no reprocessing)
  - [ ] Test: Async processing with BackgroundTasks
- [ ] Implement semantic extraction integration tests
  - [ ] Test all 36 semantic patterns with real activities
  - [ ] Verify correct handler invocation for each
  - [ ] Test pattern ordering (specific before general)
- [ ] Implement error handling integration tests
  - [ ] Test all HTTP error codes (400, 404, 405, 413, 415, 422, 500)
  - [ ] Verify error response format
  - [ ] Verify error logging
- [ ] Implement logging integration tests
  - [ ] Test structured log format
  - [ ] Test correlation ID propagation
  - [ ] Test log levels
- **Specs**: TB-03-001, TB-03-002, TB-03-003, TB-04-003
- **Estimated Effort**: 3-4 days

#### 3.3 Enhance Test Infrastructure ❌

- [ ] Create `test/factories.py` module
- [ ] Implement test data factories
  - [ ] Factory for VulnerabilityReport objects
  - [ ] Factory for VulnerabilityCase objects
  - [ ] Factory for ActivityStreams activities (Create, Accept, Reject, etc.)
  - [ ] Factory for Actor objects
  - [ ] Use realistic domain data in tests
- [ ] Centralize fixtures in root `conftest.py`
  - [ ] Shared `client` fixture (FastAPI TestClient)
  - [ ] Shared `datalayer` fixture with automatic cleanup
  - [ ] Shared `test_actor` fixture
  - [ ] Activity factory fixtures
- [ ] Improve test isolation
  - [ ] Ensure database cleared between tests
  - [ ] Ensure no global state leakage
  - [ ] Add cleanup hooks for all fixtures
  - [ ] Add markers for parallel-safe tests
- [ ] Document test patterns and conventions
  - [ ] Add `docs/testing-guide.md` document
  - [ ] Include examples of good test structure
  - [ ] Document fixture usage
  - [ ] Document markers usage
- **Specs**: TB-05-001, TB-05-002, TB-05-003, TB-05-004, TB-06-001
- **Estimated Effort**: 2-3 days

---

### DEFERRED: Phase 4 - Additional Handler Business Logic ✅ COMPLETE

**Status**: ✅ COMPLETE — All 37 handlers implemented via BT phases BT-1 through
BT-7 (see BT phases above for details).

**Completed Handlers** (37/37):

- ✅ **Report handlers (8)**: create_report, submit_report, validate_report (BT),
  invalidate_report, ack_report, close_report, engage_case (BT), defer_case (BT)
- ✅ **Case handlers (5)**: create_case (BT), add_report_to_case, close_case,
  create_case_participant, add_case_participant_to_case
- ✅ **Actor invitation handlers (4)**: invite_actor_to_case,
  accept_invite_actor_to_case, reject_invite_actor_to_case,
  remove_case_participant_from_case
- ✅ **Embargo handlers (7)**: create_embargo_event, add_embargo_event_to_case,
  remove_embargo_event_from_case, announce_embargo_event_to_case,
  invite_to_embargo_on_case, accept_invite_to_embargo_on_case,
  reject_invite_to_embargo_on_case
- ✅ **Metadata handlers (7)**: create_note, add_note_to_case, remove_note_from_case,
  create_case_status, add_case_status_to_case, create_participant_status,
  add_participant_status_to_participant
- ✅ **Suggest/Ownership handlers (6)**: suggest_actor_to_case,
  accept_suggest_actor_to_case, reject_suggest_actor_to_case,
  offer_case_ownership_transfer, accept_case_ownership_transfer,
  reject_case_ownership_transfer
- ✅ **Special (1)**: unknown (logs WARNING and returns None)

**Implementation Pattern** (established by report handlers):

1. Extract relevant objects from `dispatchable.payload`
2. Rehydrate nested object references using data layer
3. Validate business rules and object types
4. Persist state changes via data layer `create()` or `update()`
5. Update actor outbox if creating new activities
6. Log state transitions at INFO level
7. Handle errors gracefully with appropriate exceptions

---

### DEFERRED: Phase 5 - Response Generation

**Status**: DEFERRED until Phase 4 complete

**Dependencies**:

- Phase 4 complete (all handler business logic)
- Understanding of response patterns from real-world usage

- [ ] Design response activity patterns
  - [ ] Map handler outcomes to response types
  - [ ] Define `inReplyTo` correlation rules
  - [ ] Design error extension format
- [ ] Implement response generation
  - [ ] Accept response builder
  - [ ] Reject response builder
  - [ ] TentativeReject response builder
  - [ ] Update response builder
  - [ ] Error response builder with extensions
- [ ] Implement response correlation
  - [ ] Add `inReplyTo` field to all responses
  - [ ] Track original activity ID
  - [ ] Prevent duplicate responses
- [ ] Implement response delivery
  - [ ] Queue responses to actor outbox
  - [ ] Process outbox for delivery
  - [ ] Handle delivery failures
  - [ ] Retry logic with backoff
- [ ] Add tests
  - [ ] Unit tests for response builders
  - [ ] Integration tests for response delivery
  - [ ] Test duplicate response prevention
- **Files**: New `vultron/api/v2/backend/response_builder.py`, update handlers
- **Specs**: RF-02-001, RF-03-001, RF-04-001, RF-05-001, RF-06-001, RF-08-001
- **Tests**: `test/api/v2/backend/test_response_generation.py`
- **Estimated Effort**: 5-7 days

---

### DEFERRED: Phase 6 - Code Quality & Documentation

#### 6.1 Code Style Compliance ❌

- [ ] Run `black --check vultron/`
- [ ] Fix any formatting issues
- [ ] Verify import organization (stdlib, third-party, local)
- [ ] Check for circular imports
  - [ ] Core modules should not import from API layer
  - [ ] Document module dependency graph
- [ ] Run `mypy vultron/`
- [ ] Fix type errors
- [ ] Add missing type hints
- [ ] Add docstrings to all public functions
- [ ] Add docstrings to all classes
- **Specs**: CS-01-001 through CS-05-001
- **Estimated Effort**: 1-2 days

#### 6.2 Documentation Updates ❌

- [ ] Update API documentation
  - [ ] Document inbox endpoint behavior
  - [ ] Document health check endpoints
  - [ ] Document error response formats
  - [ ] Add request/response examples
- [ ] Create specification compliance matrix
  - [ ] Document which specs are implemented
  - [ ] List known gaps and limitations
  - [ ] Update as implementation progresses
- [ ] Add inline documentation
  - [ ] Complex logic explanations where needed
- [ ] Create troubleshooting guide
  - [ ] Common error scenarios
  - [ ] Debugging tips
  - [ ] Log analysis examples
- **Estimated Effort**: 2-3 days

---

### FUTURE: Phase 7 - Performance & Scalability

**Status**: DEFERRED - Post-research phase

- [ ] Evaluate async dispatcher implementation
  - [ ] Queue-based processing (Redis, RabbitMQ)
  - [ ] Worker pool architecture
  - [ ] Horizontal scaling support
- [ ] Database optimization
  - [ ] Replace TinyDB with production database
  - [ ] Add indexes for common queries
  - [ ] Implement connection pooling
- [ ] Caching strategies
  - [ ] Actor metadata caching
  - [ ] Activity deduplication cache
  - [ ] Response template caching
- [ ] Rate limiting
  - [ ] Per-actor rate limits
  - [ ] Global rate limits
  - [ ] Backpressure mechanisms
- [ ] Monitoring and metrics
  - [ ] Prometheus metrics export
  - [ ] Request latency tracking
  - [ ] Queue depth monitoring
  - [ ] Error rate alerting
- **Files**: TBD based on performance requirements
- **Specs**: Not yet specified
- **Tests**: Performance test suite
- **Estimated Effort**: TBD based on requirements

---

## Task Sequencing & Dependencies (Updated 2026-02-13)

```text
✅ Phase 0 & 0A (Report Demo) - COMPLETE
   ├─ All 6 report handlers implemented
   ├─ Demo script refactored into three workflows
   ├─ All tests passing (1 demo test, 367 total tests)
   └─ Documentation complete via comprehensive docstring

--- CURRENT DECISION POINT ---

Option A: Expand Demos (Case/Embargo Workflows)
  Phase 0B (Case Management Demo)
    ├─ Implement case handlers (3-4 days)
    ├─ Implement invitation handlers (1-2 days)
    └─ Create demo script (1 day)
  
  Phase 0C (Embargo Management Demo)
    ├─ Implement embargo handlers (3-4 days)
    ├─ Implement embargo invitation handlers (1-2 days)
    └─ Create demo script (1 day)

Option B: Production Hardening (Deferred per PRIORITIES.md)
  Phase 1 (Infrastructure) - DEFERRED
    ├─ 1.1 Request Validation (1-2 days)
    ├─ 1.2 Error Responses (1-2 days) [depends on 1.1 for validation errors]
    └─ 1.3 Health Checks (0.5 days) [independent]
  
  Phase 2 (Observability) - DEFERRED
    ├─ 2.1 Structured Logging (2-3 days) [depends on 1.2 for error logging]
    └─ 2.2 Idempotency (1-2 days) [depends on 2.1 for logging]
  
  Phase 3 (Testing) - DEFERRED
    ├─ 3.1 Coverage Config (0.5 days) [independent]
    ├─ 3.2 Integration Tests (3-4 days) [depends on 1.1, 1.2, 2.1, 2.2]
    └─ 3.3 Test Infrastructure (2-3 days) [depends on 3.2]
  
  Phase 4 (Remaining Handlers) - DEFERRED
    ├─ 4.1-4.6 Handler Business Logic (10-15 days) [depends on 1.1 for validation]
    └─ Can be done incrementally, grouped by semantic category
  
  Phase 5 (Responses) - DEFERRED
    └─ Response Generation (5-7 days) [depends on 4.1-4.6]
  
  Phase 6 (Quality) - DEFERRED
    ├─ 6.1 Code Style (1-2 days) [independent, can run anytime]
    └─ 6.2 Documentation (2-3 days) [depends on all phases for accuracy]
```

**Effort Estimates** (for planning purposes only):

- Option A (Demo Expansion): 10-14 days (case + embargo demos)
- Option B (Production Hardening): 30-46 days (phases 1-6)

**Critical Path**: Phase 0 & 0A complete. Next direction depends on project goals (more demos vs production readiness).

---
