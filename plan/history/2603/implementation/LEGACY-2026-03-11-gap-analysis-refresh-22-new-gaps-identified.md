---
title: 'Gap analysis refresh #22: new gaps identified'
type: implementation
timestamp: '2026-03-11T00:00:00+00:00'
source: LEGACY-2026-03-11-gap-analysis-refresh-22-new-gaps-identified
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 407
legacy_heading: "2026-03-10 \u2014 Gap analysis refresh #22: new gaps identified"
date_source: git-blame
legacy_heading_dates:
- '2026-03-10'
---

## Gap analysis refresh #22: new gaps identified

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:407`
**Canonical date**: 2026-03-11 (git blame)
**Legacy heading**

```text
2026-03-10 — Gap analysis refresh #22: new gaps identified
```

**Legacy heading dates**: 2026-03-10

### P70 DataLayer refactor — when to plan

`notes/domain-model-separation.md` says the DataLayer relocation SHOULD be planned
together with PRIORITY-100 (actor independence). The P70 tasks in the plan follow
that guidance: P70-1 relocates the port Protocol and TinyDB adapter to their
correct architectural homes, which unblocks the per-actor isolation work in
PRIORITY-100. P60-3 must come first (adapters package stub needed before TinyDB
moves there).

### TECHDEBT-4 superseded

TECHDEBT-4 ("reorganize top-level modules `activity_patterns`, `semantic_map`,
`enums`") is largely complete:

- `vultron/activity_patterns.py` and `vultron/semantic_map.py` deleted in
  ARCH-CLEANUP-1.
- AS2 structural enums moved from `vultron/enums.py` to `vultron/wire/as2/enums.py`
  in ARCH-CLEANUP-2.
- `vultron/enums.py` now only re-exports `MessageSemantics` plus defines
  `OfferStatusEnum` and `VultronObjectType`.

Remaining work: move `OfferStatusEnum` and `VultronObjectType` to their proper
homes and delete `vultron/enums.py`. Tracked in TECHDEBT-4 (marked superseded in
plan) and P70-2.
