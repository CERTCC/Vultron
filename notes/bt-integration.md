---
title: Behavior Tree Integration Design Notes
status: active
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
