---
title: TASK-RFC-401 BTTestScenario deep-module test harness
type: implementation
timestamp: '2026-04-30T19:06:09+00:00'

source: TASK-RFC-401
---

Created `test/core/behaviors/bt_harness.py` with `BTTestScenario` class and
three pytest fixtures (`bt_scenario`, `bt_scenario_factory`, `shared_dl_actors`).
Rewrote `test/core/behaviors/report/test_nodes.py` and
`test/core/behaviors/case/test_nodes.py` to eliminate duplicated
`setup_node_blackboard()` boilerplate and direct `node.update()` calls,
routing all BT execution through `BTBridge.execute_with_setup()`.
Updated `test/core/behaviors/conftest.py` to export harness fixtures.
1991 tests passing. Resolves GitHub issue #401.
