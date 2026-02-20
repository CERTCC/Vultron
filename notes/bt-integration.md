# Behavior Tree Integration Design Notes

## Architecture Overview

Handler functions in `vultron/api/v2/backend/handlers.py` MAY orchestrate
complex workflows using the `py_trees` behavior tree library via the bridge
layer in `vultron/behaviors/`. Simple CRUD-style handlers use procedural code
directly.

**Key boundary**: `vultron/bt/` is the simulation BT engine (custom, do NOT
modify or reuse for prototype handlers). `vultron/behaviors/` uses `py_trees`
for prototype handler BTs. These coexist independently and MUST NOT be merged.

---

## Key Design Decisions

### 1. py_trees for Prototype (Not Custom BT Engine)

Use `py_trees` (v2.2.0+) for prototype handler BTs. The existing
`vultron/bt/` simulation code uses a custom BT engine and MUST remain
unchanged.

**Rationale**: py_trees is mature, well-tested, provides visualization and
debugging tools, and allows focus on workflow logic rather than BT engine
maintenance. See ADR-0008.

### 2. Handler-Orchestrated BT (Handler-First)

Handlers orchestrate BT execution — handlers call BTs, BTs do not replace
the handler architecture.

**Rationale**: Preserves semantic extraction and dispatch infrastructure.
Allows gradual handler-by-handler migration. Keeps ActivityStreams as the API
surface (BT is an internal implementation detail). Aligns with ADR-0007.

**Rejected alternative**: BTs directly consuming ActivityStreams — would
require rewriting semantic extraction and tighter coupling.

### 3. DataLayer as State Store (No Separate Blackboard Persistence)

BTs interact directly with DataLayer for all persistent state. The py_trees
blackboard MAY be used for transient in-execution state only.

**Rationale**: Single source of truth, eliminates sync issues, simplifies
architecture, transaction semantics handled by DataLayer.

**Blackboard key naming**: Keys MUST NOT contain slashes (py_trees
hierarchical path parsing issues). Use `{noun}_{id_segment}` where
`id_segment` is the last path segment of the object's URI.
Examples: `object_abc123`, `case_def456`, `actor_vendorco`.

**Rejected alternative**: Separate blackboard with periodic sync — risk of
inconsistencies, complex sync logic.

### 4. Focused BTs per Workflow (Not Monolithic)

Create small, focused behavior trees triggered by specific message semantics.
Each `MessageSemantics` type that uses BT has a corresponding tree
encapsulating that workflow.

**Rationale**: Event-driven model (one message → one tree), easier to test
in isolation, clear handler entry points, composable via subtrees, better
performance.

**Rejected alternative**: Single monolithic `CvdProtocolBT` — doesn't match
event-driven handler architecture, harder to test, poor performance.

### 5. Single-Shot Execution (Not Persistent Tick Loop)

BTs execute to completion per handler invocation. No state is preserved
between handler invocations.

**Rationale**: Matches HTTP request/response model, simpler failure handling,
clear transaction boundaries (one execution = one commit).

**Rejected alternative**: Async tick-based execution with pause/resume —
requires BT state persistence between ticks, complex failure recovery.

### 6. Case Creation Includes CaseActor Generation

VulnerabilityCase creation triggers CaseActor (ActivityStreams Service)
creation as part of the same workflow.

**Rationale**: Case needs a message-processing owner. CaseActor models
case-as-agent, enables multi-case coordination, clear responsibility
boundary. One CaseActor per VulnerabilityCase (1:1 relationship).

**Case ownership model**:

- **Case Owner**: Organizational Actor (vendor/coordinator) responsible for
  decisions.
- **CaseActor**: ActivityStreams Service managing case state (NOT the case
  owner).
- **Initial Owner**: Typically the recipient of the VulnerabilityReport Offer.

### 7. CLI Invocation Support (MAY)

BTs can be invoked independently via CLI for testing and AI agent
integration. See `BT-08-*` in `specs/behavior-tree-integration.md`.

---

## Actor Isolation and BT Domains

Each actor has an isolated BT execution domain with no shared blackboard
access:

- Actor A and Actor B have separate py_trees blackboards.
- Cross-actor interaction happens ONLY through ActivityStreams messages
  (inboxes/outboxes).
- This models real-world CVD: independent organizations making autonomous
  decisions.
- Each actor's internal state (RM/EM/CS state machines) is private.

---

## Concurrency Model

**Prototype approach**: Sequential FIFO message processing.

