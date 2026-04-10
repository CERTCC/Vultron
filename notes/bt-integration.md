# Behavior Tree Integration Design Notes

## Architecture Overview

Use-case functions in `vultron/core/use_cases/` orchestrate complex workflows
using the `py_trees` behavior tree library via the bridge layer in
`vultron/core/behaviors/`. All protocol-significant behaviors MUST be
implemented as BT nodes or subtrees. See
`specs/behavior-tree-integration.md` BT-06-001.

**Key boundary**: `vultron/bt/` is the simulation BT engine (custom, do NOT
modify or reuse for prototype handlers). `vultron/core/behaviors/` uses
`py_trees` for prototype handler BTs. These coexist independently and MUST
NOT be merged.

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

## All Protocol-Significant Behavior MUST Be in the BT

**There is no "simple enough to skip" threshold for BT usage.**

All protocol-observable actions and state transitions MUST be implemented as
BT nodes or subtrees. This includes:

- Emitting ActivityStreams activities
- Transitioning RM/EM/CS state
- Creating or updating domain objects that represent protocol state
- Cascading to downstream behaviors (e.g., validate → engage/defer)

The BT is the domain documentation. If a behavior is not in the tree, it is
invisible to analysis, audit, and explainability tools. See BT-06-001,
BT-06-005, BT-06-006 in `specs/behavior-tree-integration.md`.

### Post-BT Procedural Cascade Anti-Pattern

```python
# ❌ WRONG — cascade hidden outside the tree
def execute(self) -> None:
    bridge.execute_with_setup(self._dl, bt, bb)
    if bt.status == Status.SUCCESS:
        SvcEngageCaseUseCase(self._dl, engage_event).execute()  # ← VIOLATION
```

The validate→engage cascade is invisible at the BT level. This pattern exists
in three places and is tracked as D5-7-BTFIX-1 and D5-7-BTFIX-2.

```python
# ✅ CORRECT — cascade expressed as a child subtree
class ValidateReportBt:
    def __init__(...):
        bt = py_trees.composites.Sequence(...)
        validate_node = ValidateReportNode(...)
        prioritize_subtree = PrioritizeBt(...)  # engage OR defer
        bt.add_children([validate_node, prioritize_subtree])
```

The cascade from the canonical `?_RMValidateBt → ?_RMPrioritizeBt` is now
visible in the BT structure and auditable from the tree alone.

### Procedural Glue Exception

The `execute()` method MAY contain infrastructure glue only:

- Instantiate the BT
- Set up the blackboard from the event (load actor/case IDs)
- Call `bridge.execute_with_setup()`
- Check BT status
- Extract output from the blackboard

Nothing domain-significant lives outside the tree.

### Historical Decision Table (Retired)

The "When to Use BTs vs. Procedural Code" table that previously appeared in
this section has been removed. It created a false "simple enough to skip"
threshold that led directly to the anti-pattern violations above.

For the mapping of canonical BT subtrees to current use cases, see
`notes/canonical-bt-reference.md`.

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

**A word about Fuzzer nodes**: Fuzzer nodes in the simulation
represent
non-deterministic decisions where the system might need to check some
external condition, ask a human for input, or perform some complex task
before proceeding. In the simulation, they would just randomly return
SUCCESS or FAILURE based on a stochastic model. In the prototype, we will
need to keep track of these nodes as places where further specification may
be needed or additional implementation work may be required to handle the
real-world logic that these nodes represent. See `bt-fuzzer-nodes.md`
for more discussion on this topic.

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

`EvaluateCasePriority` (in `vultron/core/behaviors/report/nodes.py`) is a
**stub node for the outgoing direction** — when the local actor decides whether
to engage or defer a case after receiving a validated report.

The receive-side trees (`EngageCaseBT`, `DeferCaseBT` in
`vultron/core/behaviors/report/prioritize_tree.py`) do **not** use
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

Per ADR-0015, a `VulnerabilityCase` is created at report receipt
(RM.RECEIVED). `VultronParticipant` records are created at that time:
reporter at RM.ACCEPTED, receiver at RM.RECEIVED. RM state is tracked
in `VultronParticipant.participant_status[].rm_state` from the moment
of case creation.

`ReportStatus` in the flat status layer is a **transient pre-case
mechanism** that was previously used for reports not yet associated with
a case (pre-case RM states: RECEIVED, INVALID). Under ADR-0015, the case
is created at receipt, so `VultronParticipant` records carry RM state
from the start. `ReportStatus` is retained for backwards compatibility but
is no longer the primary RM state carrier.

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

## Composability of Behavior Trees

Behavior trees can be composed by adding one tree's root node as the child
of a node in another tree. In this way, the Vultron Behavior Trees represent
a library of reusable mini-workflows that can be composed into larger workflows.
This allows us to build complex behavior logic while keeping individual trees focused
and maintainable. In fact, the entire behavior logic described in
`docs/topics/behavior_logic` is really one big behavior tree with all the
sub-nodes described separately for clarity. In the real implementation, we
want these behaviors to be more individually triggerable and composable, but
we may still want to be able to trigger an individual behavior tree as well
as another item that contains it for a larger workflow.

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

---

## Related

- `notes/canonical-bt-reference.md` — canonical subtree map, trunk-removed
  branches model, anti-pattern examples
- `specs/behavior-tree-integration.md` — formal BT requirements
  (BT-06-001 through BT-06-006 especially)
- `notes/bt-fuzzer-nodes.md` — fuzzer node catalog and replacement patterns
- `notes/use-case-behavior-trees.md` — use-case/BT conceptual layering
- `notes/protocol-event-cascades.md` — cascade gaps and BT subtree fixes
- `vultron-bt.txt` — full canonical CVD protocol BT dump (read-only reference)
