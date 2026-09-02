---
title: BT Cross-Cutting Mechanics
status: active
description: >
  Cross-cutting mechanics for py_trees BT integration: failure reason
  propagation, blackboard key semantics, idempotency patterns,
  memory=False partial-write behavior, key namespacing, and other
  mechanics that apply to any BT node or domain.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-design-patterns.md
  - notes/embargo-lifecycle.md
  - notes/received-status-authorization.md
  - notes/testing-pitfalls.md
relevant_packages:
  - py_trees
  - vultron/core/behaviors
---

# BT Cross-Cutting Mechanics

> See also: [bt-integration.md](bt-integration.md) for design decisions and
> [bt-canonical-reference.md](bt-canonical-reference.md) for the canonical BT
> structure. Domain-specific pitfalls live in per-directory `AGENTS.md` files
> under `vultron/core/behaviors/`.

## BT Failure Reason Propagation

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
Sequence node's own `feedback_message` is always `""`. Always use
`BTBridge.get_failure_reason(tree)` (depth-first walk to the first failing
leaf) to get a meaningful message. Apply this pattern **everywhere**
`feedback_message` is logged after a BT failure — not just for a single BT
class.

---

## py_trees `blackboard.get()` Raises KeyError for Unwritten READ Keys

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
   development: the class body of one node was accidentally embedded *inside*
   another. Python resolves to the *last* definition, so the correct `update()`
   was silently replaced. The embedded `setup()` only registered one key, so
   `get()` for the missing key was never called, and the node returned `SUCCESS`
   for the wrong reason.

**Rules**:

- Use `Blackboard.storage.get("/key")` (with the leading `/` prefix that
  py_trees uses internally) only in tests to inspect raw storage — never in
  production node code.
- In production `update()`, use `self.blackboard.get(key)` knowing it will
  raise if the key is unset. Guard with an explicit `try/except KeyError` or
  ensure the key is always written before being read.
- When a new node class is added to a file, **always verify class boundaries
  with `grep -n "^class " <file>`** before committing.

---

## BT Result Channel for Domain Errors

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

## Decomposed BT Leaf Must Return FAILURE for Missing Blackboard Keys

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

## BT-HELPER-01 — Helpers Raise; `update()` Catches

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
no `self.feedback_message` set. Helpers are clean typed functions;
`update()` owns the failure-to-`Status` translation. See ADR-0032.

For the note-specific partial-write worked example, see
`vultron/core/behaviors/note/AGENTS.md` § "`memory=False` Note Sequence".

---

## Conditional BT Branches as Selector Composites

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
blackboard keys. This makes each leaf independently testable and the overall
flow readable from the tree structure alone.

---

## Decomposed BT Nodes Must Preserve Alternate Context Seams

(ISSUE-714, 2026-06-10)

When replacing a god node with a leaf-node sequence, preserve all input
seams the original node accepted:

- `case_id` from a blackboard key
- `case_obj`-derived context set during setup

If downstream leaves rely on blackboard keys written during setup, add
explicit fallback reads from staged objects/status context to avoid
regressing call paths that provide context in one form but not the other.

---

## Use DataLayer Outbox for Idempotency, Not Module-Level Sets

(Resolved pattern — the former `AutoCloseBranchNode` used a module-level
`_auto_close_triggered: set[str]` that was replaced in PR #1724 by a
`CloseNotYetEmittedConditionNode` that queries the DataLayer outbox.)

A module-level `set[str]` used to prevent duplicate fires is **per-process**,
not per-container. In a Docker deployment, vendor-1 and finder-1 each have
separate Python processes with separate sets. Furthermore, within a single
process, two fires can race: if a phantom fire (wrong actor) runs first and
claims the slot, the legitimate fire (correct actor) is silently skipped.

**Fix**: Use a `DataLayerCondition` node that queries the DataLayer outbox for
an existing activity, not a module-level set. This survives process restarts
and is visible to the BT audit trail.

