---
source: Priority-360
timestamp: '2026-04-23T00:00:00+00:00'
title: 'Priority 360: BT composability audit (IDEA-26041703)'
type: priority
---

Addresses the deeper concern from IDEA-26041703: BT nodes and subtrees should
be composable, reusable branches rather than one-off behaviors hard-coded to
specific actors or demo scenarios. The "fractal" composition pattern in
`vultron/bt/` is the intended model.

Deliverables:

- `notes/bt-reusability.md` — durable design note capturing the fractal
  composability pattern, the "trunkless branch" intent, and anti-patterns
  to avoid.
- `specs/behavior-tree-node-design.yaml` — formal requirements for BT node
  parameterization, composability, and reuse (e.g., nodes MUST NOT hard-code
  actor roles; roles/identities MUST be constructor parameters; reusable
  subtrees MUST be composed rather than duplicated).
- Codebase audit: identify one-off BT nodes or near-duplicate subtrees that
  should be refactored to use the composability pattern; produce a task list.

Can begin in parallel with P-347.