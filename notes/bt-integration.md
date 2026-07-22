---
title: Behavior Tree Integration Design Notes
status: active
tags: [bt, behavior-trees, py_trees, blackboard, BT-nodes, protocol-cascades]
description: >
  BT design decisions, py_trees patterns, simulation-to-prototype translation
  strategy, subtree map, and anti-patterns to avoid.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes.md
  - notes/protocol-event-cascades.md
  - notes/use-case-behavior-trees.md
relevant_packages:
  - py_trees
  - vultron/bt
  - vultron/core/behaviors
  - vultron/core/use_cases
---

# Behavior Tree Integration Design Notes

## Architecture Overview

Use-case functions in `vultron/core/use_cases/` orchestrate complex workflows
using the `py_trees` behavior tree library via the bridge layer in
`vultron/core/behaviors/`. All protocol-significant behaviors MUST be
implemented as BT nodes or subtrees. See
`specs/behavior-tree-integration.yaml` BT-06-001.

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
integration. See `BT-08-*` in `specs/behavior-tree-integration.yaml`.

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

**Prototype approach**: Sequential FIFO message processing per actor.

**Implementation**: BackgroundTasks queues messages; inbox endpoint returns
202 immediately. BT execution happens in the background via
`anyio.to_thread.run_sync`, which places synchronous callables onto a
**thread pool** — not a single thread.

**Critical implication**: Two BT executions can and do run on different
threads simultaneously. The `py_trees.blackboard.Blackboard.storage` dict
is process-global and is **not** thread-safe without explicit locking.

**Fix**: `BTBridge.execute_with_setup` wraps its entire
setup → execute → cleanup critical section with a module-level
`threading.RLock`. An `RLock` (not `Lock`) is required because
`lifecycle.py` BT nodes call `execute_with_setup` recursively — a plain
`Lock` deadlocks in that path.

**Race condition that prompted this fix** (PR-886): Thread A's
`execute_with_setup` writes `actor_id=A` and `datalayer=DL_A`; Thread B
overwrites them with `actor_id=B` / `datalayer=DL_B`; Thread A then reads
the wrong `actor_id`, queuing its outbound activity under the wrong actor's
outbox — the activity is silently lost. Thread B may also crash when
Thread A's cleanup removes `/datalayer` before B reads it.

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
BT-06-005, BT-06-006 in `specs/behavior-tree-integration.yaml`.

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

### Trigger/Received Parity

The BTBridge requirement applies equally to **trigger-side** and
**received-side** `execute()` methods. There is no carve-out for trigger
use cases.

State machine transitions — RM transitions (e.g., `RM.INVALID`, `RM.CLOSED`),
EM lifecycle calls (e.g., `EmbargoLifecycle.propose_embargo()`), direct
`ParticipantStatus` writes with a specific `rm_state` — are all
protocol-significant behavior (BT-15-001, BT-06-006). They MUST live in BT
leaf nodes executed via `bridge.execute_with_setup()`, not directly in
`execute()`.

```python
# ❌ WRONG — trigger-side inline RM state transition
def execute(self) -> dict:
    set_status = ParticipantStatus(rm_state=RM.INVALID, ...)
    _idempotent_create(dl, ..., set_status, ...)
    add_activity_to_outbox(actor_id, activity_id, dl)
    return {"activity": activity_dict}
```

```python
# ✅ CORRECT — trigger-side SM transition in BTBridge
def execute(self) -> dict:
    bridge = BTBridge(datalayer=dl, trigger_activity=factory)
    tree = invalidate_report_trigger_bt(...)
    result = bridge.execute_with_setup(tree, actor_id=actor_id)
    if result.status != Status.SUCCESS:
        raise VultronValidationError(
            f"InvalidateReport failed: {BTBridge.get_failure_reason(tree)}"
        )
    return {"activity": captured.get("activity")}
```

The historical asymmetry — where `received/` use cases used BTBridge and
`triggers/` did not — arose from the now-retired "simple CRUD" guidance.
See BT-15-001 in `specs/behavior-tree-integration.yaml`.

### Historical Decision Table (Retired)

The "When to Use BTs vs. Procedural Code" table that previously appeared in
this section has been removed. It created a false "simple enough to skip"
threshold that led directly to the anti-pattern violations above.

For the mapping of canonical BT subtrees to current use cases, see
the "Canonical CVD Protocol Behavior Tree Reference" section of this file.

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

### py_trees Fuzzer Node Home: `vultron/demo/fuzzer/`

When re-implementing the `vultron/bt/` fuzzer nodes using `py_trees`,
the correct target location is **`vultron/demo/fuzzer/`** — NOT
`vultron/core/behaviors/`.

**Why demo, not core?** Fuzzer nodes are simulation/demo stubs standing
in for real external-dependency touchpoints (system integrations, human
decisions, environmental checks). They are not production protocol
behaviors and MUST NOT pollute `vultron/core/behaviors/`.

**Module layout** (see BT-16-004):

| Module | Source | Nodes |
|---|---|---|
| `vultron/demo/fuzzer/base.py` | `vultron/bt/base/fuzzer.py` | Probabilistic base types |
| `vultron/demo/fuzzer/embargo.py` | `vultron/bt/embargo_management/fuzzer.py` | ~15 embargo nodes |
| `vultron/demo/fuzzer/messaging.py` | `vultron/bt/messaging/inbound/_behaviors/fuzzer.py` | ~1 messaging node |
| `vultron/demo/fuzzer/report_management/` | `vultron/bt/report_management/fuzzer/` | ~70 nodes in submodules |

**Note**: `vultron/bt/vul_discovery/fuzzer.py` is intentionally excluded —
the `DiscoverVulnerabilityBt` tree operates upstream of real Vultron
(which starts at `Offer(VulnerabilityReport)`). There is no corresponding
real workflow in `vultron/core/` to target.

Each fuzzer node MUST include a docstring identifying:

1. Its semantic function in the CVD process
2. The category of external input it simulates:
   - **System integration** — automatable via API calls, metadata queries,
     or policy-rule evaluation
   - **Human decision** — requires analyst judgment or policy oversight
   - **Environmental check** — real-world state observable automatically
3. Its approximate success probability (maps to `WeightedBehavior` subclass)
4. Its automation potential (High / Medium / Low / N/A) per BT-16-005

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

- `notes/bt-integration.md` — canonical subtree map, trunk-removed
  branches model, anti-pattern examples (merged from former
  `canonical-bt-reference.md`)
- `specs/behavior-tree-integration.yaml` — formal BT requirements
  (BT-06-001 through BT-06-006 especially)
- `notes/bt-fuzzer-nodes.md` — fuzzer node catalog and replacement patterns
- `notes/use-case-behavior-trees.md` — use-case/BT conceptual layering
- `notes/protocol-event-cascades.md` — cascade gaps and BT subtree fixes
- `notes/vultron-bt.txt` — full canonical CVD protocol BT dump (read-only
  reference)

---

## Canonical CVD Protocol Behavior Tree Reference

This section documents the **canonical CVD Protocol Behavior Tree** — the
authoritative definition of what Vultron does at the domain level. It
captures the "trunk-removed branches" mental model, provides an annotated
structural overview, maps canonical subtrees to current use cases, and
gives implementation guidance for locating new behaviors before coding them.

**Source**: `vultron-bt.txt` (full tree dump from the simulation engine),
`docs/topics/behavior_logic/` (narrative documentation per subtree),
`vultron/bt/` (simulation implementation, do NOT modify).