---

## `memory=False` Sequence: Partial-Write Behavior on FAILURE

(BTND07-913, 2026-06-15; see `specs/behavior-tree-node-design.yaml` BTND-07-001)

A `Sequence(memory=False)` re-evaluates all children from the start on each
tick. If an early child succeeds but a later child fails, the early child's
side effects **have already been committed**. The Sequence as a whole returns
FAILURE, but local state written by the successful earlier children persists.

**Design implication**: When using `memory=False` sequences for partially-
reversible operations, document which steps are non-transactional and what
state is committed if a later step fails. Tests MUST assert partial-write
behavior explicitly so future readers do not assume FAILURE → no writes
occurred.

For the note-domain worked example, see
`vultron/core/behaviors/note/AGENTS.md` § "`memory=False` Note Sequence".

---

## No-Op Path Must Clear Output Blackboard Keys

(ISSUE-834, 2026-06-18; see `specs/behavior-tree-integration.yaml` BT-17-003,
BT-17-004)

`py_trees.blackboard.Blackboard.storage` is process-global. `execute_with_setup`
cleans only the `datalayer` and `trigger_activity_factory` keys on exit — it
does NOT clean domain-specific output keys such as `broadcast_activity_id`.

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
treat both `KeyError` (key never written) and `None` (key explicitly cleared
by no-op path) as equivalent no-op sentinels.

**Regression test pattern**: Add a test that runs two `execute_with_setup`
calls back-to-back on the same blackboard instance without clearing between
them. Assert the second run does not observe output values from the first when
the producer node takes a no-op path.

---

## Namespaced Inter-Node Handoff Keys

(CONCERN-1335, 2026-07-10; see `specs/behavior-tree-node-design.yaml` BTND-03-004)

The py_trees blackboard is **process-global**. When a tree factory function is
called for two concurrent incoming messages of the same type, both tree
instances write to the same flat blackboard namespace. A node in instance A that
writes `suggested_roles` will have that value overwritten by instance B before
instance A's downstream consumer reads it — causing silent data corruption.

**Pattern**: Any BT node that writes an inter-node handoff key MUST include
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

**Key derivation convention**: `{noun}_{id_segment}` where `id_segment` is
`correlation_id.split("/")[-1]` for HTTP URIs, or the last colon-delimited
segment for URN IDs. This matches the existing `object_{id_segment}` pattern
used by `WriteObjectToBBNode` / `ReadObjectFromBBNode` in `helpers.py`.

**When this applies**: Any inter-node handoff key in a tree factory that may
realistically be called with multiple concurrent executions — i.e., where the
factory is called per-incoming-message for a message type that can arrive in
bursts (offer/accept/reject workflows in particular).

**Known instances** (catalogue for conformance audits):

| Key(s) | Tree factory | Correlation ID | Discovered |
|---|---|---|---|
| `suggested_roles` | `create_recommend_actor_to_case_received_tree` | `recommendation_id` | CONCERN-1335 |
| `new_case_participant`, `participant_case`, `new_participant_id` | `create_receive_report_case_tree` | `report_id` | CONCERN-1349 |

### BTND-03-004 Audit Scope: All Keys in the Subtree

(ISSUE-1397, 2026-07-14)

When namespacing blackboard keys per BTND-03-004, audit ALL
`register_key` calls within the affected composite subtree — not just the
keys named in the issue body.

**How to audit**: grep for `register_key` across the affected module, list
every key, then check whether each one crosses a concurrent-execution
boundary. Keys that are always cleaned up and rewritten before being read
within a single `Sequence(memory=False)` are low-risk, but namespacing
eliminates the risk entirely and is cheap.

---

## Blackboard List Mutation: Write-Back Is Redundant (But Needed for New Lists)

(ISSUE-1374, 2026-07-13)

py_trees stores blackboard values by reference. Mutating a list retrieved from
the blackboard updates the stored value in place — any subsequent reader sees
the change without a write-back.

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

