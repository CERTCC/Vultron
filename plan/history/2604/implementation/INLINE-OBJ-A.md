---
title: "INLINE-OBJ-A \u2014 Inline typed outbound activity objects"
type: implementation
date: '2026-04-16'
source: INLINE-OBJ-A
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6447
legacy_heading: "INLINE-OBJ-A \u2014 Inline typed outbound activity objects\
  \ (COMPLETE 2026-04-16)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-16'
---

## INLINE-OBJ-A — Inline typed outbound activity objects

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6447`
**Canonical date**: 2026-04-16 (git blame)
**Legacy heading**

```text
INLINE-OBJ-A — Inline typed outbound activity objects (COMPLETE 2026-04-16)
```

**Legacy heading dates**: 2026-04-16

- Narrowed initiating outbound AS2 activity `object_` fields from permissive
  `XxxRef` unions to inline typed objects across report, case, participant,
  embargo, actor, and sync activity classes.
- Added MV-09 outbound-object integrity enforcement in the outbox handler so
  delivery rejects bare string or `as_Link` `object_` values after a final
  expansion attempt.
- Fixed all remaining callers in demos, vocab examples, trigger fixtures, and
  received/trigger tests to pass inline domain objects instead of bare IDs.
- Normalized persisted embargo records in `SvcTerminateEmbargoUseCase` so
  SQLite `as_Event` round-trips can still be re-validated as `EmbargoEvent`
  before constructing `AnnounceEmbargoActivity`.
- Updated regression coverage for narrowed activity classes, outbox integrity,
  embargo trigger routes, and vocab example expectations.