### The Trunk-Removed Branches Model

The Vultron simulation runs one large `CvdProtocolRoot` tree continuously,
ticking through all branches on every cycle. The prototype cannot do this
— it is event-driven, receiving one ActivityStreams message at a time.

The solution: **remove the trunk, keep the branches**.

Each use case in `vultron/core/use_cases/` corresponds to a named subtree
in the canonical BT. When an external event (HTTP message, trigger API call)
arrives, the dispatcher activates the matching subtree as a py_trees BT.
The branch executes to completion, exactly as it would if the full tree had
ticked down to it.

```text
Canonical tree:          Prototype:
CvdProtocolRoot          (trunk removed)
  ├─ ReceiveMessages ──►  CreateReportReceivedUseCase → __HandleRs_51 subtree
  │    └─ HandleRS  ──►   ValidateReportUseCase       → RMValidateBt_416 subtree
  │    └─ HandleEP  ──►   ProposeEmbargoReceivedUseCase → __HandleEp_135 subtree
  └─ ReportMgmtBt ──►    SvcEngageCaseUseCase         → RMPrioritizeBt_505 subtree
       └─ RmValid        SvcDeferCaseUseCase           → RMPrioritizeBt_505 subtree
            └─ Prioritize
```

**Why this matters**: When adding a cascade (A triggers B), check the
canonical tree. If B is a *child* of A in the canonical tree, B must be a
BT subtree within A's use-case BT — not a procedural call after `bt.run()`
returns. The tree structure IS the documentation. Anything outside the tree
is invisible to analysis and audit.

### Node Symbol Legend

The canonical BT uses prefix symbols to identify node types:

| Symbol | Node type | py_trees equivalent |
|--------|-----------|---------------------|
| `+--`  | Root sequence | `py_trees.composites.Sequence` |
| `>`    | Sequence (all children must succeed) | `py_trees.composites.Sequence` |
| `?`    | Selector (first success wins) | `py_trees.composites.Selector` |
| `l`    | While/loop | custom repeat decorator |
| `^`    | Inverter | `py_trees.decorators.Inverter` |
| `!`    | Action (emit message) | action leaf node |
| `a`    | Action (state transition) | action leaf node |
| `c`    | Condition check | condition leaf node |
| `z`    | Fuzzer node (human/external input stub) | replaced by real integration |
| `L->`  | Last child of parent | (same types as above) |

### Top-Level Structure

```text
CvdProtocolRoot (Sequence)
├─ Snapshot                     # capture current state
├─ DiscoverVulnerabilityBt      # finder role: find/receive vuln
├─ ReceiveMessagesBt            # process inbound message queue
├─ ReportManagementBt           # RM state machine (non-message-driven)
├─ EmbargoManagementBt          # EM state machine (non-message-driven)
└─ CaseStateBt                  # CS state machine (non-message-driven)
```

The prototype maps these five branches to use cases. The first three
(Snapshot, DiscoverVuln, ReceiveMessages) are reactive; the last two plus
ReportManagementBt are autonomous/trigger behaviors.

### Subtree Map: Canonical BT → Use Cases

#### Message Receipt: ReceiveMessagesBt (lines 26–410 in vultron-bt.txt)

The canonical tree dispatches on message type inside
`?__HandleMessage_36`. Each message type handler is a subtree:

| Canonical subtree | Message type | Current use case |
|---|---|---|
| `>__HandleRs_51` | RS (Report Submit) | `SubmitReportReceivedUseCase` |
| `>_ProcessRMMessagesBt_37` + `>__HandleRs_51` | RS inbound | `SubmitReportReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEp_135` | EP (Embargo Propose) | `ProposeEmbargoReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEr_113` | ER (Embargo Revise) | `ReviseEmbargoReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEa_148` | EA (Embargo Accept) | `AcceptEmbargoReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEt_98` | ET (Embargo Terminate) | `TerminateEmbargoReceivedUseCase` |
| `>_ProcessCSMessagesBt_277` | CV/CF/CD/CP/CX messages | CS-state use cases |

#### Report Management State Machine: ReportManagementBt (lines 411–940)

The RM state machine drives autonomous behavior once a report is received.
Sub-trees by RM state:

| Canonical subtree | RM state trigger | Current use case |
|---|---|---|
| `>_RmReceived_414` + `?_RMValidateBt_416` | RM=RECEIVED → validate | `SvcValidateReportUseCase` / `ValidateCaseUseCase` |
| `>__ValidationSequence_425` → `>__ValidateReport_431` | validate → RM.VALID | validate BT (validate_tree.py) |
| `>__InvalidateReport_440` | validate → RM.INVALID | validate BT failure path |
| `>_RmValid_503` + `?_RMPrioritizeBt_505` | RM=VALID → prioritize | `SvcEngageCaseUseCase` / `SvcDeferCaseUseCase` |
| `>__TransitionToRmAccepted_524` | prioritize → RM.ACCEPTED | `SvcEngageCaseUseCase` (engage BT) |
| `>__TransitionToRmDeferred_536` | prioritize → RM.DEFERRED | `SvcDeferCaseUseCase` (defer BT) |
| `?_RMCloseBt_451/549/613` + `>__ReportClosureSequence_453` | RM=VALID/DEFERRED/ACCEPTED → close | `SvcCloseReportUseCase` |

**Critical**: In the canonical tree, `?_RMValidateBt_416` and
`?_RMPrioritizeBt_505` are parent→child. The validate subtree runs, then
the prioritize subtree runs as the next step in the same RM sequence. This
means **the validate→prioritize (engage/defer) cascade MUST be expressed as
a BT subtree**, not as a procedural call after validation succeeds.

#### Embargo Management State Machine: EmbargoManagementBt (lines 940+)

| Canonical subtree | Trigger | Current use case |
|---|---|---|
| `?_EMProposeBt` | EM=NONE → propose | `SvcProposeEmbargoUseCase` |
| `?_EMEvalBt` | EM=PROPOSED → evaluate | embargo evaluation BT |
| `?_EMRevise` | EM=ACTIVE → revise | `SvcReviseEmbargoUseCase` |
| `?_EMTerminateBt` | EM=ACTIVE → terminate | `SvcTerminateEmbargoUseCase` |

### The Prioritize Subtree in Detail

The validate → engage/defer cascade is one of the most commonly
misimplemented patterns. The canonical structure is:

```text
?_RMPrioritizeBt_505 (Selector)
├─ >__ConsiderGatheringMorePrioritizationInfo_506
│    └─ skip if already DEFERRED or ACCEPTED
├─ >__DecideIfFurtherActionNeeded_515 (Sequence)
│    ├─ check RM in VALID/DEFERRED/ACCEPTED
│    ├─ a_EvaluatePriority_520          ← fuzzer: SSVC or other evaluator
│    ├─ c_PriorityNotDefer_521          ← condition: should we engage?
│    └─ ?__EnsureRmAccepted_522
│         └─ >__TransitionToRmAccepted_524
│              ├─ OnAccept_525
│              ├─ transition RM → ACCEPTED
│              └─ !_Emit_RA_533         ← emit RA message
└─ ?__EnsureRmDeferred_534
     └─ >__TransitionToRmDeferred_536
          ├─ OnDefer_537
          ├─ transition RM → DEFERRED
          └─ !_Emit_RD_545              ← emit RD message
```

