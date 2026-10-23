---
source: ISSUE-751
timestamp: '2026-06-11T18:35:45.019724+00:00'
title: Conditional BT branches can replace inline node if logic as Selector composite
type: learning
---

## 2026-06-09 ISSUE-751 — Conditional BT branches can replace inline node if logic cleanly

- For god-node decomposition, represent optional behavior as an explicit
  `Selector` subtree (`active-branch` then `no-active` guard) instead of inline
  branching in a single `update()` method.
- Blackboard handoff keys (`new_case_participant`, `participant_case`,
  `new_participant_id`) make each leaf independently testable while preserving
  end-to-end behavior.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Conditional BT Branches as Selector Composites".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
