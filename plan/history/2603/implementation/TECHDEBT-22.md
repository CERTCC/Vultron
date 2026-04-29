---
title: "TECHDEBT-22 \u2014 UseCase[Req, Res] Protocol base on all use case\
  \ classes (2026-03-16)"
type: implementation
date: '2026-03-16'
source: TECHDEBT-22
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1705
legacy_heading: "TECHDEBT-22 \u2014 UseCase[Req, Res] Protocol base on all\
  \ use case classes (2026-03-16)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-16'
---

## TECHDEBT-22 — UseCase[Req, Res] Protocol base on all use case classes (2026-03-16)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1705`
**Canonical date**: 2026-03-16 (git blame)
**Legacy heading**

```text
TECHDEBT-22 — UseCase[Req, Res] Protocol base on all use case classes (2026-03-16)
```

**Legacy heading dates**: 2026-03-16

**What was done**: Added explicit `UseCase[RequestType, ResponseType]` inheritance
to all 47 use case classes across 11 files in `core/use_cases/` and
`core/use_cases/triggers/`. Handler use cases inherit from
`UseCase[XxxReceivedEvent, None]`; trigger use cases inherit from
`UseCase[XxxTriggerRequest, dict]`. Added `from vultron.core.ports.use_case
import UseCase` import to each file. Fixed two edge cases where the import
insertion script placed the new import inside a multi-line import block in
`triggers/case.py` and `triggers/report.py`.

**Lessons learned**: When inserting imports after the last import line, a line
scan looking for `from` / `import` prefixes can land on the first line of a
multi-line import block. Must verify the located line is not inside an unclosed
parenthesis.

**Test results:** 893 passed, 0 failed (unchanged from baseline).
