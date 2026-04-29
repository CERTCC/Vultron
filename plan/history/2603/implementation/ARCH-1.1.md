---
title: 'ARCH-1.1 complete: MessageSemantics moved to vultron/core/models/events.py'
type: implementation
date: '2026-03-09'
source: ARCH-1.1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 737
legacy_heading: "2026-03-09 \u2014 ARCH-1.1 complete: MessageSemantics moved\
  \ to vultron/core/models/events.py"
date_source: git-blame
legacy_heading_dates:
- '2026-03-09'
---

## ARCH-1.1 complete: MessageSemantics moved to vultron/core/models/events.py

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:737`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
2026-03-09 — ARCH-1.1 complete: MessageSemantics moved to vultron/core/models/events.py
```

**Legacy heading dates**: 2026-03-09

Created `vultron/core/` package with `models/events.py` containing only
`MessageSemantics`. Removed the definition from `vultron/enums.py` (which
now re-exports it for backward compatibility). Updated all 17 direct import
sites across `vultron/` and `test/`. 815 tests pass.

The compatibility re-export in `vultron/enums.py` may be removed once ARCH-1.3
consolidates the extractor and the AS2 structural enums move to
`vultron/wire/as2/enums.py` (R-04).
