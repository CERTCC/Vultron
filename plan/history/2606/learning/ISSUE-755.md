---
source: ISSUE-755
timestamp: '2026-06-11T18:37:28.414841+00:00'
title: SYNC god-node decomposition works best as context handoff leaves
type: learning
---

## 2026-06-10 ISSUE-755 — SYNC god-node decomposition works best as context handoff leaves

- For replay/fan-out flows, split nodes around blackboard context boundaries:
  collect context, derive index/recipients, then perform side effects.
- Condition+action hybrid nodes are clearer and safer as `Selector` composites:
  a pure condition leaf first, then side-effect action fallback.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Fan-out / SYNC Decomposition: Context Handoff Pattern".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
