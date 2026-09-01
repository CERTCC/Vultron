---
title: "Design decision: a violated port data_type fails the whole tree, not the one node"
type: learning
timestamp: 2026-09-01T22:50:00Z
source: ISSUE-2907
signal: design-question
---

Tightening a port from `data_type=object` to a concrete class changes the
failure mode for a wrong-typed blackboard value, and the change is larger than
it looks.

`get_input()` raises `TypeError`. `_try_get_input()`
(`vultron/core/behaviors/helpers.py`) catches only `NoDataAvailable` and
`NotImplementedError`, so the `TypeError` escapes `initialise()`.
`py_trees.behaviour.Behaviour.tick()` calls `initialise()` outside any
try/except, so the exception unwinds the tick and is absorbed by
`BTBridge.execute_tree`'s blanket `except Exception` — the **whole tree**
returns `BTExecutionResult(status=FAILURE)` with the type-mismatch message
logged. A node that previously ignored a junk value it never dereferenced (e.g.
`AdvanceOwnerRmToAcceptedNode` when `/case_id` was set) now takes its enclosing
Selector's fallback branch out of reach.

**Decision**: leave `_try_get_input()` alone. A violated blackboard contract is
a wiring/programming error, not a protocol condition, so failing closed and
loudly is the right outcome; and it is already the behavior of the seven ports
hardened by #2909, so the alternative would mean changing those too.

**Why the obvious alternative is wrong**: catching `TypeError` in
`_try_get_input()` and returning `None` would make a corrupt value
indistinguishable from an absent one. Several callers treat `None` as "not
supplied" and proceed, which is precisely the silent-degradation bug ARCH-15
forbids ("Silent `None` Returns and Fake `SUCCESS` Are the Same Bug"). If the
node-local `Status.FAILURE` shape is wanted instead, it has to be an explicit
failure signal, not a `None`.

**Decide this once, before the next sweep.** `_try_get_input` is shared by
~150 nodes, so the choice is not per-port. The tension is real: the project
convention is that BT nodes return `FAILURE` rather than raise
(`notes/bt-pitfalls.md` § BT-HELPER-01), and an uncaught exception unwinding
the tick is a cruder instrument than a logged `FAILURE` with a feedback
message. The counter-argument is that a tree whose data contract is broken has
no correct partial outcome to report.

Related: [[20260901-2907-port-data-type-object-corpus-wide]] (the remaining
sites a sweep would touch),
[[20260831-2490-blackboard-cast-design-question]] (the `cast()` decision that
made the declaration load-bearing).
