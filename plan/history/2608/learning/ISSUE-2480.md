---
title: test_demo_completes_under_5_seconds is flaky at the 5s boundary
type: learning
timestamp: 2026-08-26T19:10:00Z
source: ISSUE-2480
signal: concern
---

`test/demo/test_delivery_fallback_speed.py::test_demo_completes_under_5_seconds`
fails intermittently when run as part of the full integration suite (observed:
5.16s) but passes when run in isolation (5.01s on main, 5.16s → 5.01s isolated).

The threshold is exactly 5 seconds and the test runs at ~5s on the current CI
hardware — any load from parallel tests pushes it over. This produced a false
integration failure during the #2480 build session that required a pre-existing
check to rule out.

Should be tracked as a Concern: either raise the threshold (e.g. 8s with a
comment), mark it `@pytest.mark.flaky`, or make the demo scenario faster.

**Promoted**: 2026-08-27 — captured in specs/received-status-handling.yaml RSH-05-015/16/17 and specs/case-bootstrap-trust.yaml CBT-01-008/09 and CBT-05-008, specs/state-machine.yaml SM-04-001, notes/bt-pitfalls.md, notes/flaky-tests.md, AGENTS.md. Concern issues #2736 #2737 filed. Docs PR: <pending>.
