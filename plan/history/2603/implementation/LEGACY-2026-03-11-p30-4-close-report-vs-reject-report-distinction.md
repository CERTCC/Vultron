---
title: P30-4 `close-report` vs `reject-report` distinction
type: implementation
timestamp: '2026-03-11T00:00:00+00:00'
source: LEGACY-2026-03-11-p30-4-close-report-vs-reject-report-distinction
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 447
legacy_heading: "2026-03-09 \u2014 P30-4 `close-report` vs `reject-report`\
  \ distinction"
date_source: git-blame
legacy_heading_dates:
- '2026-03-09'
---

## P30-4 `close-report` vs `reject-report` distinction

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:447`
**Canonical date**: 2026-03-11 (git blame)
**Legacy heading**

```text
2026-03-09 — P30-4 `close-report` vs `reject-report` distinction
```

**Legacy heading dates**: 2026-03-09

Both `reject-report` and `close-report` emit `RmCloseReport` (`as_Reject`), but
they differ in context:

- `reject-report` hard-rejects an incoming report offer (offer not yet validated;
  `object=offer.as_id`)
- `close-report` closes a report after the RM lifecycle has proceeded (RM → C
  transition; emits RC message)

The existing `trigger_reject_report` implementation uses `offer_id` as its target.
The `trigger_close_report` implementation should also use `offer_id` but should
validate that the offer's report is in an appropriate RM state for closure (not
just any offered report). This distinction should be documented in the endpoint
docstring.
