---
title: "BUG-2026040102 Fix \u2014 Circular Import in validate_tree"
type: implementation
date: '2026-04-01'
source: LEGACY-2026-04-01-bug-2026040102-fix-circular-import-in-validate-t
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4255
legacy_heading: "BUG-2026040102 Fix \u2014 Circular Import in validate_tree\
  \ (COMPLETE 2026-04-01)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-01'
---

## BUG-2026040102 Fix — Circular Import in validate_tree

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4255`
**Canonical date**: 2026-04-01 (git blame)
**Legacy heading**

```text
BUG-2026040102 Fix — Circular Import in validate_tree (COMPLETE 2026-04-01)
```

**Legacy heading dates**: 2026-04-01

### Issue

`test/core/behaviors/test_performance.py` failed to collect (ImportError) when
run in isolation due to a circular import chain:

```text
validate_tree → nodes → triggers._helpers (via triggers __init__)
  → triggers.report → validate_tree  ← CIRCULAR
```

The full suite sometimes passed because other modules pre-loaded `validate_tree`
first; in isolation or with unlucky ordering the partial-module error surfaced.

After fixing the import cycle, two tests in `test_performance.py` that had
previously been un-runnable also failed because:

- `CreateCaseNode` creates `VultronCase` objects, but `is_case_model()` checked
  for `record_event` which only existed on the wire-layer `VulnerabilityCase`.
- The mock DataLayer in the test did not track objects persisted via `create()`,
  so subsequent `read()` calls returned `None`.

### Root Cause

`vultron/core/behaviors/report/nodes.py` imported `update_participant_rm_state`
from `vultron.core.use_cases.triggers._helpers`.  Loading that dotted path
causes Python to first initialize `vultron.core.use_cases.triggers.__init__`,
which re-exports from `triggers.report`, which imports `create_validate_report_tree`
from `validate_tree` — before `validate_tree` had finished loading.

### Resolution

1. **Break the import cycle**: Moved `update_participant_rm_state` (and
   `resolve_case`) from `triggers/_helpers.py` to the neutral
   `vultron/core/use_cases/_helpers.py`.  `nodes.py` now imports from there,
   bypassing the `triggers` package `__init__`.
2. **Fix `is_case_model` for `VultronCase`**: Added `record_event()` to
   `VultronCase` (core model) using `VultronCaseEvent` (also core), so the
   Protocol guard returns `True` for core-created cases.
3. **Fix test mock**: Updated `mock_datalayer` in `test_performance.py` to
   store objects in an in-memory dict when `create()`/`save()` are called,
   enabling subsequent `read()` calls to find them.

### Validation

`uv run pytest test/core/behaviors/test_performance.py` — 2 passed (in isolation).
Full suite: 1199 passed, 5581 subtests passed (up from 1026; the previously
uncollectable test file now contributes 2 tests).
