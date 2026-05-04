---
title: "P75-4-pre \u2014 Standardize UseCase Interface (2026-03-16)"
type: implementation
timestamp: '2026-03-16T00:00:00+00:00'
source: LEGACY-2026-03-16-p75-4-pre-standardize-usecase-interface-2026-03
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1528
legacy_heading: "P75-4-pre \u2014 Standardize UseCase Interface (2026-03-16)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-16'
---

## P75-4-pre — Standardize UseCase Interface (2026-03-16)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1528`
**Canonical date**: 2026-03-16 (git blame)
**Legacy heading**

```text
P75-4-pre — Standardize UseCase Interface (2026-03-16)
```

**Legacy heading dates**: 2026-03-16

**What was done:**

- Created `vultron/core/ports/use_case.py` — defines the `UseCase[Req, Res]`
  Protocol with a single `execute(request: Req) -> Res` method.  This is the
  standard interface all class-based use cases must implement going forward.
- Refactored `vultron/core/use_cases/unknown.py` — introduced `UnknownUseCase`
  as the reference implementation (`__init__` receives `DataLayer`; `execute`
  contains the logic).  The old `unknown(event, dl)` function is kept as a
  thin backward-compat wrapper so the existing dispatcher routing table and
  tests are unaffected.
- Added `test/core/ports/` package with `test_use_case.py` — 8 new tests
  covering Protocol structural check, `UnknownUseCase` construction, logging
  behaviour, and backward-compat wrapper.

**Test results:** 895 passed, 0 failed
