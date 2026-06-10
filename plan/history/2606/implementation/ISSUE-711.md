---
source: ISSUE-711
timestamp: '2026-06-09T15:34:45.378118+00:00'
title: Trigger embargo BT action-node integration
type: implementation
---

## Issue #711 — Trigger-side state machine BT integration: move EM/PEC transitions out of execute() into BT Action nodes

Implemented trigger-side embargo BT integration for propose/accept/reject/terminate flows by adding dedicated embargo lifecycle BT action nodes and trigger trees, then routing the four `Svc*EmbargoUseCase` paths through `BTBridge` + those trees.

This preserves strict EmbargoLifecycle transition semantics while ensuring the state-machine transition path is represented as BT actions before outbound sender fan-out.

Added trigger-use-case coverage for propose and terminate paths in `test/core/use_cases/triggers/test_embargo.py`, so all four trigger embargo use cases now execute through BT-covered paths.

PR: [#841](https://github.com/CERTCC/Vultron/pull/841)