**Rationale**: Eliminates race conditions without complexity. Single-threaded
execution of the inbox queue is sufficient for prototype validation.

**Implementation**: BackgroundTasks queues messages; inbox endpoint returns
202 immediately. BT execution happens in the background, sequentially.

**Future optimization paths** (defer until needed):

- Optimistic locking (version numbers on VulnerabilityCase)
- Resource-level locking (lock specific case during mutations)
- Actor-level concurrency (parallel across actors, sequential per-actor)

---

## When to Use BTs vs. Procedural Code

**Use BTs** (complex orchestration):

- Multiple conditional branches in the workflow
- State machine transitions (RM/EM/CS) with preconditions
- Policy injection needed (e.g., pluggable validation rules)
- Workflow composition (reuse subtrees across handlers)
- Reference implementations for CVD protocol documentation alignment

**Use procedural code** (simple workflows):

- Simple CRUD operations (`ack_report`, `create_report`, `submit_report`)
- Linear workflows with 3–5 steps and no branching
- Single database read/write operations
- Logging-only or passthrough operations

**Decision table for report and case handlers**:

| Handler                     | BT Value  | Rationale                                                                |
|-----------------------------|-----------|--------------------------------------------------------------------------|
| `validate_report`           | ✅ HIGH   | ✅ DONE — complex branching, policy injection, case creation subtree      |
| `engage_case`               | ✅ HIGH   | ✅ DONE — participant RM state, policy evaluation, state transitions      |
| `defer_case`                | ✅ HIGH   | ✅ DONE — participant RM state, policy evaluation, state transitions      |
| `create_case`               | ✅ HIGH   | ✅ DONE — idempotency check, validate, persist, CaseActor creation        |
| `close_report`              | ⚠️ MEDIUM | Has procedural logic; multi-step with preconditions; BT adds clarity    |
| `invalidate_report`         | ⚠️ MEDIUM | Has procedural logic; relatively short but state-machine-tied           |
| `create_report`             | ❌ LOW    | Simple CRUD; no branching; keep procedural                              |
| `submit_report`             | ❌ LOW    | Offer/status update; simple; keep procedural                            |
| `ack_report`                | ❌ LOW    | Single status transition; no branching; keep procedural                 |
| `add_report_to_case`        | ❌ LOW    | Simple append with idempotency; keep procedural                         |
| `close_case`                | ❌ LOW    | Leave + activity emit; simple; keep procedural                          |
| `create_case_participant`   | ❌ LOW    | Simple CRUD with idempotency; keep procedural                           |
| `add_case_participant_to_case` | ❌ LOW | Simple append with idempotency; keep procedural                         |

---

## Simulation-to-Prototype Translation Strategy

Use simulation trees in `vultron/bt/` as **architectural reference** (not
code reuse targets). The simulation uses a custom BT engine with incompatible
initialization patterns.

**Translation steps**:

1. Find the corresponding simulation tree in
   `vultron/bt/report_management/_behaviors/` (or embargo/case equivalents).
2. Note the sequence/fallback composition hierarchy and node ordering.
3. Map condition nodes (e.g., `RMinStateValid`) to py_trees `Behaviour`
   subclasses checking DataLayer state.
4. Replace fuzzer nodes (e.g., `EvaluateReportCredibility`) with
   deterministic policy nodes using configurable defaults.
5. Preserve state transition order and precondition checks.
6. Wrap state changes with DataLayer update operations.
7. Generate ActivityStreams activities for outbox where simulation emits
   messages.

**Fuzzer node replacement pattern**: Create a policy class with a clear
interface (e.g., `ValidationPolicy.is_credible(report) -> bool`) and a
default `AlwaysAcceptPolicy` implementation. This provides a deterministic
stub with an explicit extension point.

**Source of truth priority** when conflicts arise:

1. **Primary**: `docs/howto/activitypub/activities/*.md` — process
   descriptions, message examples, workflow steps.
2. **Secondary**: `vultron/bt/report_management/_behaviors/*.py` — state
   machine logic, tree composition.
3. **Tertiary**: `docs/topics/behavior_logic/*.md` — conceptual diagrams,
   motivation.

**Simulation tree to handler mapping**:

