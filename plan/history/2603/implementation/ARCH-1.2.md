---
title: 'ARCH-1.2 complete: InboundPayload introduced; AS2 type removed from
  DispatchActivity'
type: implementation
date: '2026-03-09'
source: ARCH-1.2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 750
legacy_heading: "2026-03-09 \u2014 ARCH-1.2 complete: InboundPayload introduced;\
  \ AS2 type removed from DispatchActivity"
date_source: git-blame
legacy_heading_dates:
- '2026-03-09'
---

## ARCH-1.2 complete: InboundPayload introduced; AS2 type removed from DispatchActivity

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:750`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
2026-03-09 — ARCH-1.2 complete: InboundPayload introduced; AS2 type removed from DispatchActivity
```

**Legacy heading dates**: 2026-03-09

Added `InboundPayload` to `vultron/core/models/events.py` with fields
`activity_id`, `actor_id`, `object_type`, `object_id`, and `raw_activity: Any`.
`DispatchActivity.payload` now types as `InboundPayload` instead of `as_Activity`,
removing the AS2 import from `vultron/types.py` (V-02) and from
`behavior_dispatcher.py` (V-03). All 38 handler functions updated to
`activity = dispatchable.payload.raw_activity`. `verify_semantics` decorator
updated to compare `dispatchable.semantic_type` directly (ARCH-07-001), removing
the second `find_matching_semantics` call. 815 tests pass.