## Always Check `BTBridge.execute_with_setup` Return Value

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

## Guard Name Must Match the State-Machine Transition Precondition

(ISSUE-1825, 2026-07-30)

When naming a guard node, derive the name from the state(s) that the guarded
action's state-machine transition actually requires — not from the informal
description of "not yet done" in the issue AC.

**Anti-pattern**: AC says "Create `CheckCSFixNotYetDeployed` guard." Read
literally, that name only requires the `D` bit to be unset, which is true for
`vfd`, `Vfd`, and `VFd`. But the transition the guard protects (`vfd→VFD` via
`TransitionCStoFixDeployed`) is only valid from `VFd`. Implementing the guard
as "D is unset" allows an invalid `vfd → VFD` jump.

**Rule**: Before implementing a guard node, look up the state-machine
transition the guarded action performs and use that transition's domain
precondition as the guard's correctness criterion. Name the node to reflect
the specific state required (e.g., `CheckCSFixReadyNotDeployed` — VFd
specifically), not the weaker absence predicate. Catching this requires reading
`vultron/core/states/cs.py` `_vfd_transitions`, not just the AC text.

<!-- Source: ISSUE-1825 -->

---

## `_resolve_case_manager_id` Is Duplicated in `develop_fix.py` — Do Not Canonicalise Yet