`a_EvaluatePriority_520` is a fuzzer node — a stub for real-world
prioritization logic. In the prototype this becomes the
**priority-check node** described in IDEA-26041004: a node that returns
SUCCESS (engage), FAILURE (defer), or RUNNING (evaluation pending). The
default implementation returns SUCCESS to preserve current demo behavior.

This subtree MUST be a child of the validate BT (or its parent), not a
procedural function called after `bt.run()` returns.

### How to Locate a New Behavior in the Canonical Tree

When implementing a new cascade, state transition, or downstream behavior:

1. **Find the canonical subtree path** in `vultron-bt.txt`. Use the node
   names (e.g., `?_RMPrioritizeBt_505`) to locate the right section.
2. **Check whether it is a child of the triggering subtree** in the
   canonical tree. If yes → it MUST be a BT subtree, not procedural code.
3. **Identify any fuzzer nodes** (`z_` prefix) in the path. These are
   integration points where real logic (human, AI, external system) must
   replace the stub. In the prototype, implement as a leaf node that can
   be replaced without changing the tree structure.
4. **Implement as a shared subtree factory** (e.g.,
   `create_prioritize_subtree()`) so the same subtree can be instantiated
   anywhere the canonical tree reuses it.
5. **Document divergence**: if the prototype diverges from the canonical
   structure (e.g., skips a branch that requires human input), add a
   comment explaining why and file a tech debt item.

### Key Fuzzer Nodes: Future Integration Points

Fuzzer nodes in the canonical BT represent the planned extension points for
the Vultron system. Each one is a location where real-world logic will
eventually replace the simulation stub. See `notes/bt-fuzzer-nodes.md`
for the full inventory.

Highest-priority fuzzer nodes for the prototype:

| Node | Location | Real-world replacement |
|---|---|---|
| `a_EvaluatePriority_520` | RMPrioritizeBt | SSVC evaluator, policy engine, or simple default |
| `z_EvaluateReportCredibility_429` | RMValidateBt | Report credibility check (reporter trust, content check) |
| `z_EvaluateReportValidity_430` | RMValidateBt | Technical validity assessment |
| `z_EnoughPrioritizationInfo_511` | RMPrioritizeBt | Data sufficiency check before prioritization |

### Anti-Pattern Reference

#### DO NOT: post-BT procedural cascade

```python
# BAD — the engage/defer decision is invisible outside the BT
def execute(self) -> None:
    result = bridge.execute_with_setup(validate_tree, actor_id=...)
    if result.status == Status.SUCCESS:
        SvcEngageCaseUseCase(self._dl, ...).execute()  # ANTI-PATTERN
```

This pattern violates BT-06-006.

#### DO: cascade as BT subtree

```python
# GOOD — engage/defer is a child subtree of the validate tree
def create_validate_and_prioritize_tree(report_id, offer_id):
    validate_subtree = create_validate_report_subtree(report_id, offer_id)
    prioritize_subtree = create_prioritize_subtree(report_id)
    root = py_trees.composites.Sequence(
        name="ValidateAndPrioritize",
        memory=False,
        children=[validate_subtree, prioritize_subtree],
    )
    return root
```

The full behavior — validate then prioritize (engage or defer) — is visible
by reading the tree. No domain logic lives in `execute()`.

#### DO NOT: BT node calling a use case

(BT-IDM-01, 2026-06-03)

A BT node's `update()` method MUST NOT directly instantiate and call a use
case. Use cases are the handlers that *create* BTs, not work items *inside*
BTs. Calling a use case from inside a BT node creates a BT→UseCase→BT→UseCase
call chain that is impossible to audit or preempt.

```python
# BAD — BT node calling a use case (PublicDisclosureBranchNode anti-pattern)
class PublicDisclosureBranchNode(py_trees.behaviour.Behaviour):
    def update(self):
        # ...
        SvcTerminateEmbargoUseCase(self._dl, ...).execute()  # ANTI-PATTERN
        return Status.SUCCESS
```

Instead, compose the behavior as a child subtree of the calling BT. The
sub-behavior becomes a set of leaf nodes in a `Sequence` or `Selector` — not
a use case call embedded inside another node.

**Rule**: BT leaf nodes MUST NOT instantiate or call use-case classes.
If a node needs to trigger a multi-step workflow, that workflow MUST be
modeled as a child subtree of the current tree. See BT-06-001 and
BT-06-006.

---

#### DO NOT: BT node importing from use case modules

(BT-IDM-02, 2026-06-03)

BT nodes in `vultron/core/behaviors/` MUST NOT import private helpers or
functions from `vultron/core/use_cases/`. The dependency direction MUST be:

```text
use_cases/ → behaviors/ (use cases call BTs)
```

Not:

```text
behaviors/ → use_cases/ (BT nodes importing from use cases — WRONG)
```

**Why**: Importing a use-case helper into a BT node inverts the layer
boundary and creates circular dependency risk. If a helper is needed in
both a use case and a BT node, it MUST be extracted to a shared utility
module (e.g., `vultron/core/behaviors/shared/` or a domain-model method).

Example violation: `ApplyEmbargoTeardownNode` in
`vultron/core/behaviors/embargo/nodes.py` imported
`_reset_case_participant_embargo_consent` from
`vultron.core.use_cases.received.embargo`. Fix: move the helper to a
shared location importable by both layers.

---

#### DO NOT: God BT nodes with long `update()` methods

(BT-IDM-03, 2026-06-03)

A BT leaf node's `update()` method SHOULD NOT exceed ~20–30 lines of
logic. If a node's `update()` is 60–100+ lines, it is doing too much and
defeats the core purpose of BTs: simple, auditable, composable leaves with
the complexity visible in tree *structure*, not in individual nodes.

**Smell signals** that a node is a god node:

- More than 3–4 distinct responsibilities (read, validate, create,
  persist, broadcast, …)
- Multiple `dl.save()` calls in one `update()`
- Boolean constructor parameters (`advance_to_accepted=True`) that
  silently activate optional branches
- Internal `if/else` chains that should be separate `Sequence`/`Selector`
  child nodes

**Fix**: Decompose into a named subtree of simple leaf nodes, each with a
single responsibility. The subtree factory function becomes the visible
documentation of the workflow. See also `specs/behavior-tree-node-design.yaml`
BTND-02-001 and `notes/bt-design-patterns.md`.

---

### BT Failure Reason Propagation

(DR-12, 2026-04-20)

When a BT returns `Status.FAILURE`, log messages MUST include a human-readable
reason indicating *which* node failed and *why*. Add a `get_failure_reason()`
utility in `vultron/core/behaviors/bridge.py`:

```python
def get_failure_reason(tree) -> str:
    """Walk the tree depth-first; return the first FAILURE node's
    feedback_message (or class name if no message is set)."""
    for node in tree.root.iterate():
        if node.status == py_trees.common.Status.FAILURE:
            return node.feedback_message or type(node).__name__
    return "unknown failure"
```

Apply to all BT-failure log messages (e.g., `EngageCaseBT`, `ValidateReportBT`,
etc.):

```python
if bt.root.status == Status.FAILURE:
    reason = get_failure_reason(bt)
    logger.error("BT failed: %s (reason: %s)", bt.root.name, reason)
```

**Why this matters**: Without this utility, BT failures produce generic "BT
failed" log lines that require re-running the scenario to diagnose. The
`feedback_message` is set by failing nodes in py_trees and is the canonical
source of diagnostic information.

