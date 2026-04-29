---
title: "OX-1.0 \u2014 ActivityEmitter port stub (2026-03-19)"
type: implementation
date: '2026-03-19'
source: OX-1.0
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2501
legacy_heading: "OX-1.0 \u2014 ActivityEmitter port stub (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## OX-1.0 — ActivityEmitter port stub (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2501`
**Canonical date**: 2026-03-19 (git blame)
**Legacy heading**

```text
OX-1.0 — ActivityEmitter port stub (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

**Task**: Add `vultron/core/ports/emitter.py` — `ActivityEmitter` Protocol
(outbound counterpart to `core/ports/dispatcher.py`).

**What was done**:

- Created `vultron/core/ports/emitter.py` with the `ActivityEmitter` Protocol.
  Defines `emit(activity: VultronActivity, recipients: list[str]) -> None` as
  the outbound (driven) port contract for delivering activities to recipient
  actor inboxes.
- Created `vultron/adapters/driven/delivery_queue.py` with a stub
  `DeliveryQueueAdapter` class that imports and implements `ActivityEmitter`.
  The stub logs a debug message and returns; the body will be filled in OX-1.1.
- Updated `vultron/core/ports/__init__.py` and
  `vultron/adapters/driven/__init__.py` docstrings to reflect the new modules.

**Result**: 984 tests pass (no regressions). OX-1.1 (local delivery
implementation) is now unblocked.
