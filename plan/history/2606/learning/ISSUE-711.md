---
source: ISSUE-711
timestamp: '2026-06-11T18:35:36.182595+00:00'
title: Surface domain transition failures from BT action nodes via result channel
type: learning
---

## 2026-06-09 ISSUE-711 — Surface domain transition failures from BT action nodes

- When strict state-machine transitions move into BT action nodes, use cases
  still need original domain exception types (for example
  `VultronInvalidStateTransitionError`) to preserve caller/test semantics.
- A small BT node result channel (`result_out["error"]`) lets the use case
  re-raise lifecycle domain errors directly instead of collapsing everything
  into a generic BT failure message.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"BT Result Channel for Domain Errors" and `AGENTS.md` reference index.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