(ISSUE-1812, 2026-07-29; tracked for unification in #1428)

`vultron/core/behaviors/report/nodes/develop_fix.py` contains a local copy of
`_resolve_case_manager_id` that mirrors the canonical version in
`vultron.core.use_cases._helpers`. This duplication was deliberate: BT nodes
in `vultron/core/behaviors/` cannot import from `vultron/core/use_cases/`
(BTND-04-003), and no shared `core.behaviors` helper location exists yet.

**Do not unify or move these helpers until #1428 is addressed.** Adding a
shared helper module under `vultron/core/behaviors/` is a design decision
requiring an ADR or spec entry. Until then, keep the inlined copy — it is not
tech debt to fix in the same PR.

<!-- Source: ISSUE-1812 -->

---

## `NoDataAvailable` Surfaces in `initialise()`, Not `setup_ports()`

(ADR-0044 / BTND-03-011, 2026-07-29)

`py_trees.behaviour.BehaviourWithPorts` raises `NoDataAvailable` when
`get_input()` is called for a port whose blackboard key has no value. This
happens in `initialise()` at the **start of the first tick** — not in
`setup_ports()` or `setup()`.

**ADR-0044 and BTND-03-011 use "early error detection" to mean "at
`initialise()`, before the main `update()` logic"** — not "before any tick."

**Test pattern for missing-required-port coverage**:

```python
# ❌ Wrong — setup_ports() does not raise; test passes vacuously
node.setup_ports()

# ✅ Correct — the raise happens in initialise()
node.setup_ports()  # register keys; blackboard is still empty
with pytest.raises(py_trees.blackboard.timebomb.NoDataAvailable):
    node.initialise()  # calls get_input() → raises here
```

<!-- Source: ISSUE-1808; spec: BTND-03-011; ADR: ADR-0044 -->

---

## Sentinel Blackboard Writes Enable Structured Failure Context for Selector Fallbacks

When a py_trees Sequence needs a fallback action on node failure, the standard
Selector pattern only works cleanly if the failing node leaves the blackboard
in a usable state for its sibling.

**Pattern**: write sentinel values to the blackboard **before** returning
`Status.FAILURE`. The sibling fallback node in the enclosing Selector can then
read those sentinel values and act on structured failure context rather than
empty keys.

```python
# Example: ReconstructChainTailNode writes sentinels before failing
# so the sibling SendRejectLogEntryNode can compose a well-formed Reject.
self.blackboard.tail_hash = ""    # sentinel: distinct from any valid 64-char hash
self.blackboard.tail_index = -1   # sentinel: distinct from any non-negative index
return Status.FAILURE
```

**Safety rule**: sentinel values MUST be semantically distinct from all valid
data so that downstream consumers can distinguish "node failed" from "node
succeeded with this value".

**When not to use this pattern**: if the failing node is not inside a Selector
that has a fallback sibling, writing sentinel values is unnecessary overhead.

<!-- Source: ISSUE-1873 -->

---

## Blackboard Bridge Channel for Guard-to-Effect Communication

(ISSUE-2258, 2026-08-20)

When a guard node detects an anomaly and needs to communicate structured
context to a downstream effect node — but returns `Status.FAILURE` so the
Sequence aborts before the effect node runs — use the blackboard as an
explicit channel:

1. Define a module-level constant for the key (e.g.
   `BB_RM_ANOMALY = "rm_transition_anomaly"`).
2. The guard node writes to this key on **every** tick: `None` on normal
   paths, a typed dict on anomaly paths, **including the FAILURE path**.
3. The effect node reads the key. It runs only on the SUCCESS path of the
   Sequence; on FAILURE it never runs.

**Base class**: use `DataLayerAction` (not `DataLayerActionWithPorts`) for
emission nodes that need both `self.blackboard` (standard py_trees blackboard)
and DataLayer access. `DataLayerActionWithPorts` does not provide
`self.blackboard`; calling `self.blackboard.get(...)` on it raises
`AttributeError`.

See `vultron/core/behaviors/status/nodes/dimension_filter.py` for the
reference implementation. *Source: ISSUE-2258*

---

## SHOULD-Level Emission Nodes Must Always Return SUCCESS

(ADR-0067, RSH-06-004, 2026-08-20)

Any BT node that emits a SHOULD-level side effect — advisory notes, audit
records, non-critical notifications — MUST return `Status.SUCCESS` in all
cases, including when the emission fails (no DataLayer, no factory, exception).

**Why:** The note is advisory. Returning `FAILURE` would abort the enclosing
Sequence and undo the status adoption that already succeeded — a worse outcome
than a missing note. Protocol correctness MUST NOT depend on SHOULD-level
emissions.

**Pattern:** wrap the emission in a try/except, log a WARNING on failure, and
always return `Status.SUCCESS`.

```python
def update(self) -> Status:
    try:
        self._emit_note()
    except Exception as exc:
        logger.warning("Could not emit note: %s", exc)
    return Status.SUCCESS
```

<!-- Source: ISSUE-2258, ADR-0067 -->

---

## py_trees Class Registry: BT Subclasses Must Be Module-Level in Tests

(CONCERN-2321, 2026-08-26)

py_trees maintains a global class registry. When a `BT` subclass is defined
**inside** a test function (as a local class), it is registered globally by
class name. If two test functions define a local class with the same name (e.g.,
`MyBT`), the second definition clobbers the first in the registry. Trees built
from the first definition then resolve to the wrong class.

**Rule**: All py_trees `BT` subclasses used in tests MUST be defined at
**module level**, never inside test functions or fixtures.

```python
# ❌ WRONG — local class, clobbers registry if another test defines 'MyBT'
def test_something():
    class MyBT(py_trees.behaviours.Behaviour):
        def update(self): return py_trees.common.Status.SUCCESS
    ...

# ✅ CORRECT — module-level definition, stable registry entry
class _MyBT(py_trees.behaviours.Behaviour):
    def update(self): return py_trees.common.Status.SUCCESS

def test_something():
    node = _MyBT()
    ...
```

**Convention**: prefix module-level test-only classes with `_` to signal
they are not part of the public test API.

---

## `_on_success()` Must Be Outside the Try Block

(CONCERN-2321, 2026-08-26)

In BT nodes that use the `BT-HELPER-01` pattern (helpers raise; `update()` catches),
`_on_success()` or any success-path side-effect helper MUST be called **outside**
the `try` block — after the logic that can raise has completed:

```python
# ❌ WRONG — _on_success() inside try block; exception from side-effect
# is caught by the wrong handler
def update(self) -> Status:
    try:
        result = self._do_work()
        self._on_success(result)   # inside try — wrong
        return Status.SUCCESS
    except BtNodePreconditionError as e:
        self.feedback_message = str(e)
        return Status.FAILURE

# ✅ CORRECT — success-path side-effect outside the try block
def update(self) -> Status:
    try:
        result = self._do_work()
    except BtNodePreconditionError as e:
        self.feedback_message = str(e)
        return Status.FAILURE
    self._on_success(result)   # outside try — correct
    return Status.SUCCESS
```

**Why it matters**: if `_on_success()` raises unexpectedly (e.g., DataLayer
error), placing it inside the `try` block causes the `except BtNodePreconditionError`
handler to swallow it silently, returning `FAILURE` with a misleading
`feedback_message` rather than propagating the real error.

## Guarded-Commit BTs Must Execute Under the CASE_MANAGER Actor's Identity

`CheckIsCaseManagerNode` compares the *blackboard* `actor_id` against the case's
CASE_MANAGER participant. Any code that calls `execute_with_setup` for a BT
containing `GuardedCommitCaseLedgerEntryBT` MUST pass the *receiving* actor's ID
(e.g. `request.receiving_actor_id`), NOT the sender's (`request.actor_id`). This
applies to production received-side use cases and to tests alike.

In tests, use `actor_id=case_manager_actor_id`; in received-side use cases, use
`resolve_receiving_actor_id(self._dl, request.receiving_actor_id)`, which falls
back to the **store's own actor** when the field is absent and raises when
neither source yields one. Do **not** fall back to `request.actor_id`: that is
the sender, and since `actor_id` now selects the store, using it routes every
read and write into an actor other than the one whose replica is being updated.

BT nodes that also need the *sender* ID must store it as a private attribute
(e.g. `self._target_actor_id`); `DataLayerAction.setup()` will overwrite the
blackboard `actor_id`, and a stored attribute is the only safe way to keep it.
See BT-17-005, BT-17-006, BT-05-006.

Sources: ISSUE-2300, ISSUE-2238

## A BT's Store Follows Its Executing Actor

The blackboard `datalayer` is the store of the blackboard `actor_id`, reconciled
in `BTBridge._store_for_actor` (BT-05-005). Seeding one actor's store and
executing as another therefore leaves the tree reading an empty one: the symptom
is a role gate that skips, or a "case not found" warning — not an error. Where a
tree is role-gated, the role holder, the receiving actor and the store owner must
be **one** actor (BT-05-006); letting any two drift is a silent skip.

Source: ISSUE-2238

## BT Write Nodes Must Validate Transitions at Their Own Boundary

A BT node that writes CS/VFD/PXA/EM/RM state MUST call the relevant
`is_valid_*_transition()` function inside the write node itself, not only in
upstream guard or condition nodes. Upstream guards can be absent or bypassed when
the write node is reused in a new tree. For VFD writes see CSB-16-001; for PXA
writes see CSB-16-002 and SM-09-001; for EM writes route through
`EmbargoLifecycle` (EMB-18-001). See
[notes/embargo-lifecycle.md](embargo-lifecycle.md).

Source: CONCERN-2412

## BT Nodes Must Not Clear Blackboard Keys They Do Not Own

A node's `_clear()` or tick-start zero-write MUST only target keys that node is
the sole producer of. Clearing a shared global key (e.g.
`BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE`) in a node that is not its producer silently
destroys a value written by an earlier node in the same Sequence, even when the
clear runs for BT-17-003 compliance.

Ownership rule: **the node that writes the key on its active path is the sole
node that clears it on its no-op path.** The complementary requirement — that a
producer MUST clear its own key on every no-op tick — is in
[notes/received-status-authorization.md](received-status-authorization.md)
§ "Per-dimension partial accept".

Source: CONCERN-2711
