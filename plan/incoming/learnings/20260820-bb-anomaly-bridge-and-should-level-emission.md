---
title: "BB_RM_ANOMALY bridge pattern: blackboard key as guard-to-effect channel; SHOULD-level emission nodes always return SUCCESS"
type: learning
timestamp: 2026-08-20
source: ISSUE-2258
signal: design-question
---

## Blackboard bridge pattern

When a guard node detects an anomaly that needs a downstream effect but does
not own the emit responsibility (e.g. it returns FAILURE and the Sequence
aborts), the pattern is:

1. Define a named blackboard key (e.g. `BB_RM_ANOMALY = "rm_transition_anomaly"`).
2. The guard node **always** writes to this key on every tick — clearing it to
   `None` on normal paths and setting a typed dict on anomaly paths (including
   the FAILURE path).
3. A separate effect node later in the Sequence reads the key and acts on it.

The guard and effect nodes share only the key name (defined as a module-level
constant in `dimension_filter.py`). Neither imports the other. This preserves
the single-responsibility principle and the BT node independence invariant.

**Critical detail**: the guard must write the anomaly even on the FAILURE path,
because the Sequence aborts after a FAILURE and the effect node never runs on
that path. The effect node is a best-effort emit placed after other effect
nodes — it will run only on the SUCCESS path (normal or partial-accept). For
the FAILURE path (backward regression on a fully-refused assertion), the anomaly
write in the guard is the only record on the blackboard; it is available to any
node that runs before the next tick clears it.

## SHOULD-level emission nodes always return SUCCESS

Per ADR-0067 and RSH-06-004, `EmitRMGapNoteNode` always returns `SUCCESS`
even when it cannot emit the note (no datalayer, no factory, exception).

Reasoning: the note is advisory — a human-readable record for the operator.
Its absence does not compromise protocol correctness. Returning `FAILURE` would
abort the enclosing Sequence and undo the status adoption that already succeeded,
which would be worse than a missing note.

Rule: any node that emits a SHOULD-level side effect (notes, audit records,
non-critical notifications) must return `SUCCESS` in all cases and degrade
gracefully with a WARNING log. The enclosing tree's correctness must not depend
on it.

## Base class selection for blackboard access in emission nodes

Use `DataLayerAction` (not `DataLayerActionWithPorts`) for nodes that need both
`self.blackboard` (standard py_trees blackboard) and DataLayer access.
`DataLayerActionWithPorts` uses the typed ports interface and does not expose
`self.blackboard`; attempting to call `self.blackboard.get(...)` on it raises
`AttributeError`.
