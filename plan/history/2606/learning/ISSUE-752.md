---
source: ISSUE-752
timestamp: '2026-06-11T18:37:04.387015+00:00'
title: God-node splits must preserve node-local failure semantics for missing blackboard
  keys
type: learning
---

## 2026-06-09 ISSUE-752 — God-node splits should preserve node-local failure semantics

- Decomposing a monolithic BT action into leaf nodes can change failure shape
  if required blackboard keys are read without `KeyError` handling.
- Leaf nodes that require blackboard context should convert missing-key reads
  into explicit node `FAILURE` with a clear error message, not bridge-level
  exception failures.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Decomposed BT Leaf Must Return FAILURE for Missing Blackboard Keys".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