**Critical pitfall — `result.feedback_message` on the root is always empty**:
When a `py_trees` Sequence fails because a child node fails, the root
Sequence node's own `feedback_message` is always `""`. Logging
`result.feedback_message` or `bt.root.feedback_message` after a BT failure
therefore produces an empty string, not the diagnostic message set by the
failing child. Always use `BTBridge.get_failure_reason(tree)` (depth-first walk
to the first failing leaf) to get a meaningful message. Apply this pattern
**everywhere** `feedback_message` is logged after a BT failure — not just for
a single BT class.

---

### AttachNoteToCase Idempotency: Check Attachment, Not Existence

(DR-08, 2026-04-20)

`AttachNoteToCaseNode.update()` MUST check whether the note is already
**attached to the case** for idempotency — NOT whether the note object exists
in the DataLayer.

```python
# WRONG — note may exist in DataLayer without being attached to the case
if dl.read(note.id_) is not None:
    return Status.SUCCESS  # false idempotency

# CORRECT — check the case's note reference list
case = dl.read(case_id)
if note.id_ in case.notes:
    return Status.SUCCESS  # truly idempotent
case.notes.append(note.id_)
dl.save(case)
return Status.SUCCESS
```

**Why this matters**: The DataLayer stores notes as top-level objects
independently of their attachment to a case. A note can be created and
persisted without ever being added to `case.notes`. Checking `dl.read(note_id)
is not None` would falsely skip re-attachment if the note was stored by another
path but never linked.

---

### Closing Bugs with Concrete Evidence

(BUG-26041701 closure, 2026-04-22)

When a backlog bug may already be fixed by unrelated work, close it with
**concrete evidence** rather than forcing a redundant follow-up patch:

1. **Code search**: confirm that the triggering condition is no longer possible
   (e.g., search for the pattern that caused the original bug and verify it's
   gone).
2. **Regression test**: add or verify a test that would fail if the bug
   recurred.
3. **Document the fix points**: note which commits/layers addressed each aspect
   of the root cause.

**Anti-pattern**: Treating "I can't reproduce it" as sufficient closure — the
fix may be coincidental and fragile. Concrete evidence ensures it won't
silently regress.

### py_trees `blackboard.get()` Raises KeyError for Unwritten READ Keys

`Client.get(key)` does **not** return `None` when a key is registered for
`Access.READ` but has not yet been written to `Blackboard.storage`. It raises
`KeyError`. This has two consequences:

1. **Test nodes return wrong status** — if `update()` calls `get()` on an
   unwritten key, the `KeyError` propagates out of `update()`. If the node
   has a broad `except Exception` block, it catches the error and returns
   `FAILURE` — but if the `KeyError` propagates all the way to `execute_tree()`
   and the outer `except Exception` there returns `FAILURE`, a test expecting
   `SUCCESS` will correctly fail. However if the `KeyError` is caught somewhere
   that swallows it silently, status can be wrong.

2. **Silent node shadowing** — a more insidious variant occurred during
   development of `SendOfferCaseManagerRoleNode`: the class body of
   `EmitCreateCaseActivity` was accidentally embedded *inside*
   `SendOfferCaseManagerRoleNode` (as a duplicate `__init__`, `setup`, and
   `update()` defined later in the same class body). Python resolves to the
   *last* definition, so the correct `update()` was silently replaced by the
   embedded one. The embedded `setup()` only registered `case_id`, so
   `get("case_actor_id")` never raised — it was never even called. The node
   returned `SUCCESS` whenever `case_id` was present, masking the real logic
   entirely.

**Rules**:

- Use `Blackboard.storage.get("/key")` (with the leading `/` prefix that
  py_trees uses internally) only in tests to inspect raw storage — never in
  production node code.
- In production `update()`, use `self.blackboard.get(key)` knowing it will
  raise if the key is unset. Guard with an explicit `try/except KeyError` or
  ensure the key is always written before being read (i.e., the writing node
  precedes the reading node in the sequence).
- When a new node class is added to a file, **always verify class boundaries
  with `grep -n "^class " <file>`** before committing. Python silently accepts
  duplicate method definitions within a class; the last definition wins.

---

### BT Result Channel for Domain Errors

(ISSUE-711, 2026-06-09)

When strict state-machine transitions move into BT action nodes, use cases
still need the original domain exception types (e.g.,
`VultronInvalidStateTransitionError`) to preserve caller and test semantics.

**Pattern**: Write the error into `result_out["error"]` inside the BT node,
then let the use case's `execute()` re-raise it directly:

```python
# In BT node:
def update(self) -> Status:
    try:
        lifecycle.do_transition(...)
    except VultronInvalidStateTransitionError as e:
        self.blackboard.result_out = {"error": e}
        return Status.FAILURE
    return Status.SUCCESS

# In use case execute():
result = bridge.execute_with_setup(tree, ...)
if result.status == Status.FAILURE:
    err = (result_out or {}).get("error")
    if isinstance(err, VultronError):
        raise err
```

This avoids collapsing domain errors into generic BT failure messages and
lets tests assert on the original exception type.

---

### Lenient vs. Strict Participant Lookup Node Variants

(ISSUE-710, 2026-06-09)

Two distinct lookup patterns exist for resolving a participant from an
actor ID:

- **Strict** (`LookupParticipantNode`, fail-on-missing): Required for
  operations that must have a participant record (e.g., recording acceptance).
  Returns `FAILURE` when the participant is not found.
- **Lenient** (`OptionalLookupParticipantNode`, succeed-on-missing): Correct
  for operations where the participant may not exist on this peer yet (e.g.,
  processing an invite or reject). Returns `SUCCESS` even when the participant
  is absent, so the broadcast log entry can proceed.

**Why "Always SUCCESS" is intentional for the lenient variant**: When a
peer receives a log entry for a participant it has not yet seen, succeeding
allows the case ledger cascade to proceed. The state gap resolves when the
participant is later introduced via the normal invite/accept flow.

**Documentation rule**: The docstring for any lenient node MUST explicitly
state that it always returns `SUCCESS` and explain *why* this is correct for
its use case — so future reviewers understand it is a deliberate design
choice, not a missing failure check.

**Constructor parameter audit**: When migrating procedural logic to BT
nodes, verify that all constructor parameters are actually used inside the
node. An unused parameter (e.g., `actor_id_source`) creates confusion about
whether the parameter controls behavior — it suggests a future branching
path that may never be implemented.

**Actor ID handoff in invite trees**: When the invitee actor ID differs
from the sender actor ID, pass the *invitee* ID (not the sender) to
`bridge.execute_with_setup()` so participant-lookup nodes resolve the
correct participant record.

---

### Decomposed BT Leaf Must Return FAILURE for Missing Blackboard Keys

(ISSUE-752, 2026-06-09)

When a god node is decomposed into a sequence of leaf nodes, each leaf
that requires blackboard context MUST explicitly convert a missing-key read
into node `FAILURE` with a clear error message — not propagate the exception
up to the bridge level where it becomes an opaque failure.

```python
# BAD — exception escapes the node
def update(self) -> Status:
    case_id = self.blackboard.get("case_id")  # raises KeyError if unset

# GOOD — missing key → explicit FAILURE
def update(self) -> Status:
    try:
        case_id = self.blackboard.get("case_id")
    except KeyError:
        self.logger.error("case_id not set in blackboard")
        return Status.FAILURE
```

