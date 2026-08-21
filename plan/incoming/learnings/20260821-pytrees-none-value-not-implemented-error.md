---
title: py_trees raises NotImplementedError when blackboard stores explicit None
type: learning
timestamp: "2026-08-21"
source: ISSUE-1885
signal: spec-gap
---

When a blackboard client stores an explicit `None` value (e.g. `bb.datalayer = None`)
and a typed-Ports node calls `self.get_input("datalayer")`, py_trees raises:

```text
NotImplementedError: Support for None values has not yet been considered.
```

This is an upstream py_trees limitation in `ports.py:635`. Our base classes
(`DataLayerConditionWithPorts.initialise()` and `DataLayerActionWithPorts.initialise()`)
now catch `NotImplementedError` and set the attribute to `None`, so
`_require_datalayer()` in `update()` handles the missing-datalayer case as FAILURE.

No spec entry covers this pattern. Consider adding a BTND-03 or BTND-10 note
clarifying that `initialise()` must handle `NotImplementedError` from `get_input()`
alongside `NoDataAvailable`, and that explicit-None blackboard values are treated
as "not available" for required base ports.

The fix is in `helpers.py:848` and `helpers.py:931`.
