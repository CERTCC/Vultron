---
title: Behavior Tree Integration Design Notes
status: active
tags: [bt, behavior-trees, py_trees, blackboard, BT-nodes, protocol-cascades]
description: >
  BT design decisions, py_trees patterns, simulation-to-prototype translation
  strategy, subtree map, and anti-patterns to avoid.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-endpoint.yaml
  - specs/case-ledger-processing.yaml
  - specs/embargo-policy.yaml
  - specs/participant-case-replica.yaml
  - specs/case-bootstrap-trust.yaml
related_notes:
  - notes/bt-canonical-reference.md
  - notes/case-ledger-authority.md
  - notes/bt-pitfalls.md
  - notes/embargo-lifecycle.md
  - notes/bt-fuzzer-nodes.md
  - notes/protocol-event-cascades.md
  - notes/use-case-behavior-trees.md
  - notes/testing-pitfalls.md
  - notes/inbox-orchestration.md
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

### 6. Case Creation Does *Not* Generate a Per-Case CaseActor Object

**Corrected in #1872.** This note previously said case creation creates a
CaseActor object, one per `VulnerabilityCase` (1:1). It does not, and that model
was the bug.

Authority over a case is a **role** — `CVDRole.CASE_MANAGER`, held by whichever
participant is the case's authority — worn by a container, one per container, not
a per-case object (CP-08-002/003). The concrete actor that enacts it (the
prototype's "CaseActor") has the stable identity
`{case_actor_service_url}/actors/case-actor`. A per-case identity such as
`.../actors/case-actor-{slug}` was a phantom: computed by the sender, hosted by
nobody, so delivery to it 404'd permanently and the proposal round-trip never
began.

What actually happens: `PublishCaseActorIdentityNode` *publishes* the configured
identity to the blackboard and creates nothing;
`EnsureCaseActorHostedNode` provisions the record in the enacting actor's own store so
its inbox answers, and returns `SUCCESS` when that actor is hosted elsewhere,
because that is a normal topology. `ResolveCaseActorUrlsNode` — which derived the
per-case identity *and* created a per-case `Service` object to match — is gone.

**Rationale**: a case needs a message-processing owner, but "owner" is a role
held in the case, and its holder may be any Actor type. Making it a role rather
than an object is also what lets a dedicated container provision itself from its
own seed config.

**Case ownership model**:

- **Case Owner**: Organizational Actor (vendor/coordinator) responsible for
  decisions.
- **CASE_MANAGER**: the case-management authority role; the actor enacting it
  (the prototype's "CaseActor", an ActivityStreams Service) manages case state,
  distinct from the case owner.
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

### The store follows the executing actor (BT-05-005)

`BT-05-002` and `BT-05-003` put the store and the executing actor on the
blackboard as two independent facts, so they could disagree. Under per-actor
storage they are one fact: a store is always *some* actor's own, so the blackboard
`actor_id` determines which store the tree operates on. `BTBridge` therefore
**reconciles** the two rather than accepting whatever store the caller injected —
see `_store_for_actor`, which delegates to
`vultron/core/behaviors/store_scope.py::store_for_actor`.

The delegated-emit pattern is where divergence bites. A trigger emitting on the
CASE_MANAGER's behalf runs with `actor_id` set to the CASE_MANAGER while the injected
DataLayer belongs to the *requesting* actor: the activity is created in one store
and queued in the other's outbox, so the CASE_MANAGER never delivers it and its
outbox names an activity its own store does not hold.

Exception: a store that reports no `actor_id` at all — a test double, or any
implementation that predates per-actor storage — is passed through untouched, and
a test may deliberately let the identities differ to assert the *skip* path.

### Role-gated trees: three identities must be one (BT-05-006)

Where a tree is gated on a role held in the case, the **role holder**, the
**receiving actor** and the **store owner** must be one actor. Letting any two
drift produces a silent skip rather than an error: the gate evaluates against an
actor holding no role, returns SUCCESS-by-skip, and nothing is written.

The corollary for node authors: gate on the role
(`create_case_manager_gated_tree`), never by comparing `actor_id` against a
computed `case_actor_id` (CM-24-004). Once the emit is role-gated the executing
actor *is* the case manager, so the activity and its outbox entry land in one
store by construction. Ungated, the same helper is identity spoofing.

### The message subject is a fourth identity, and it must stay separate

BT-05-006 above is about three identities that must **coincide**. There is a
fourth that must **not**: the *subject* the message names — invitee, accepting
actor, rejecting actor, target actor. It answers "whose consent/state is this
message about?", which is a different question from "whose replica am I
applying it to?" (`resolve_receiving_actor_id()`) and from "who is executing
the tree?" (blackboard `actor_id`).

Subject identities MUST be read from the message and threaded into the tree as
leaf-node constructor data — never derived from the receiving actor (ADR-0022,
which names `invitee_id` and `accepting_actor_id` as legitimate leaf-node
inputs that are never legitimate `actor_id` values). They coincide with the
receiving actor on the direct-delivery path, which is exactly what makes the
conflation survive testing: it breaks only under CLI dispatch, log replay, a
CASE_MANAGER relaying on a participant's behalf, or a multi-recipient activity.

Two failure shapes to watch for, both of which returned SUCCESS while writing
to the wrong record (ISSUE-2762):

- **Reusing the resolved receiving actor as a subject.** Satisfies every
  written requirement and inverts the semantics.
- **A tree factory that accepts a subject argument and only logs it.** A
  lenient lookup that falls back to the BT execution actor when the subject is
  falsy makes a dropped subject argument indistinguishable from one never
  supplied. Log at WARNING when a subject *was* named and did not resolve, as
  `CanAnswerEmbargoInviteNode` does, which separates the two.

Read a subject **from the message**, never from the receiving actor. For an
`Invite(EmbargoEvent)` the invitee is the Invite's *sole* `to:` recipient
(EP-09-010, ADR-0113): every emitter sends one recipient (a participant to the
CASE_MANAGER; the CASE_MANAGER to one participant per relayed Invite), so an
Invite naming several recipients or none is refused as a misrouting, never
resolved by membership or guessed at. The earlier "addressee membership"
resolution in `resolve_invitee_id()` (`vultron/core/use_cases/received/embargo.py`)
was built for a multi-recipient shape nothing emits, and its fallback to the
receiving actor put the deadline on the enforcer's own record; #3963 retires it.
Where a message legitimately names several recipients (the report `Offer`),
test membership with `is_addressed_to()` (`vultron/core/predicates/addressing.py`),
never a bare `in`: `to:`/`cc:` arrive as the sender wrote them, so a trailing
slash misses an exact match while the receiver is canonical (#2667); see
`_is_primary_submit_report_recipient()` in `received/report.py`. Full rule:
`vultron/core/AGENTS.md` § "A Message Subject Is Never
`resolve_receiving_actor_id()`".

---

## Concurrency Model

**Prototype approach**: Sequential FIFO message processing per actor.

**Implementation**: BackgroundTasks queues messages; inbox endpoint returns
202 immediately. BT execution happens in the background on a **thread pool**
— not a single thread, and never on the event loop — by two routes:

- Trigger routes are synchronous `def` endpoints, so Starlette runs them via
  `anyio.to_thread.run_sync`.
- The inbox background task (`run_inbox_pipeline`) is an `async def`, which
  Starlette runs *on the event loop*; it therefore hands the synchronous BT
  pipeline (`process_payload` and the replay loop) to `asyncio.to_thread`
  itself, inside the per-actor asyncio lock (IE-06-003).

**Why the inbox hop matters** (#3033, #2898): before the hop, every inbound
activity stalled the whole container for its BT tick. No HTTP response went
out, peers' deliveries were not accepted, no co-hosted outbox drain could run
(the served app did not even start an `OutboxMonitor` until ADR-0112 — its
root lifespan had drifted from `app_v2`'s), and a trigger route waiting on the BT lock from
its threadpool thread starved until the client timed out. In the fv demo the
CaseActor's outbox paid one full BT tick per delivery on the vendor container
(0.6–5 s each under CI load), and `Create(VulnerabilityCase)` was queued
behind a ledger fan-out that took 17 s to drain. A stale version of this
section said the inbox path already ran on the thread pool; it had, before
the task became a coroutine.

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

Nothing domain-significant lives outside the tree. In particular, a call from
`execute()` to a helper function that writes to the DataLayer is **not** glue:
the write is outside the tree whatever the helper is named, and the mutation
ratchet (`test/architecture/test_no_dl_mutations_in_execute.py`) resolves such
calls through the use-case package transitively (CLP-10-020): a write that a
received `execute()` reaches through any function or method defined under
`vultron/core/use_cases/` — module helper, `self._method()`, relative or
re-exported import, any depth — is a violation of the file holding the
`execute()`. Resolution stops at the package boundary, so a BT node's write is
never one. Trigger-side bodies get only the direct rule (BT-15-001 governs
them). Eleven received `execute()` bodies in nine files reached a write this way
when the rule was widened, most through one shared `_idempotent_create` helper
and the rest through bespoke ones, invisible to the earlier body-only scan
because the write sat one call away (ISSUE-3339, ADR-0111). They are held as the
exact `KNOWN_VIOLATIONS` set, each entry annotated with the issue that retires
it.

### The Four Received-Side Stages (ADR-0111)

A received-side tree composed via `create_receive_activity_tree` runs four
stages in a fixed order (CLP-10-006, CLP-10-010):

1. **Intake** — one shared node, `IntakeReceivedActivityNode`
   (`vultron/core/behaviors/case/nodes/intake.py`), archives the mail: the
   received activity exactly as received, idempotently, as a
   `ReceivedActivityRecord` (`vultron/core/models/received_activity_record.py`)
   whose id the *receiver* derives (`build_id(sender_activity_id)`) and which
   carries the sender's id for the reverse lookup. Never under the sender's
   id: the DataLayer is one id-keyed table per actor, so a sender naming its
   activity after a record we derive (a pending-case-inbox marker, an offer
   record) would occupy that id ahead of our own write and a read-then-create
   helper would read the squatter as "already stored". A reader that needs
   the archived activity goes through `build_id`. It decides nothing,
   ledgers nothing, and writes nothing else (CLP-10-017). It runs first, so a
   refusal a moment later still leaves the receiver holding the archive
   (CLP-10-018). The letter's contents are not core's records: a case, note,
   status or embargo carried inline is a *message shaped like* that object, and
   the record core keeps is written by an effect node from the event's copy,
   after the guards. Intake writing them would let any sender seed a replica
   ahead of the trust checks — a stored case row *is* the replica (PCR-03-004,
   CBT-01-005). A stored `VultronActivity` dehydrates `object`/`target` to ids,
   so the faithful copy is the received evidence ADR-0107 step 5 seals at parse;
   #3742 persists it beside the archived row, through this node.
2. **Guards** — read-only precondition checks that return FAILURE to refuse.
   They write nothing. A refusal goes to the process log and, where the
   protocol calls for it, a `Reject` back to the sender — never to the ledger
   (CLP-05-002).
3. **Commit** — the CASE_MANAGER ledgers the received activity as received, a
   postmark on the envelope (ADR-0107, CLP-07-011). It never rebuilds the
   assertion from processed state.
4. **Effects** — apply the accepted assertion to the local replica and enqueue
   any cascades.

Intake is the only path that stores the received activity (CLP-10-019). Do not
add a per-tree store node or a handler-local store helper; the factory
(`create_receive_activity_tree`, `vultron/core/behaviors/case/receive_activity_tree.py`)
already supplies the intake node as the first child of every tree it builds. A
receive tree that does not compose through the factory runs no intake. #3870
moved the two that composed `create_case_manager_gated_tree` directly (add-note,
update-case) and found more that never used the factory; those are held as an
exact set in `test/architecture/test_receive_side_intake_first.py`
(`KNOWN_FACTORIES_BYPASSING_INTAKE`) — fifteen in all once a receive-side tree is
defined as one a received use case calls rather than one whose name says
"received". Each moves with the handler migration that owns its area
(#3871–#3874); the sync and dead-letter trees move with #3935. Calling the
factory is not enough: the ratchet checks that the factory *returns* the shared
factory's result, because a tree that nests it under a hand-built root (as the
close-case tree did, a Selector whose first arm guarded ahead of intake) runs
something before intake. Those are a second exact set,
`KNOWN_FACTORIES_NESTING_INTAKE`, empty since #3870 lifted the close-case
tree's intake to its root. A tree that needs a branch ahead of the receipt
commit wraps the branch: outer factory with `case_id=None` (intake, no commit),
inner factory per arm that commits. The inner intake finds the archive and
writes nothing.

The factory commits only when it is given a `case_id`, and CLP-10-013 requires
the commit exactly when the received `(type, object)` pair is a canonical payload
signature (`_CANONICAL_PAYLOAD_SIGNATURES`) — otherwise the CASE_MANAGER would
refuse its own commit. `Update(VulnerabilityCase)` is not one, so
`create_update_case_received_tree` passes `case_id=None` and the CASE_MANAGER
publishes the update through its `Announce` broadcast (CM-06-001) as before;
whether an owner's update should become a ledgered assertion (ADR-0108) is
issue #3936.

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
state machine (EM: NONE → PROPOSED → ACTIVE → REVISE → EXITED) maps
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
(RM.RECEIVED). `CaseParticipant` records are created at that time:
reporter at RM.ACCEPTED, receiver at RM.RECEIVED. RM state is tracked
in `CaseParticipant.participant_status[].rm_state` from the moment
of case creation.

> **ADR-0015 is superseded by ADR-0041.** In the CASE_MANAGER-authoritative model
> the vendor tree no longer creates the `VulnerabilityCase` directly.  The vendor
> stores the report, writes a pending `VultronReportCaseLink`, and sends
> `Create(as_CaseProposal)` to the CASE_MANAGER; the CASE_MANAGER creates the case,
> adds participants, and initializes embargo before emitting
> `Create(VulnerabilityCase)` back to the vendor.  See `notes/case-proposal.md`
> for the corrected flow (CM-22, CP-09).

`ReportStatus` in the flat status layer is a **transient pre-case
mechanism** that was previously used for reports not yet associated with
a case (pre-case RM states: RECEIVED, INVALID). Under ADR-0015, the case
is created at receipt, so `CaseParticipant` records carry RM state
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

> See also: [bt-canonical-reference.md](bt-canonical-reference.md) for the
> canonical CVD Protocol BT subtree map, node symbol legend, and BT-IDM
> anti-patterns.
>
> See also: [bt-pitfalls.md](bt-pitfalls.md) for per-pitfall debugging notes
> on blackboard semantics, idempotency, role guards, and other common BT
> implementation pitfalls.