The caller sees a clean `FAILURE` status with a logged reason rather than
an unhandled exception that bypasses normal failure-path handling.

---

### BT-HELPER-01 — Helpers Raise; `update()` Catches

(ADR-0032, 2026-07-13)

BT node helper methods (private methods called from `update()`) MUST either
complete successfully or raise a domain exception (e.g.
`BtNodePreconditionError`). They MUST NOT return `None` as a failure signal.

`update()` is the single `try/except` handler:

```python
from vultron.errors import BtNodePreconditionError


def _read_case_obj(self, case_id: str) -> VulnerabilityCase:
    try:
        obj = self.blackboard[case_id]
    except KeyError:
        raise BtNodePreconditionError(f"case {case_id!r} not in blackboard")
    if not isinstance(obj, VulnerabilityCase):
        raise BtNodePreconditionError(
            f"blackboard entry {case_id!r} is not a VulnerabilityCase"
        )
    return obj

def update(self, ...) -> Status:
    try:
        case_obj = self._read_case_obj(case_id)
        ...
    except BtNodePreconditionError as e:
        self.feedback_message = str(e)
        return Status.FAILURE
```

This eliminates the class of bug where a helper returns `None` silently with
no `self.feedback_message` set (see
`core/behaviors/case/nodes/communication.py` `_read_case_obj()` for the
canonical pre-ADR-0032 anti-pattern). Helpers are clean typed functions;
`update()` owns the failure-to-`Status` translation. See ADR-0032.

---

### Embargo Subtree Idempotency with Blackboard Flag

(ISSUE-750, 2026-06-08)

When a god node is decomposed into a sequence of leaf nodes, the original
single-pass semantics may break if duplicate-run behavior depended on the
god node's internal guard. Preserve idempotency explicitly:

- Add a blackboard flag (e.g., `embargo_initialized: bool`) that is set
  to `True` only when the current execution actually created a new embargo.
- Side-effect leaves that should only fire on first initialization (e.g.,
  seeding participants, creating events) MUST check this flag before
  acting.
- When moving EM transition logic to `EmbargoLifecycle.propose_embargo`,
  keep event creation and participant-seeding behavior aligned with
  existing duplicate-report tests to avoid introducing regressions.

---

### Conditional BT Branches as Selector Composites

(ISSUE-751, 2026-06-09)

For god-node decomposition where optional behavior depends on runtime
state, use an explicit `Selector` subtree instead of inline `if/else`
logic in a single `update()` method:

```python
# Pattern: Selector(active-branch-check, no-active-guard)
Selector(
    name="HandleActiveEmbargoOrSkip",
    memory=False,
    children=[
        Sequence(children=[CheckActiveEmbargo(), ProcessActiveEmbargo()]),
        AlwaysSuccess(name="no-active-embargo"),
    ],
)
```

**Blackboard handoff keys**: Each leaf node reads from and writes to named
blackboard keys (`new_case_participant`, `participant_case`,
`new_participant_id`). This makes each leaf independently testable and the
overall flow readable from the tree structure alone.

---

### Guarded Commit: Role-Gated Canonical Writes

(ISSUE-1021, 2026-06-17; see `specs/case-ledger-processing.yaml` CLP-09 and
`notes/case-ledger-authority.md` § "Commit Authorization and Coverage")

Any canonical-write node (e.g., `CommitCaseLedgerEntryNode`) that may be
reached from more than one actor context MUST be wrapped in a role-gated
`Selector`, never invoked bare:

```python
Selector(
    name="GuardedCommitCaseLedgerEntry",
    memory=False,
    children=[
        Sequence(
            children=[
                CheckIsCaseManagerNode(case_id=case_id),
                CommitCaseLedgerEntryNode(case_id=case_id),
            ]
        ),
        py_trees.behaviours.Success(
            name="CommitCaseLedgerEntrySkippedNotCaseManager"
        ),
    ],
)
```

This is the same Selector/Sequence/Success idiom as the section above; the
difference is what the condition checks. `CheckIsCaseManagerNode` resolves
the case's `CVDRole.CASE_MANAGER` participant and compares it against the
*actor active for this invocation* — never against the use-case class's
identity, and never assumed from a previous invocation having passed.

This matters specifically for use cases that can be invoked more than once
for the same logical activity with different receiving actors (e.g.,
`ack_report`'s case-actor invocation vs. its finder-relay invocation in the
demo). Gating per invocation, inside the tree, is what makes it safe to wire
the same shared subtree into both the trigger-side and received-side paths
of such a use case — see CLP-09-004. Do not introduce `py_trees.decorators`
for this; this codebase uses the Selector/Sequence/Success composite idiom
exclusively (see also "Conditional BT Branches as Selector Composites"
above).

Wrap the pattern once as a reusable factory (e.g.
`create_guarded_commit_case_ledger_entry_tree(case_id=None)`) rather than
re-inlining the Selector at each call site, and migrate all existing bare
`CommitCaseLedgerEntryNode` call sites to the factory — CLP-09-002 requires
a test asserting no bare usage remains outside it.

