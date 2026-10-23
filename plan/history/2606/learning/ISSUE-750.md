---
source: ISSUE-750
timestamp: '2026-06-11T18:35:18.150212+00:00'
title: Embargo subtree decomposition must preserve idempotent side effects
type: learning
---

## 2026-06-08 ISSUE-750 — Embargo subtree decomposition must preserve idempotent side effects

- Decomposing a god node into sequential BT leaves can silently change
  duplicate-run behavior when side-effect leaves always execute.
- Preserve previous semantics explicitly with a blackboard flag that tracks
  whether the current execution actually initialized a new embargo.
- When moving EM transition logic to `EmbargoLifecycle.propose_embargo`,
  keep event creation and participant-seeding behavior aligned with existing
  duplicate-report tests to avoid introducing warning-level regressions.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Embargo Subtree Idempotency with Blackboard Flag".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