| Handler             | Simulation Reference                              | Status                |
|---------------------|---------------------------------------------------|-----------------------|
| `validate_report`   | `_behaviors/validate_report.py:RMValidateBt`      | ✅ DONE               |
| `engage_case`       | `_behaviors/prioritize_report.py:RMPrioritizeBt`  | ✅ DONE               |
| `defer_case`        | `_behaviors/prioritize_report.py:RMPrioritizeBt`  | ✅ DONE               |
| `create_case`       | `case_state/conditions.py`, `transitions.py`      | ✅ DONE               |
| `invalidate_report` | `_behaviors/validate_report.py:_InvalidateReport` | ⚠️ Optional refactor  |
| `close_report`      | `_behaviors/close_report.py:RMCloseBt`            | ⚠️ Optional refactor  |

---

## Case and Embargo BT Structure Notes

**Case management** (`vultron/bt/case_state/`): Contains `conditions.py` and
`transitions.py` but no `_behaviors/` subdirectory (unlike report
management). Implement BT nodes directly from the ActivityPub how-to docs,
using `conditions.py` and `transitions.py` as state machine logic reference.

**Embargo management** (`vultron/bt/embargo_management/`): Contains
`behaviors.py`, `conditions.py`, `states.py`, `transitions.py`. The embargo
state machine (EM: NO_EMBARGO → PROPOSED → ACTIVE → REVISE → EXITED) maps
directly to the handler sequence for the establish_embargo workflow. Note:
`Accept` is an **activity type** that triggers `PROPOSED → ACTIVE` (or
`REVISE → ACTIVE`) — it is not a state. See
`vultron/bt/embargo_management/states.py` for the authoritative state list.

---

## Demo Script Architecture Pattern

Each demo script should follow `receive_report_demo.py` as the reference
pattern:

1. `setup_*()` — create preconditions (actors, prior state)
2. `demo_*(server_url)` — execute the workflow via HTTP inbox POSTs
3. `show_state(dl)` — display relevant DataLayer state after workflow
4. `main()` — orchestrate with logging, call setup then demos

Use `httpx` or `requests` against a live FastAPI test server (via
`TestClient` for in-process testing, or a running server for integration
tests).

---

## EvaluateCasePriority: Outgoing Direction Only

`EvaluateCasePriority` (in `vultron/behaviors/report/nodes.py`) is a **stub
node for the outgoing direction** — when the local actor decides whether to
engage or defer a case after receiving a validated report.

The receive-side trees (`EngageCaseBT`, `DeferCaseBT` in
`vultron/behaviors/report/prioritize_tree.py`) do **not** use
`EvaluateCasePriority`. They only record the **sender's already-made
decision** by updating the sender's `CaseParticipant.participant_status[].rm_state`.

This distinction matters because Activities are state-change notifications, not
commands: when the local actor receives `Join(VulnerabilityCase)` (ENGAGE_CASE)
or `Ignore(VulnerabilityCase)` (DEFER_CASE), it is being informed that another
participant already made their decision — the receiver simply records that fact.
Policy evaluation is only needed when the **local actor** decides to engage or
defer.

---

## RM State Machine: Participant-Specific Context

RM is a **participant-specific** state machine — each `CaseParticipant`
carries its own RM state in `participant_status[].rm_state`, independently
of other participants.

`ReportStatus` in the flat status layer is a **separate mechanism** used
only for reports not yet associated with a case (pre-case RM states:
RECEIVED, INVALID). Once a case is created from a validated report, RM state
is tracked in `CaseParticipant.participant_status[].rm_state`.

This distinction affects how `engage_case` / `defer_case` handlers work:
they update participant-level RM state, not flat report status.

---

## Performance Baseline

Phase BT-1 measurements (100 runs of `validate_report` BT):

- P50 = 0.44ms, P95 = 0.69ms, P99 = 0.84ms

This is well within the 100ms target. If more complex trees degrade
performance, consider caching BT structure (instantiate once, reuse with
fresh blackboard) and batching DataLayer operations. Measure before
optimizing.

---

## Open Architecture Questions

**Multi-actor state synchronization**: Each actor's BT loads only that
actor's DataLayer state. Cross-actor coordination happens via message
exchange. Whether to add optimistic locking for multi-actor scenarios should
be decided based on observed issues during testing.

**Message emission and outbox processing**: BT nodes generate activities and
write to actor outbox via DataLayer. Whether outbox delivery should be
triggered synchronously after BT execution or asynchronously remains to be
decided.

**Human-in-the-loop decision handling**: Report validation, embargo
acceptance, and similar steps require human judgment. The prototype uses
configurable default policies (always-accept stubs with audit logging). Async
workflow support with pause/resume is a future consideration.
