---
title: BT Pitfalls and Debugging Notes
status: active
description: >
  Per-pitfall debugging notes for py_trees BT integration: failure reason
  propagation, blackboard lookup semantics, idempotency patterns, role guards,
  memory=False sequence semantics, blackboard key namespacing, and other
  commonly encountered BT implementation pitfalls.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-design-patterns.md
relevant_packages:
  - py_trees
  - vultron/bt
  - vultron/core/behaviors
---

# BT Pitfalls and Debugging Notes

> See also: [bt-integration.md](bt-integration.md) for design decisions and
> [bt-canonical-reference.md](bt-canonical-reference.md) for the canonical BT structure.

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
Sequence node's own `feedback_message` is always `""`. Logging
`result.feedback_message` or `bt.root.feedback_message` after a BT failure
therefore produces an empty string, not the diagnostic message set by the
failing child. Always use `BTBridge.get_failure_reason(tree)` (depth-first walk
to the first failing leaf) to get a meaningful message. Apply this pattern
**everywhere** `feedback_message` is logged after a BT failure — not just for
a single BT class.

---

## AttachNoteToCase Idempotency: Check Attachment, Not Existence

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

## Closing Bugs with Concrete Evidence

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

## Lenient vs. Strict Participant Lookup Node Variants

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
no `self.feedback_message` set (see
`core/behaviors/case/nodes/communication.py` `_read_case_obj()` for the
canonical pre-ADR-0032 anti-pattern). Helpers are clean typed functions;
`update()` owns the failure-to-`Status` translation. See ADR-0032.

---

## Embargo Subtree Idempotency with Blackboard Flag

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
blackboard keys (`new_case_participant`, `participant_case`,
`new_participant_id`). This makes each leaf independently testable and the
overall flow readable from the tree structure alone.

---

## Guarded Commit: Role-Gated Canonical Writes

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

## Fan-out / SYNC Decomposition: Context Handoff Pattern

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

## Inbox Test Seam Must Preserve Production Deferral Semantics

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

## Role Guard Required for All CASE_MANAGER-Only BT Subtrees

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

## Module-Level Idempotency Sets Must Be Paired with a Role Guard

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

## `memory=False` Sequence: Partial-Write Behavior on FAILURE

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

## No-Op Path Must Clear Output Blackboard Keys

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

## Routing-Gated State Mutation

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

## Demo Devlog Race: Wait for Replica Before Dumping

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

## Integration Tests Must Use Deterministic Factories When BT Default Is Probabilistic

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

## Namespaced Inter-Node Handoff Keys

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

## Blackboard List Mutation: Write-Back Is Redundant (But Needed for New Lists)

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

## Ledger Commit Must Precede Outbox Write

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

## Use `disposition="rejected"` for Local-Only Ledger Correlation Markers

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

## suggest-actor Accept Path Does Not Thread Roles Into Invite

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

## BTND-03-004 Audit Scope: All Keys in the Subtree

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

## Production Collapse (FUZZ-08x): Use the Prior Collapse as a Concrete Template

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

## Dual-Path Consolidation Test Gap

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
