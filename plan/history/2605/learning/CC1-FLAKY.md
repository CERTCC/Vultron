---
source: CC1-FLAKY
timestamp: '2026-05-05T18:28:17.938005+00:00'
title: SUBFAILED in unittest subtests does not fail pytest; pre-existing flaky test_vultrabot
type: learning
---

## 2026-05-05 CC1-FLAKY — Pre-existing flaky subtest in test_vultrabot

`test/bt/test_vultrabot.py::MyTestCase::test_main` shows `SUBFAILED` on
`test_main` when run in the full suite but passes in isolation. This is a
pre-existing global-state ordering issue (py_trees blackboard), not caused
by CC.1 changes. Exit code remains 0 because unittest subtest failures do
not trigger pytest's failure exit code.

**Promoted**: 2026-05-05 — documented in `test/AGENTS.md` ("`SUBFAILED` in
`unittest.TestCase` Subtests Does Not Fail pytest").
