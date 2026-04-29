---
title: "PREPX-1 \u2014 Fix BT status string comparisons (2026-03-18)"
type: implementation
date: '2026-03-18'
source: PREPX-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1880
legacy_heading: "PREPX-1 \u2014 Fix BT status string comparisons (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## PREPX-1 — Fix BT status string comparisons (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1880`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
PREPX-1 — Fix BT status string comparisons (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

Replaced three `result.status.name != "SUCCESS"` string comparisons with
`result.status != Status.SUCCESS` enum comparisons in
`vultron/core/use_cases/case.py` (`CreateCaseReceivedUseCase`,
`EngageCaseReceivedUseCase`, `DeferCaseReceivedUseCase`).
Added `from py_trees.common import Status` import. No logic change.

### Test results

966 passed, 5581 subtests, 5 warnings (unchanged).
