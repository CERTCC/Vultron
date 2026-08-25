---
title: "py_trees BehaviourWithPorts subclasses must not be defined inside test functions"
type: learning
timestamp: "2026-08-25"
source: ISSUE-2582
signal: tooling-issue
---

`py_trees.ports.BehaviourWithPorts.__init_subclass__` registers each subclass
by its `__name__` in a global class-tag registry. If a BT node class is
defined **inside a test function or factory method** (dynamically each call),
py_trees raises:

```text
UserWarning: Ports class tag '_TestEmitNode' is already registered ...
  overriding with '_TestEmitNode' (last wins).
```

Worse, with pytest, this causes a `FAILED` result even on a technically
passing test when the warning becomes an error.

**Rule**: BT subclasses used in tests must be defined at **module level**
(or in a class body), never inside a function or closure. Instance-level
variation is achieved by setting instance attributes (e.g.,
`node.factory_fn = lambda ...`) rather than creating a new class per test.

This was found when writing `_StubEmitNode` for `TestEmitSingleActivityBase`.
The fix was to move from a `make_node()` factory (defining a new `_TestEmitNode`
class on each call) to a single module-level `_StubEmitNode` class whose
behaviour is controlled via `node.factory_fn` and `node.on_success_fn`
instance attributes.
