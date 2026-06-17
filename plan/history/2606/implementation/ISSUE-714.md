---
source: ISSUE-714
timestamp: '2026-06-10T18:14:57.614505+00:00'
title: Decompose CreateCaseActor and owner participant BT nodes
type: implementation
---

## Issue #714 — God node decomposition: split CreateCaseActorNode, InitializeDefaultEmbargoNode, CreateCaseOwnerParticipant, and BroadcastStatusToPeersNode into composed subtrees

Completed the in-scope decomposition for `CreateCaseActorNode` and `CreateCaseOwnerParticipant` as composed BT subtrees with named leaf nodes, preserving idempotency and call-path compatibility. Added unit coverage for subtree structure and owner RM advancement behavior.

PR: [#887](https://github.com/CERTCC/Vultron/pull/887)
