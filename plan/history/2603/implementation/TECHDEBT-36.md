---
title: "TECHDEBT-36 \u2014 Centralize `_make_payload()` test helper"
type: implementation
timestamp: '2026-03-24T00:00:00+00:00'
source: TECHDEBT-36
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2813
legacy_heading: "TECHDEBT-36 \u2014 Centralize `_make_payload()` test helper\
  \ (COMPLETE 2026-03-24)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-24'
---

## TECHDEBT-36 — Centralize `_make_payload()` test helper

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2813`
**Canonical date**: 2026-03-24 (git blame)
**Legacy heading**

```text
TECHDEBT-36 — Centralize `_make_payload()` test helper (COMPLETE 2026-03-24)
```

**Legacy heading dates**: 2026-03-24

**Goal**: Remove 5 duplicate local `_make_payload(activity, **extra_fields)` functions from
test files in `test/core/use_cases/` and replace with the shared `make_payload` pytest
fixture already defined in `test/core/use_cases/conftest.py`.

**Approach**: Removed the local function definition from each of the 5 affected test files.
Removed the now-unused `from vultron.wire.as2.extractor import extract_intent` module-level
import from 3 files (`test_status_use_cases.py`, `test_note_use_cases.py`,
`test_case_use_cases.py`). Added `make_payload` as a fixture parameter to all 37 test
methods that previously called the local function.

**Source files changed**:

- `test/core/use_cases/test_status_use_cases.py` — removed local def, updated 7 test methods
- `test/core/use_cases/test_actor_use_cases.py` — removed local def, updated 13 test methods
- `test/core/use_cases/test_note_use_cases.py` — removed local def, updated 6 test methods
- `test/core/use_cases/test_case_use_cases.py` — removed local def, updated 6 test methods
- `test/core/use_cases/test_embargo_use_cases.py` — removed local def, updated 11 test methods

### Test results

985 passed, 5581 subtests passed.
