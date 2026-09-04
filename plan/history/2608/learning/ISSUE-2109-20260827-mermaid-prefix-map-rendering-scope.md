---
title: BtNode._mermaid_prefix_map is scoped to the rendering node, not the named node
type: learning
timestamp: "2026-08-27T00:00:00Z"
source: ISSUE-2109
signal: theme-candidate
---

`BtNode.to_mermaid()` defines `fixname()` as a closure that reads
`self._mermaid_prefix_map` — the map on the node that called `to_mermaid()`,
not on the node whose name is being rendered. This means:

- If `ParentSeq` overrides `_mermaid_prefix_map["c"] = "CHECK: "`, all
  `ConditionCheck` children rendered *by ParentSeq* use `"CHECK: "`.
- If a leaf `ConditionCheck` overrides its own map, the override has no effect
  when its name is rendered by a parent — the parent's map is used.

**Why:** `fixname(child.name)` is called from within the parent's method
context, so `self` is the parent. This is consistent with how `to_mermaid()`
composes recursively: each node controls the rendering of its direct children.

**How to apply:** When adding a `_mermaid_prefix_map` override to customise
display, place it on the *composite* (non-leaf) node that owns the subtree, not
on the leaf nodes whose names should change.

---

**Promoted**: 2026-09-03 — captured in `notes/bt-pitfalls.md` ("`_mermaid_prefix_map` Is Scoped to the Rendering Node, Not the Named Node"). Docs PR: <https://github.com/CERTCC/Vultron/pull/3147>.
