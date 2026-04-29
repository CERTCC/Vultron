---
title: CS-09-002 duplication in triggers.py request models
type: implementation
date: '2026-03-11'
source: LEGACY-2026-03-11-cs-09-002-duplication-in-triggers-py-request-mod
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 463
legacy_heading: "2026-03-09 \u2014 CS-09-002 duplication in triggers.py request\
  \ models"
date_source: git-blame
legacy_heading_dates:
- '2026-03-09'
---

## CS-09-002 duplication in triggers.py request models

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:463`
**Canonical date**: 2026-03-11 (git blame)
**Legacy heading**

```text
2026-03-09 — CS-09-002 duplication in triggers.py request models
```

**Legacy heading dates**: 2026-03-09

`ValidateReportRequest` and `InvalidateReportRequest` in `triggers.py` are
structurally identical (both have `offer_id: str` and `note: str | None`). Per
CS-09-002, these should be consolidated into a single base model with the other
as a subclass or alias. Low-priority but worth addressing when the file is next
modified.
