---
title: VSR-ERR-1 + SM-GUARD-1 + BUG-FLAKY-1 (2026-03-30)
type: implementation
date: '2026-03-30'
source: LEGACY-2026-03-30-vsr-err-1-sm-guard-1-bug-flaky-1-2026-03-30
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3497
legacy_heading: VSR-ERR-1 + SM-GUARD-1 + BUG-FLAKY-1 (2026-03-30)
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## VSR-ERR-1 + SM-GUARD-1 + BUG-FLAKY-1 (2026-03-30)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3497`
**Canonical date**: 2026-03-30 (git blame)
**Legacy heading**

```text
VSR-ERR-1 + SM-GUARD-1 + BUG-FLAKY-1 (2026-03-30)
```

**Legacy heading dates**: 2026-03-30

**Branch**: p251  **Tests**: 1027 passed, 5581 subtests

### What was done

Three grouped PRIORITY-250 tasks completed in one commit:

**VSR-ERR-1 — Rename VultronConflictError**:

- Renamed `VultronConflictError` → `VultronInvalidStateTransitionError` in
  `vultron/errors.py` per `specs/state-machine.yaml` SM-04-002.
- Retained `VultronConflictError` as a deprecated alias.
- Updated all 5 raise sites in `vultron/core/use_cases/triggers/embargo.py`
  (4 sites) and `triggers/report.py` (1 site) to use the new name.
- Added `logger.warning(...)` before each raise as required by SM-04-002.
- Updated `vultron/adapters/driving/fastapi/errors.py` isinstance check.
- Updated `vultron/core/use_cases/triggers/__init__.py` docstring.
- Updated `test/core/use_cases/test_embargo_use_cases.py`.

**SM-GUARD-1 — Export EM_NEGOTIATING**:

- Added `EM_NEGOTIATING` to exports in `vultron/core/states/__init__.py`.
- Replaced inline `[EM.PROPOSED, EM.REVISE]` in
  `vultron/bt/embargo_management/transitions.py` with `list(EM_NEGOTIATING)`.

**BUG-FLAKY-1 — Fix flaky test_remove_embargo**:

- Fixed `test/wire/as2/vocab/test_vocab_examples.py::test_remove_embargo` by
  extracting the embargo from `activity.as_object` rather than independently
  calling `examples.embargo_event(days=90)` (which generates a new time-based
  ID on each call). The test now asserts `embargo.context == case.as_id`.
