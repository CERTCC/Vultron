---
title: BT Cross-Cutting Mechanics
status: active
kind: guidance
description: >
  Cross-cutting mechanics for py_trees BT integration: failure reason
  propagation, blackboard key semantics, execution-scoped key lifetime and
  the BTBridge exception-handler contract, idempotency patterns,
  memory=False partial-write behavior, key namespacing, refusal-arm
  fail-closed rules, and the received-tree CASE_MANAGER gate.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
  - specs/case-proposal.yaml
  - specs/code-style.yaml
  - specs/received-status-handling.yaml
  - specs/participant-case-replica.yaml
related_notes:
  - notes/bt-integration.md
  - notes/sync-ledger-replication.md
  - notes/call-out-configuration.md
  - notes/bt-canonical-reference.md
  - notes/bt-design-patterns.md
  - notes/domain-validation.md
  - notes/embargo-lifecycle.md
  - notes/received-status-authorization.md
  - notes/testing-pitfalls.md
  - notes/protocol-asks.md
  - notes/peer-broadcast-failure-semantics.md
  - notes/agentic-workflow.md
  - notes/case-proposal.md
  - notes/embargo-default-semantics.md
  - notes/status-dimension-objects.md
relevant_packages:
  - py_trees
  - vultron/core/behaviors
---

# BT Cross-Cutting Mechanics

> See also: [bt-integration.md](bt-integration.md) for design decisions,
> [bt-canonical-reference.md](bt-canonical-reference.md) for the canonical BT
> structure, and [bt-design-patterns.md](bt-design-patterns.md) for composite
> idioms. Domain-specific pitfalls live in per-directory `AGENTS.md` files under
> `vultron/core/behaviors/`.

## BT Failure Reason Propagation

A BT-failure log line MUST name which node failed and why: get it from
`BTBridge.get_failure_reason(tree)` (depth-first walk to the first failing leaf),
never from the root's `feedback_message`. A failing `Sequence` root's own
`feedback_message` is always `""`, so a log of it says only "BT failed" (BT-13-001).

First-failing-leaf is a transport rule, not a diagnostics budget. A node whose
validation can fail several ways MUST report all of them in its own
`feedback_message` (EH-07-001); a `memory=False` `Sequence` fails one leaf per
tick, so aggregating *within* a node is compatible with the walk, while
aggregating *across* sibling guards would need a restructure. See
[domain-validation.md](domain-validation.md) § "Rejecting as a Unit Does Not
License Reporting One Reason".

---

## py_trees `blackboard.get()` Raises KeyError for Unwritten READ Keys

`Client.get(key)` raises `KeyError`, not `None`, for a key registered `READ` but
never written. In a node's `update()`, convert that into an explicit `FAILURE`
with a `feedback_message` (via a raising helper, § BT-HELPER-01) or guarantee the
key is written first; an escaped `KeyError` becomes an opaque bridge-level failure.

- Read raw `Blackboard.storage.get("/key")` (leading `/`) only in tests, never in
  node code.
- After adding a node class to a file, check class boundaries with
  `grep -n "^class " <file>`: a class body pasted inside another silently replaces
  the earlier `update()`, and the node can return SUCCESS for the wrong reason.

---

## BT Result Channel for Domain Errors

When a BT node performs a strict state-machine transition, write the domain
exception into `result_out["error"]` and return `FAILURE`; the use case's
`execute()` re-raises it if it is a `VultronError`. Callers and tests then see the
original exception type (e.g. `VultronInvalidStateTransitionError`) instead of a
generic BT failure.

---

## BT-HELPER-01 — Helpers Raise; `update()` Catches

BT node helper methods MUST complete or raise a domain exception (e.g.
`BtNodePreconditionError`); they MUST NOT return `None` as a failure signal.
`update()` is the single `try/except`: it sets `self.feedback_message = str(e)` and
returns `FAILURE`. A helper returning `None` fails silently with no
`feedback_message` (ADR-0032).

Call `_on_success()` (or any success-path side effect) **after** the `try` block,
not inside it: inside, an unexpected error from the side effect is caught by the
precondition handler and reported as a misleading precondition failure.

