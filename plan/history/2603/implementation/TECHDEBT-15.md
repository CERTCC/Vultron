---
title: "TECHDEBT-15 \u2014 Fix flaky `test_remove_embargo` test (2026-03-16)"
type: implementation
timestamp: '2026-03-16T00:00:00+00:00'
source: TECHDEBT-15
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1548
legacy_heading: "TECHDEBT-15 \u2014 Fix flaky `test_remove_embargo` test (2026-03-16)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-16'
---

## TECHDEBT-15 — Fix flaky `test_remove_embargo` test (2026-03-16)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1548`
**Canonical date**: 2026-03-16 (git blame)
**Legacy heading**

```text
TECHDEBT-15 — Fix flaky `test_remove_embargo` test (2026-03-16)
```

**Legacy heading dates**: 2026-03-16

**Task**: Add `autouse` fixture to `test/wire/as2/vocab/conftest.py` to clear
the py_trees blackboard global state before and after each test in that
directory (TB-06-006, AGENTS.md "py_trees Blackboard Global State").

**What was done:**

- Created `test/wire/as2/vocab/conftest.py` with a `clear_py_trees_blackboard`
  `autouse` fixture that calls `py_trees.blackboard.Blackboard.storage.clear()`
  before and after each test function, matching the pattern in
  `test/core/behaviors/conftest.py`.
- Verified `test_remove_embargo` passes reliably across 5 consecutive runs.
- Full test suite continues to pass (895 tests).

**Test results:** 895 passed, 0 failed
