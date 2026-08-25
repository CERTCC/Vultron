---
title: "py_trees blackboard.get() raises KeyError on unset registered READ key"
type: learning
timestamp: "2026-07-27T00:00:00Z"
source: ISSUE-1716
signal: concern
---

`py_trees.Blackboard.get(key)` raises `KeyError` (not returns `None`) when the
key has been registered with `READ` access but has not yet been written by any
node.  `EmitCloseCaseNode` hit this in code review — the `if not case_manager_id:`
guard was unreachable and the `KeyError` would propagate uncaught.

Fix applied in ISSUE-1716: wrap `blackboard.get()` in `try/except KeyError`.

The same footgun exists anywhere `DataLayerAction.setup()` registers READ keys
and `update()` calls `blackboard.get()` without guarding.  A systematic audit of
all `register_key(..., access=Access.READ)` sites would catch latent bugs of this
form — worth a Concern issue targeting `behaviors/` BT nodes.

**Promoted**: 2026-07-28 — captured in vultron/core/behaviors/AGENTS.md § Blackboard.get() Raises KeyError.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1790>0>0>0>0>0>0>.