**`execute()` MUST do nothing but build one tree, run it once, and handle
the result** (ADR-0022, CLP-10-005, issues #1036/#1047): a received-side
use case's `execute()` method MUST (a) build exactly one BT via a
tree-factory function in `vultron/core/behaviors/`, (b) call
`BTBridge.execute_with_setup()` exactly once, with
`actor_id=receiving_actor_id`, and (c) handle the result (log, extract
output — see "Procedural Glue Exception" above). The guarded-commit
factory above MUST be composed as a child of that one tree, not invoked
separately, and the use case's main operation MUST itself be a BT node —
not procedural code sitting alongside the one `execute_with_setup()` call.

An audit (issue #1036, broadened to also resolve #1047) found this rule
violated in 9 use cases across 6 modules, in three different shapes:
genuine actor-identity switching — a real second `execute_with_setup()`
call under a different actor (`embargo.py` x3, `report.py` x2,
`status.py`; this is the literal pattern #1036 and #1047 describe, and in
`embargo.py`'s case the main tree already contains the identical
guarded-commit branch as its last child, but it no-ops because that tree
runs under the wrong actor); a single BT call preceded by non-BT
procedural code for the main operation (`note.py`, `actor/case_manager_role.py`
— a BT-06-001 gap, not actor-switching); and a single BT call under the
correct actor but assembled inline in `execute()` instead of via a
factory function (`case/lifecycle.py`). See ADR-0022 for the full
per-site breakdown and
`test/architecture/test_single_bt_execution_received_side.py` for the
migration ratchet.

---

### Fan-out / SYNC Decomposition: Context Handoff Pattern

(ISSUE-755, 2026-06-10)

For replay/fan-out flows, split nodes along blackboard context boundaries:

1. **Collect context leaf** — reads domain state, writes derived context
   (index, recipient list, current position) to named blackboard keys.
2. **Side-effect leaves** — each reads the context written by step 1 and
   performs a single side effect (emit activity, update record).

**Condition+action hybrid nodes**: If a node checks a condition and then
performs an action, decompose it further into a `Selector` composite:

```python
Selector(
    name="EmitIfRecipientExists",
    memory=False,
    children=[
        CheckRecipientPresent(),   # pure condition; returns FAILURE → fall through
        AlwaysSuccess("skip"),     # no-op when condition already met
    ],
)
```

This preserves the original guard semantics without embedding conditional
logic inside a single `update()`.

---

### Inbox Test Seam Must Preserve Production Deferral Semantics

(ISSUE-769, 2026-06-08)

A test-only inbox pipeline that reimplements defer/replay logic can drift
from production behavior unless it reuses the same expiry path. When
writing case-deferral tests:

- Set canonical `to` recipients matching the expected actor-scoped queue
  so actor-scoped queues are exercised under the same addressing assumptions
  as inbox processing.
- Do not reimplement the defer/replay path inline in tests — call the
  production code path directly so timing and queue semantics stay aligned.

---

### Decomposed BT Nodes Must Preserve Alternate Context Seams

(ISSUE-714, 2026-06-10)

When replacing a god node with a leaf-node sequence, preserve all input
seams the original node accepted:

- `case_id` from a blackboard key
- `case_obj`-derived context set during setup

If downstream leaves rely on blackboard keys written during setup, add
explicit fallback reads from staged objects/status context to avoid
regressing call paths that provide context in one form but not the other.

---

### Role Guard Required for All CASE_MANAGER-Only BT Subtrees

(ISSUE-1030, 2026-06-18; see `specs/behavior-tree-integration.yaml` BT-17-001,
BT-17-002)

The `CheckIsCaseManagerNode` role guard is not only for `CommitCaseLedgerEntryNode`
(see "Guarded Commit" above) — it MUST be applied to **any** BT subtree whose
semantics are restricted to the `CVDRole.CASE_MANAGER` actor. The canonical
composite is:

```python
Selector(
    name="ActionIfCaseManager",
    memory=False,
    children=[
        Sequence(
            name="CaseManagerGuardedAction",
            children=[
                CheckIsCaseManagerNode(case_id=case_id),
                ActionNode(case_id=case_id),   # your CASE_MANAGER-only node
            ],
        ),
        py_trees.behaviours.Success(name="ActionSkippedNotCaseManager"),
    ],
)
```

**Why this is necessary**: Received-side use cases run the BT with the receiving
actor's `actor_id`. Every participant that receives a broadcast may run the same
BT. Without an in-tree role guard, a CASE_MANAGER-only node such as
`AutoCloseBranchNode` fires for every receiving actor — including participants who
should remain silent. Placing the guard outside the tree (e.g., in `execute()`) is
insufficient because the same tree factory may be shared across trigger-side and
received-side paths.

#### Module-Level Idempotency Sets Must Be Paired with a Role Guard

A module-level `set[str]` used to prevent duplicate fires is **per-process**,
not per-container. In a Docker deployment, vendor-1 and finder-1 each have
separate Python processes with separate sets; a claim in finder-1 does not
affect vendor-1. However, **within a single process**, two fires can race:
if a phantom fire (wrong actor) runs first and claims the slot, the legitimate
fire (correct actor) is silently skipped.

**Fix**: Always pair a module-level idempotency set with a `CheckIsCaseManagerNode`
role guard at tree-composition time. The role guard ensures only the correct actor
can claim the slot. Issue #1030 observed this race on `AutoCloseBranchNode`:
the phantom fire on finder-1 claimed the set and blocked the real fire on the
case-actor in the same process.

---

### `memory=False` Sequence: Partial-Write Behavior on FAILURE

(BTND07-913, 2026-06-15; see `specs/behavior-tree-node-design.yaml` BTND-07-001)

A `Sequence(memory=False)` re-evaluates all children from the start on each
tick. If an early child succeeds but a later child fails, the early child's
side effects **have already been committed**. The Sequence as a whole returns
FAILURE, but local state written by the successful earlier children persists.

Example: `add_note_to_case_trigger_bt` uses a `memory=False` Sequence with
three children:

1. `CreateNoteNode` — creates and writes the note to the DataLayer
2. `AttachNoteFromResultNode` — attaches the note to the case
3. `SenderSideBT` — enqueues the outbound activity

If `SenderSideBT` fails (e.g., no CASE_MANAGER recipient resolved), steps 1
and 2 have already committed. **The note IS attached to the case locally even
though the overall BT returns FAILURE.** Tests MUST assert this partial-write
behavior explicitly so future readers do not assume FAILURE → no writes occurred.

**Design implication**: When using `memory=False` sequences for partially-
reversible operations, document which steps are non-transactional and what
state is committed if a later step fails.

---

### No-Op Path Must Clear Output Blackboard Keys

(ISSUE-834, 2026-06-18; see `specs/behavior-tree-integration.yaml` BT-17-003,
BT-17-004)

`py_trees.blackboard.Blackboard.storage` is process-global. `execute_with_setup`
cleans only the `datalayer` and `trigger_activity_factory` keys on exit — it does
NOT clean domain-specific output keys such as `broadcast_activity_id`.

**Rule**: When a BT node takes a no-op path (empty recipient list, guard
condition not met, etc.), it MUST explicitly write `None` to any output
blackboard key it would normally set. Leaving the key at its stale value from
a prior execution contaminates the next execution.

```python
# ✅ Correct — clear the key on no-op path
if not recipients:
    self.blackboard.broadcast_activity_id = None
    return Status.SUCCESS

# ❌ Wrong — stale value visible to next execution
if not recipients:
    return Status.SUCCESS
```

**Consumer side**: Any node that reads an output key from a peer node MUST
treat both `KeyError` (key never written, first-ever run) and `None` (key
explicitly cleared by no-op path) as equivalent no-op sentinels. Only handle
actual typed values.

**Regression test pattern**: Add a test that runs two `execute_with_setup`
calls back-to-back on the same blackboard instance without clearing between
them. Assert the second run does not observe output values from the first when
the producer node takes a no-op path.

---

### Routing-Gated State Mutation

(BT-19, 2026-06-26; see `specs/behavior-tree-integration.yaml` BT-19-001,
BT-19-002)

A BT Sequence that performs a protocol state-machine transition (EM, RM, or CS)
and then routes an outbound activity MUST resolve all routing prerequisites
in a read-only guard node placed **before** the state-mutation node.

**Why ordering matters**: Once the DataLayer accepts a state write (e.g.,
`EM=EXITED`), the transition is committed. If the subsequent routing step
then fails (missing Case Manager, missing factory), the outbound notification is
never sent. Peers retain the prior state; local state has advanced — a
divergence window that requires ledger-sync catch-up (SYNC-10) to repair.
Moving the routing guard to the top of the Sequence eliminates the divergence:
if routing prerequisites are absent, the tree returns `FAILURE` with zero
DataLayer state change.

**Shared factory requirement**: Duplicated monolithic BT nodes that inline both
state mutation and dispatch in a single `update()` method drift independently.
The canonical factory-composed path may correctly order the guard, while the
automatic-cascade monolith retains the old unsafe ordering, reintroducing the
divergence bug on that path only. All call sites for the same lifecycle
transition MUST use a shared BT factory function (BT-19-002).

**Canonical Sequence structure**:

```text
Sequence
├── ResolveCaseManagerNode          ← read-only guard; FAILURE = bail, no write
├── <StateTransitionNode>           ← mutation committed after guard passes
└── <SendDispatchNode>              ← routing succeeds because guard already verified
```

**Anti-pattern** (Issue #1054 — `TerminateEmbargoNode`):

```text
Sequence
├── TerminateEmbargoLifecycleNode   ← mutation committed first ← ❌
└── SenderSideBT                    ← routing checked second; fail = divergence
```

**Fix**: Extract a shared factory (`terminate_embargo_bt`) that places
`ResolveCaseManagerNode` before `TerminateEmbargoLifecycleNode`, and replace
all standalone monolithic nodes with the factory output. Both trigger and
cascade call sites use the shared factory directly (BT-19-002, PR #1263).

---

### Demo Devlog Race: Wait for Replica Before Dumping

(DEMO-DEVLOG-RACE, 2026-06-18)

Demo phases that write JSONL devlogs will miss recently committed canonical
ledger entries if they run before the async `Announce(CaseLedgerEntry)`
fan-out has been processed and stored by the replica actor.

**Pattern**: After any phase that commits a new canonical ledger entry, query
the sender's current tail hash and poll until the replica acknowledges it before
writing the devlog:

```python
vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
if vendor_entries:
    tail = max(vendor_entries, key=lambda e: e["log_index"])
    wait_for_finder_log_entry(finder_client, case.id_, tail["entry_hash"])
```

Apply this poll-until-hash pattern after every phase that introduces a new
ledger tail before a devlog dump. This is the same pattern used in
`_phase_sync_verification` and ensures dump artifacts are always consistent
with the replica's committed state.

---

### Integration Tests Must Use Deterministic Factories When BT Default Is Probabilistic

(BT-FACTORY-DETERMINISM, 2026-07-08; learning `ISSUE-1151`)

When a tree builder's default `CallOutBackendFactory` wraps a probabilistic
fuzzer node (e.g., `AlmostAlwaysSucceed` at 90% success), integration tests
that assert `result.status == Status.SUCCESS` become flaky. Two such nodes in
series give ~81% tree success — a failure probability that surfaces within a
few test runs.

**Pattern that caused this**: Adding factory injection to a tree builder (e.g.,
`create_validate_report_tree`) where the fuzzer defaults (`EvaluateReportCredibility`,
`EvaluateReportValidity`) are `AlmostAlwaysSucceed` nodes. Existing integration
tests called the builder with no factory args and asserted `SUCCESS`.

**Fix**: Add a module-level `_always_succeed_factory` helper to the test file
and pass it explicitly to all integration tests that require `SUCCESS`:

```python
def _always_succeed_factory(name: str) -> py_trees.behaviour.Behaviour:
    class _AlwaysSucceed(py_trees.behaviour.Behaviour):
        def update(self):
            return py_trees.common.Status.SUCCESS
    return _AlwaysSucceed(name)
```

**Scope**: This applies only to integration tests (those that assert
`Status.SUCCESS` on the full tree execution). Tree-structure tests (node names,
child counts) and `FAILURE`-path tests (missing `DataLayer`, missing report)
are not affected.

**Rule**: Any time a tree builder's default factory wraps a probabilistic fuzzer
node, update all integration tests that assert `SUCCESS` to pass an explicit
deterministic factory. See `test/AGENTS.md` § "BT Factory Determinism".

---

### Namespaced Inter-Node Handoff Keys

(CONCERN-1335, 2026-07-10; see `specs/behavior-tree-node-design.yaml` BTND-03-004)

The py_trees blackboard is **process-global**. When a tree factory function is
called for two concurrent incoming messages of the same type (e.g., two
simultaneous `Offer(Actor, Case)` deliveries), both tree instances write to the
same flat blackboard namespace. A node in instance A that writes `suggested_roles`
will have that value overwritten by instance B before instance A's downstream
consumer reads it — causing silent data corruption.

**Pattern**: Any BT node that writes an inter-node handoff key (a value written
by one node and consumed by a downstream sibling in the same tree) MUST include
the execution-scoped correlation ID in the key name:

```python
# ❌ WRONG — flat key, collides across concurrent tree instances
self.blackboard.register_key("suggested_roles", access=Access.WRITE)
self.blackboard.suggested_roles = [CVDRole.VENDOR]

# ✅ CORRECT — namespaced by execution-scoped ID
id_segment = self.recommendation_id.split("/")[-1]
self.blackboard_key = f"suggested_roles_{id_segment}"
self.blackboard.register_key(self.blackboard_key, access=Access.WRITE)
setattr(self.blackboard, self.blackboard_key, [CVDRole.VENDOR])
```

The consumer node derives the same key from the same correlation ID:

```python
# In setup():
id_segment = self.recommendation_id.split("/")[-1]
self.blackboard_key = f"suggested_roles_{id_segment}"
self.blackboard.register_key(self.blackboard_key, access=Access.READ)

# In update():
try:
    roles = self.blackboard.get(self.blackboard_key)
except KeyError:
    roles = [CVDRole.VENDOR]  # safe default if key not set
```

**Key derivation convention**: `{noun}_{id_segment}` where `id_segment` is
`correlation_id.split("/")[-1]` for HTTP URIs (same as `helpers.py` line 352),
or the last colon-delimited segment for URN IDs. This matches the existing
`object_{id_segment}` pattern used by `WriteObjectToBBNode` /
`ReadObjectFromBBNode` in `helpers.py`.

**When this applies**: Any inter-node handoff key in a tree factory that may
realistically be called with multiple concurrent executions — i.e., where the
factory is called per-incoming-message for a message type that can arrive in
bursts (offer/accept/reject workflows in particular). Keys that are always
cleaned up and rewritten before being read (e.g., within a single Sequence with
`memory=False`) are safe, but namespacing eliminates the risk entirely and
is cheap to implement.

**Known instances** (catalogue for conformance audits):

| Key(s) | Tree factory | Correlation ID | Discovered |
|---|---|---|---|
| `suggested_roles` | `create_recommend_actor_to_case_received_tree` | `recommendation_id` | CONCERN-1335 |
| `new_case_participant`, `participant_case`, `new_participant_id` | `create_receive_report_case_tree` | `report_id` | CONCERN-1349 |

When auditing for compliance, grep for flat blackboard key registrations in
tree factories called per-incoming-message and verify each inter-node handoff
key includes the execution-scoped correlation ID segment.

---

### Blackboard List Mutation: Write-Back Is Redundant (But Needed for New Lists)

(ISSUE-1374, 2026-07-13)

py_trees stores blackboard values by reference. Mutating a list retrieved from
the blackboard (e.g., `list.pop(0)`, `list.append(x)`) updates the stored value
in place — any subsequent reader sees the change without a write-back.

```python
# ❌ REDUNDANT — write-back is a no-op; same object is already updated
lst = self._bb.my_key
lst.pop(0)
self._bb.my_key = lst   # same reference; no effect

# ✅ CORRECT — omit the write-back for mutation of an existing list
lst = self._bb.my_key
lst.pop(0)
```

**Exception**: the write-back IS required when the list was created fresh in
an `except KeyError` branch. A brand-new `[]` is not yet stored on the
blackboard; the write-back is the only thing that persists it:

```python
try:
    lst = self._bb.my_key
except KeyError:
    lst = []
    self._bb.my_key = lst  # ← required: new list, not yet in blackboard
lst.pop(0)
```

---

### Always Check `BTBridge.execute_with_setup` Return Value

(ISSUE-1325, 2026-07-13)

`BTBridge.execute_with_setup` never raises — it catches all exceptions from
the inner BT tick and returns `BTExecutionResult(status=FAILURE, ...)`. If the
caller ignores the return value and falls through to `return Status.SUCCESS`,
the node silently reports success even when the subtree failed.

```python
# ❌ WRONG — subtree failure is silently swallowed
BTBridge(...).execute_with_setup(tree=commit_tree, actor_id=self.actor_id)
return Status.SUCCESS

# ✅ CORRECT — raise on failure so the outer node propagates FAILURE
result = BTBridge(...).execute_with_setup(
    tree=commit_tree, actor_id=self.actor_id
)
if result.status != Status.SUCCESS:
    raise RuntimeError(f"subtree failed: {result.feedback_message}")
```

Raising inside the outer `except Exception` handler in `update()` ensures the
calling node returns `FAILURE` rather than `SUCCESS`.

---

### Ledger Commit Must Precede Outbox Write

(ISSUE-1325, 2026-07-13)

When a BT subtree both commits a ledger correlation marker and records an
outbox item, the ledger commit MUST happen first.

If the outbox write happens first and the ledger commit subsequently fails,
the outbox item is orphaned: an activity queued for delivery with no
corresponding ledger entry. On the next invocation, the duplicate-detection
guard finds no pending entry and takes the "fresh" path, triggering a
duplicate offer or invite.

Correct ordering in a tree or composite node:

1. Build activity via factory (creates the object in the DataLayer)
2. Commit ledger correlation marker (fail-fast if anything is wrong)
3. Record outbox item (reached only if ledger commit succeeded)

This invariant is enforced by CLP-10-006 in `specs/case-ledger-processing.yaml`.

---

### Use `disposition="rejected"` for Local-Only Ledger Correlation Markers

(ISSUE-1325, 2026-07-13)

When a BT node needs a local ledger entry that does NOT correspond to a
canonical AS2 activity (e.g., tracking an outbound
`offer_case_participant` for duplicate detection), use
`disposition="rejected"` in `create_commit_log_entry_tree`.

`_validate_canonical_entry` returns early for non-`"recorded"` dispositions,
bypassing the `_CANONICAL_PAYLOAD_SIGNATURES` allowlist check.  The entry is
still persisted and `find_protocol_pair` does not filter on disposition, so
the correlation marker remains visible to duplicate-detection nodes.

The `_find_equivalent_recorded_entry` idempotency check also filters on
`disposition == "recorded"`, so repeated calls each create a new marker —
which is fine when the BT guarantees at-most-once execution per receipt (e.g.,
via `GuardedCommit` in `create_receive_activity_tree`).

---

### suggest-actor Accept Path Does Not Thread Roles Into Invite

(ISSUE-1406, 2026-07-14)

`create_accept_actor_recommendation_received_tree` (CaseActor receives
`Accept(Offer(CaseParticipant))` from Case Owner) never writes the
`suggested_roles` blackboard key. `EmitInviteActorToCaseNode` reads this key
via `_read_suggested_roles()`, gets a `KeyError`, and passes `roles=None` to
`factory.invite_actor_to_case()`. The resulting `Invite` carries `roles=None`,
so after `Accept(Invite)` the new `VultronParticipant.case_roles` is `[]`.

This is documented behavior (ADR-0032, BT-HELPER-01: no silent default
substitution), not a bug.

**Test implication**: Only the `invite_actor_to_case_trigger_bt` path (or a
tree with `EvaluateDefaultRolesNode`) produces a non-empty `case_roles`. The
`AcceptOfferCaseParticipant` received-side use case always produces
`roles=None` in the Invite. Tests that verify roles end up on a participant
MUST exercise the trigger path, not the received path.

**Blackboard key contrast**:

| Tree factory | Key written | Namespaced? |
|---|---|---|
| `create_recommend_actor_to_case_received_tree` | `suggested_roles_{id_segment}` | ✅ |
| `create_accept_actor_recommendation_received_tree` | *(never written)* | N/A |

---

### BTND-03-004 Audit Scope: All Keys in the Subtree

(ISSUE-1397, 2026-07-14)

When namespacing blackboard keys per BTND-03-004, audit ALL
`register_key` calls within the affected composite subtree — not just the
keys named in the issue body. Code review on ISSUE-1397 caught two more
flat keys (`participant_accepted_status`, `owner_initial_status`) that were
intra-Sequence only (currently low-risk) but still violate BTND-03-004.

**How to audit**: grep for `register_key` across the affected module, list
every key, then check whether each one crosses a concurrent-execution
boundary. Keys that are always cleaned up and rewritten before being read
within a single `Sequence(memory=False)` are low-risk, but namespacing
eliminates the risk entirely and is cheap.

---

### Production Collapse (FUZZ-08x): Use the Prior Collapse as a Concrete Template

(ISSUE-1310, 2026-07-22; see also `notes/bt-fuzzer-nodes-report-management.md`)

When implementing a FUZZ-08x Production Collapse, read the most recently merged
sibling collapse first and mirror its file layout, import structure, test-file
shape, and doc-update checklist. The pattern is stable across collapses:

**What survives:**

- Outer loop structure (evaluators/retrievers/effort gates)
- All factory call-out points (ADR-0025)
- Typed sub-loops where relevant

**What is replaced:**

- Granular simulator Actuator nodes → a single `EvaluatorCallOutPoint` (or
  `suggest-actor-to-case` trigger for notification loop collapses)
- The eliminated `InjectX` / `BypassX` fuzzer classes remain in the demo
  module as catalogued simulator stand-ins; they stop being wired into the
  production tree

**Import structure:**

- Decision model lives in the core tree module
  (`vultron/core/behaviors/*/…_tree.py`)
- Demo fuzzer Evaluator imports the model at module level
- Core tree module uses **deferred (function-local) imports** of the fuzzer to
  avoid the circular dependency

**Default field encoding:** the `EvaluatorCallOutPoint` mixin writes
`typ()` (a default-constructed instance) on SUCCESS, so a decision model's
field defaults MUST encode the sensible default outcome (e.g.,
`PublicationIntentDecision` defaults to publish fix + report, withhold
exploit).

**Arm gating:** use the positively-named gate idiom (BTND-08-001):
`Selector(Sequence(ShouldPublishX, Prepare, Publish), Inverter(ShouldPublishX))`
— a not-intended arm is a graceful SUCCESS no-op while a genuine
Prepare/Publish FAILURE still propagates.

**Doc-update checklist per collapse:**

1. ADR: `proposed` → `accepted`, remove `PROVISIONAL` marker
2. `specs/behavior-tree-integration.yaml` BT-20-xxx: remove `PROVISIONAL` from
   rationale, update `tracking_issue` to the implementing PR/issue
3. `notes/bt-fuzzer-nodes-report-management.md`: rewrite the matching
   "Production Collapse N" section and each affected node's "Factory-fn
   placement" line

<!-- Source: ISSUE-1310 -->

---

### Dual-Path Consolidation Test Gap

(ISSUE-1378, 2026-07-14)

When consolidating two helpers with different lookup paths into one unified
function, the new test suite MUST exercise each distinct path in isolation.

In ISSUE-1378, `_resolve_case_manager_id` was consolidated from two helpers:
a primary `actor_participant_index` path and a fallback `case_participants`
path. All 6 initial tests only populated `case_participants`, leaving the
primary index path entirely untested. Code review caught the gap; a 7th test
(`test_primary_index_path_returns_actor_id`) was added before the PR merged.

**Pattern**: For a helper with N distinct lookup paths, write at least one
test per path where that path is the *sole* source of truth — all other paths
are left empty or unpopulated. "One test exercises both paths" means neither
path is verified independently.