The exceptions are a port type mismatch (§ "`NoDataAvailable` Surfaces in
`initialise()`") and nodes in a refusal arm (§ "A Refusal Arm in a Selector Fails
Toward 'Admit'"), where letting the error escape is the safe outcome.

---

## Decomposed BT Nodes Must Preserve Alternate Context Seams

When replacing a god node with a leaf sequence, preserve every input seam the
original accepted (a `case_id` blackboard key, `case_obj`-derived context set in
setup), so call paths that supply context in only one form do not regress. Keep
the optional branch as a `Selector`/`Sequence` subtree with named blackboard
handoff keys, not inline `if/else` in one `update()` — see
[bt-design-patterns.md](bt-design-patterns.md) § "Handler / Routing BTs:
Precondition-Sequence".

---

## Use DataLayer Outbox for Idempotency, Not Module-Level Sets

An "already fired?" guard MUST query the DataLayer (e.g. the outbox), as
`CloseNotYetEmittedConditionNode` does. A module-level `set[str]` is
per-process — separate containers keep separate sets — and within one process a
wrong-actor fire can claim the slot first and silently suppress the legitimate one.

---

## `memory=False` Sequence: Partial-Write Behavior on FAILURE

A `Sequence(memory=False)` that fails at a later child leaves the earlier
children's side effects committed. Document which steps are non-transactional,
and assert the partial-write state in tests so nobody assumes FAILURE means no
writes (BTND-07-001). To make a failing guard leave nothing behind, put every
read-only guard (case existence, role resolution, routing prerequisite) before the
first mutation (BT-19-001). Worked example: `vultron/core/behaviors/note/AGENTS.md`
§ "`memory=False` Note Sequence".

---

## An Idempotency `Selector(…, Success)` Masks a Real Downstream FAILURE

The skip-if-done idiom `Selector(Sequence(guard, work), Success)` returns SUCCESS
whatever `work` does. Where `work` can genuinely fail (case creation, a commit)
and that FAILURE must reach the caller, put the gate in front instead:
`Sequence(gate, existing_selector)`. The gate still short-circuits, and a real
failure is no longer swallowed.

---

## No-Op Path Must Clear Output Blackboard Keys

`Blackboard.storage` is process-global, and the bridge restores only the keys in
`execute_with_setup`'s `managed_keys`. A node that writes an output key on its
active path MUST clear it on every no-op path (`None` for a scalar, the empty
collection for a collection port), or the next execution reads a stale value
(BT-17-003). Example: `CapturePreCommitBackfillTargetNode`
(`case/nodes/invite_ledger_backfill.py`) writes `pre_commit_backfill_target` as
`None` on its no-op path.

- A key the *caller* passes as a `context_data` kwarg is managed and restored; a
  key a node writes mid-tree is not, unless listed in `managed_keys` (next
  section). Name the key form, not the noun: the namespaced
  `suggested_roles_{id_segment}` written by `EvaluateDefaultRolesNode` is
  node-owned and follows this rule, cleared through its port.
- Consumers treat `KeyError` (never written) and `None` (cleared) alike as no-op
  (BT-17-004).
- Regression test: two back-to-back `execute_with_setup` runs on one blackboard,
  second takes the no-op path, assert it sees nothing from the first.

### BT Nodes Must Not Clear Blackboard Keys They Do Not Own

Only the node that writes a key on its active path clears it on its no-op path.
Clearing a shared key such as `BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE` from a
non-producer destroys a value an earlier node in the same Sequence wrote
(CONCERN-2711). The producer side of the rule is in
[received-status-authorization.md](received-status-authorization.md)
§ "Per-dimension partial accept".

---

## Execution-Scoped Hand-off Keys Are Reset by the Bridge, Not by a Node

A key written by one node and consumed by a *later* node in the same run (e.g.
`BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE`, written by `FinalizeCsFilterNode`) cannot be
cleaned by any node on every outcome, because a short-circuiting Sequence may skip
the consumer. List it in `execute_with_setup`'s `managed_keys` so the bridge
restores it in `finally` on every outcome (#3101). Ownership stays with the
producer; *lifetime* is the bridge's.

- `rm_transition_anomaly` (`BB_RM_ANOMALY`) is managed for the same reason:
  `EmitRMGapNoteNode` runs as a refusal effect even when the adjudication guard
  never ran. Tests that inspect it wrap the tree in `RMAnomalyProbe`
  (`test/support/rm_declaration.py`) rather than reading the blackboard afterwards.
- `activity`, `is_leader` and every `context_data` key are added to `managed_keys`
  at the start of `execute_with_setup`, so a nested call restores the outer
  value. Consequently none of them can carry a result out: pass a mutable
  `result_out` dict instead.
- The snapshot/restore lives in `vultron/core/behaviors/blackboard_scope.py`,
  shared with the inbox pipeline. Use it rather than re-implementing: a key absent
  before the call must be *removed* afterwards (not set to `None`, which reads as
  "cleared" under BT-17-003), and both the `/name` and bare spellings are covered.

### `/actor_id` Is Restored Too, Because Nodes Re-Read It Every Tick

`/actor_id` is in `managed_keys`. The `DataLayer*` node bases read it in
`initialise()`, which py_trees calls on every tick in which the node is not
`RUNNING`, so an unrestored inner actor from a nested `execute_with_setup` would
be read by every later sibling — up to a ledger commit's `payloadSnapshot.actor`
(CLP-07-003, #3516). Restoring is safe: the inner call's own `finally` puts back
the value it snapshotted. The general test for "may this key stay un-restored?"
is whether any **node** re-reads it, and when. Guards:
`test_an_inner_actor_id_does_not_clobber_the_outer_one` and
`test_a_later_sibling_reads_its_own_trees_actor` in `test_bridge.py`.

### Every Classifying Exception Handler Is One Helper

Every `BTBridge` handler that builds a result — the tick loop in `execute_tree`
and the `setup_tree`/`execute_tree` phases of `execute_with_setup`, each split by
`VultronError` — goes through `BTBridge._exception_result(e, *, prefix,
internal_error=False)`. The helper derives message, log level and the
`internal_error` flag from one input so they cannot drift (#3080):
`False` → WARNING, no traceback; `True` → `logger.exception` (call it from inside
the `except`). `execute_with_setup` keeps two `try` blocks so the `prefix` names
the phase that failed. Ratchet:
`test/architecture/test_bridge_exception_handlers_use_helper.py`.

---

## Namespaced Inter-Node Handoff Keys

An inter-node handoff key in a tree factory that can run concurrently for several
messages of one type MUST carry the execution-scoped correlation id:
`{noun}_{id_segment}`, where `id_segment` is the last `/`-segment of an HTTP id
(or last `:`-segment of a URN), matching the `object_{id_segment}` keys in
`helpers.py`. A flat key is overwritten by the concurrent instance before the
downstream reader runs (BTND-03-004). When namespacing, audit every `register_key`
in the affected subtree, not only the key the issue names.

---

## Blackboard List Mutation: Write-Back Is Redundant (But Needed for New Lists)

Blackboard values are stored by reference, so mutating a retrieved list updates
the stored value; do not write it back. The write-back IS required when the list
was created fresh in an `except KeyError` branch — it is not stored until assigned.

---

## Always Check `BTBridge.execute_with_setup` Return Value

`execute_with_setup` never raises; it returns `BTExecutionResult(status=FAILURE,
…)`. A node that runs a subtree MUST check `result.status` and fail (raise inside
its `update()` `try`) when it is not `SUCCESS`; ignoring it reports success for a
failed subtree.

### …And That Idiom Is Why `internal_error` Cannot See a Nested Crash

`BTExecutionResult.internal_error` means "an internal error reached the bridge",
never "no bug occurred". The idiom above converts a nested failure into the outer
node's own `FAILURE`, and most nodes running a subtree discard the inner
`internal_error`, so a crash inside a subtree is invisible in the outer result.
`CommitCaseLedgerEntryNode` is the exception: it raises `VultronBTInternalError`
when its nested commit reports `internal_error`, which the bridge classifies as
internal (ADR-0095). Reuse that idiom at any other nested site; until the flag is
propagated everywhere (CONCERN-3019), do not branch on `internal_error is False`
as proof a failure was deliberate. Test-side mirror:
[testing-pitfalls.md](testing-pitfalls.md) § "A FAILURE Test Must Prove the
Harness Can Produce Its Named Reason".

---

## Inner BTBridge Inherits `is_leader` From the Outer Execution's Blackboard

A `BTBridge` built without `is_leader` inherits the callable the enclosing
`execute_with_setup` wrote to `/is_leader`, falling back to `_default_is_leader`
(always True) when there is none; an explicit `is_leader=fn` overrides it. Never
write `/is_leader` from a node — the outer bridge owns it. Without inheritance a
non-leader could mint a `CaseLedgerEntry` through an inner bridge (CLP-08-005,
SYNC-09-003).

---

## Guard Name Must Match the State-Machine Transition Precondition

Derive a guard's condition (and name) from the precondition of the transition it
protects, read from the state machine (`vultron/core/states/cs.py`), not from the
issue's "not yet done" wording. "D bit unset" admits `vfd`/`Vfd`, but `vfd→VFD`
via `TransitionCStoFixDeployed` is valid only from `VFd` — see
`CheckCSFixNotYetDeployed` (#1825).

---

## `NoDataAvailable` Surfaces in `initialise()`, Not `setup_ports()`

`BehaviourWithPorts.get_input()` raises `NoDataAvailable` for an unset port key in
`initialise()`, at the start of the first tick; "early error detection" in
ADR-0044/BTND-03-011 means that point, not "before any tick". A missing-port test
must call `node.initialise()` inside `pytest.raises(NoDataAvailable)`; asserting on
`setup_ports()` passes vacuously.

`get_input()` also raises `TypeError` when the value is not the port's declared
`data_type`, and `_try_get_input()` does not catch it: the whole tree fails via
`BTBridge`. That is deliberate — a violated blackboard type contract is a wiring
error, so it fails closed. See `vultron/core/behaviors/AGENTS.md` § "Port
`data_type` Is Enforced".

---

## Sentinel Blackboard Writes Enable Structured Failure Context for Selector Fallbacks

When a failing node's Selector sibling needs structured context, write sentinel
values before returning `FAILURE`, and make them distinct from every valid value
(e.g. `ReconstructChainTailNode` writes `tail_hash = ""` and `tail_index = -1`
for `SendRejectLogEntryNode`). Outside a Selector with a fallback sibling this is
unnecessary.

---

## Blackboard Bridge Channel for Guard-to-Effect Communication

When a guard must hand structured anomaly context to a later effect node, define a
module-level key constant and have the guard write it on **every** tick — `None`
on normal paths, a typed dict on anomaly paths including FAILURE. Reference:
`BB_RM_ANOMALY` in `vultron/core/behaviors/status/nodes/dimension_filter.py`. An
emission node that needs `self.blackboard` uses `DataLayerAction`;
`DataLayerActionWithPorts` has no `self.blackboard`.

---

## SHOULD-Level Emission Nodes Must Always Return SUCCESS

A node that emits a SHOULD-level side effect (advisory note, audit record,
non-critical notification) MUST return `SUCCESS` even when the emission fails —
log a WARNING. Returning `FAILURE` would abort the Sequence and undo the work the
note describes (ADR-0067, RSH-06-004).

---

## Guarded-Commit BTs Must Execute Under the CASE_MANAGER Actor's Identity

`CheckIsCaseManagerNode` compares the blackboard `actor_id` with the case's
CASE_MANAGER, so a tree containing `GuardedCommitCaseLedgerEntryBT` MUST run as the
**receiving** actor: `resolve_receiving_actor_id(self._dl,
request.receiving_actor_id)` in use cases, `actor_id=case_manager_actor_id` in
tests. Never fall back to `request.actor_id` — that is the sender, and `actor_id`
also selects the store. A node that also needs the sender keeps it as a private
attribute, since `DataLayerAction.setup()` overwrites the blackboard `actor_id`
(BT-17-005, BT-17-006).

## A BT's Store Follows Its Executing Actor

The blackboard `datalayer` is the store of the blackboard `actor_id`
(`BTBridge._store_for_actor`, BT-05-005). Seeding one actor's store and executing
as another reads an empty store, which shows up as a skipped role gate or a "case
not found" warning, not an error. For a role-gated tree, the role holder, the
receiving actor and the store owner must be one actor (BT-05-006).

### The Store Is Not the Subject

Which store a received tree runs in says nothing about whose state it writes. A
received activity is an assertion about the **sender's** state (HP-00-001), so the
subject of every received-side RM write is `request.actor_id` (RSH-08-001). The
receiver's own RM moves on receipt only when it is itself the mover — sender and
receiver coincide, or CM-23-002 has the CASE_MANAGER advance its own participant
on owner departure. When making the subject explicit (BTND-10-005), check that it
is the sender, not merely explicit (CONCERN-3473).

## BT Write Nodes Must Validate Transitions at Their Own Boundary

A node that writes CS/VFD/PXA/EM/RM state MUST validate the transition itself, not
rely on an upstream guard: guards are absent when the node is reused, and several
call sites reach write nodes with no guard (BTND-10-001, BTND-10-003).

- **`ParticipantStatus`** (`rm`/`vf`/`d`/`pxa`): call
  `validate_participant_status_write()` (`behaviors/case/nodes/participant/common.py`),
  which composes `participant_transition_violations()` and reports every
  violation. Never name an individual `is_valid_*_transition()` /
  `violation_*` predicate (BTND-10-002, EH-07-001); enforced by
  `test/architecture/test_participant_status_validation.py`.
- **`CaseStatus` and other dimensions**: call the relevant
  `is_valid_*_transition()` (CSB-16-001 for VFD; CSB-16-002, SM-09-001 for PXA).
- **EM**: route through `EmbargoLifecycle` (EMB-18-001); see
  [embargo-lifecycle.md](embargo-lifecycle.md).

## Never Construct `CreateParticipantStatusNode` Inside Another Node's `update()`

A node constructed inside another's `update()` never gets `setup()`, so its
DataLayer and blackboard wiring are empty, and a surrounding `try/except` swallows
the result. Pre-build the sub-node in `__init__` and run it via
`BTBridge.execute_with_setup(self._status_node, **context)` (BTND-10-004);
enforced by `test/architecture/test_participant_status_validation.py`.

## `CreateParticipantStatusNode` Accepts No `case_id` Constructor Argument

The case id comes only through `CaseIdInputPortMixin`: build-time callers seed it
with `execute_with_setup(node, case_id=...)`, received trees let the node read
`/case_id` at tick time. The subject actor is an explicit constructor argument,
never a fallback to the blackboard `actor_id`, which is the executing actor
(BTND-10-005, ADR-0089). Both are enforced by
`test/architecture/test_participant_status_validation.py`.

## `_mermaid_prefix_map` Is Scoped to the Rendering Node, Not the Named Node

In the simulator's `BtNode.to_mermaid()` (`vultron/bt/base/bt_node.py`), a node's
children are rendered with the **parent's** `_mermaid_prefix_map`. Put a prefix
override on the composite that owns the subtree; one on a leaf has no effect.

## Call-Out Bundle Factories Hand Out Guard-Wrapped Nodes (BT-18-011)

Every `CallOutBundle` factory returns its node wrapped in `SynchronousCallOut`
(applied in `CallOutBundle.__post_init__`). The wrapper is name- and
status-transparent, but a test asserting on the backend's concrete type or
attributes must use `unwrap_call_out(node)`. Code that ticks a factory product
outside a `BTBridge` tree must use `tick_once()` / `setup_with_descendants()`,
never bare `update()` / `setup()` (see `_record_named_peer` in
`use_cases/triggers/actor.py`). Rationale: [protocol-asks.md](protocol-asks.md)
§ "Why there is nothing to suspend" (ADR-0080); bundle
configuration: [call-out-configuration.md](call-out-configuration.md).

---

## A Refusal Arm in a Selector Fails Toward "Admit"

A Selector runs its next child on FAILURE, so any failure inside a *refusal* arm
hands control to the permissive branch. `_EmitSingleActivityBase.update()` turns
every exception into FAILURE, so a missing payload or store error in a decline
arm becomes "proceed with accept" (CP-05-002). No ordering of arms fixes both this
and the reverse error (CLP-10-009).

**Fix with durable state, not structure.** Persist the decision before the side
effect, and make its absence a precondition of the permissive arm:

```text
Selector
  ├─ AlreadyDeclinedArm      # record exists → decision stands; ensure the Reject went out
  ├─ DeclineProposalArm      # Inverter(evaluate) → RECORD → emit
  └─ AcceptProposalArm
       ├─ CheckNoDeclineRecordNode   # FAILURE when the record exists
       └─ <accept flow>
```

This also makes redelivery idempotent (the decision is not re-made), a lost side
effect recoverable ("decided, nothing emitted" is a distinct state, as with
`PendingCreateCaseActivity`, CP-05-005), and the re-emitted reason match the
original.

Rules for the arm:

- **Guards ahead of the durable write let errors propagate.** In a refusal arm a
  guard that cannot answer has no safe status — FAILURE and SUCCESS both admit —
  so it must raise; `BTBridge` turns that into whole-tree FAILURE. This inverts
  BT-HELPER-01 for these nodes.
- **An "already answered" guard covers every state the permissive path leaves
  behind**, probing the earliest durable evidence that it began, not its last
  step.
- **Record the id of what you sent on the decision record.** Neither the store
  ("persisted") nor the outbox ("queued", and popped on delivery) can say whether
  a refusal was sent. Three states: undecided, decided-but-unanswered (re-emit),
  decided-and-answered (emit nothing).
- **Key every guard on the identity of the request being adjudicated**, never on
  a value the sender chooses (such as an embedded `report_id`), and write your own
  per-request evidence before the first effect. A gate keyed on a requester's
  value is one the requester can arrange to skip (#3399). For fixing every member
  of the affected set, see [agentic-workflow.md](agentic-workflow.md)
  § "Enumerate the Affected Set From Its Consumers, Not From the Site the Report
  Names".

---

## Emit and Broadcast Nodes Fail Loudly

- **An emit node in a case-scoped trigger BT resolves the CASE_MANAGER
  recipient before enqueueing** and returns FAILURE when it cannot (PCR-08-011);
  otherwise the miss surfaces later as `VultronOutboxToFieldMissingError`.
- **A peer broadcast node must not mask delivery failure**: it returns FAILURE
  when preparation or enqueueing fails (BT-14-001). See
  [peer-broadcast-failure-semantics.md](peer-broadcast-failure-semantics.md).

---

## A Received Tree Gets Its CASE_MANAGER Gate From the Factory (BT-17-008)

`create_receive_activity_tree` is the one place that applies the CASE_MANAGER
gate; hand-wrapping each tree let new trees leave it out. A received-tree module
never calls `create_case_manager_gated_tree` itself.

- **Two effect kinds.** `replica_effects` run on every replica, ungated;
  `manager_effects` are wrapped in a `CaseManagerGate` on `manager_case_id`
  (separate from the commit's `case_id`, which may be `None`). Stage order:
  intake → guards → commit → `replica_effects` → `manager_effects`.
  `manager_gate_name`, `manager_body_name` and `manager_case_may_be_absent`
  configure the gate.
- **Emit-capable nodes carry `EmitCapable`** (`vultron/core/behaviors/emit_capable.py`).
  The factory raises `VultronWiringError` when a marked node sits in
  `replica_effects` outside every `CaseManagerGate` without a covering exemption.
  Only `create_case_manager_gated_tree` builds a `CaseManagerGate`; the
  participant-replica gate does not count.
- **Ledger replication carries no marker.** Senders through `SyncActivityPort` or
  `create_commit_log_entry_tree` are gated by ledger authority
  (`DeclineForeignLedgerCommitNode`, ADR-0073) and pinned in
  `LEDGER_REPLICATION_SENDERS`.
- **A by-design ungated emit is a named exemption.** `replica_emit_exemption`
  takes a `ReplicaEmitExemption` (`replica_emit_exemptions.py`) with a name, a
  reason and `covers`; the factory refuses an unregistered exemption, an ungated
  emitter outside `covers`, and an exemption covering nothing (stale). A
  migration-only exemption names the issue that deletes it. A sender check is no
  substitute: it says nothing about whether this replica owns the case.
- **Refusal effects are gated too**: `refusal_effects` run only when a guard
  refuses, inside `{name}RefusalIfCaseManager` with `case_may_be_absent=True`
  (CLP-10-022); see [bt-integration.md](bt-integration.md) § "The Four
  Received-Side Stages".
- **`manager_effects` run last, so a step that must follow gated work moves.** If
  the gate and the participant-replica arm partition every receiver, put the step
  at the end of each arm. If the step is also CASE_MANAGER-only, put both in
  `manager_effects` in order. A gated emit inside a branch whose guards cannot be
  re-checked is not split from it — each arm builds the whole branch from one
  helper. Never keep the order with an in-place `Selector[Sequence[check, emit],
  Success]`: it reads a failed emit as a skip (BTND-07-005). A gated subtree a
  use case also runs standalone lives outside the received-tree modules and is
  pinned in `GATE_CALLERS_OUTSIDE_RECEIVED_TREES`.
- **State writes carry `StateWriteCapable`** (RSH-08-003), checked on the built
  tree by `test/architecture/test_received_tree_state_writes_are_gated.py`: a
  marked node outside every `CaseManagerGate` must be in the pinned
  `REPLICA_STATE_WRITES` set. A class reaching a state-write seam (`dl.save`,
  `EmbargoLifecycle`, `apply_pec_transition`, directly or via a helper) carries the
  marker or is pinned in `WRITES_NO_CASE_STATE` with its reason; a leaf that
  builds and ticks a writer itself (`RMClosureWriter`) carries the marker, since
  the walk cannot see the inner write. Move a write into `manager_effects` only
  after its replay slot exists (RSH-08-004).
- **Ratchets**: `test/architecture/test_received_tree_case_manager_gate.py`
  (ARCH-18-001, ARCH-18-005).
