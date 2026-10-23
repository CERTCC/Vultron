---
source: SINGLE-BT-1050
timestamp: '2026-06-22T19:35:59.410867+00:00'
title: Single-BT-execution test must use unique blackboard namespace per run
type: learning
---

The architecture ratchet `test_single_bt_execution_received_side.py` verifies
that each received-side use case calls `execute_with_setup` exactly once. When
this test runs against multiple use cases in the same pytest session, stale
`actor_id` / `datalayer` keys from a previous test can make a new test's
setup appear successful even when blackboard injection fails — causing a
false-positive. Isolate each test case with a fresh `py_trees.blackboard.Blackboard.enable_activity_stream()`
call and clear the blackboard in a `yield`-style fixture. Map the fixture
identity (actor ID) to a unique mock DL instance so the assertion
`dl.save.call_count == 1` can be attributed correctly.

**Promoted**: 2026-06-22 — captured in `specs/behavior-tree-integration.yaml`
(BT-17-005: guarded-commit test identity) and `AGENTS.md` (Single BT Test
pitfall).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
