---
title: "TECHDEBT-27 \u2014 Standardize error handling in use cases (2026-03-17)"
type: implementation
date: '2026-03-17'
source: TECHDEBT-27
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1761
legacy_heading: "TECHDEBT-27 \u2014 Standardize error handling in use cases\
  \ (2026-03-17)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-17'
---

## TECHDEBT-27 — Standardize error handling in use cases (2026-03-17)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1761`
**Canonical date**: 2026-03-17 (git blame)
**Legacy heading**

```text
TECHDEBT-27 — Standardize error handling in use cases (2026-03-17)
```

**Legacy heading dates**: 2026-03-17

Removed all silent `except Exception as e: logger.error(...)` swallowers
(with no re-raise) from every `execute()` method in 7 use case files:
`actor.py`, `case.py`, `case_participant.py`, `embargo.py`, `note.py`,
`report.py`, `status.py`. Domain exceptions now propagate naturally out of
use cases.

Added catch-log-reraise in `DispatcherBase._handle()`: unexpected exceptions
are logged at ERROR level with `exc_info=True` (full stack trace) and then
re-raised, satisfying the dispatcher-boundary requirement.

Inner `try/except ValueError` idempotency guards in `report.py` and `case.py`
(`CloseCaseReceivedUseCase`) were preserved unchanged.

**Test results:** 913 passed, 0 failed.
