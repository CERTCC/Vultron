---
source: ISSUE-535
timestamp: '2026-06-03T19:23:25.855498+00:00'
title: Replace mixin system with direct @property declarations on event classes
type: implementation
---

## Issue #535 — Replace mixin system with direct @property declarations on event classes

Replaced the 26-class mixin hierarchy in `vultron/core/models/events/_mixins.py`
with explicit `@property` declarations directly on each event subclass.

### What changed

- Deleted `_mixins.py` (311 lines: 26 mixin classes + 7 Protocol helper
  classes).
- Updated `report.py`, `case.py`, `actor.py`, `case_participant.py`,
  `embargo.py`, `note.py`, `status.py`: removed mixin inheritance and added
  direct `@property` for each named alias (e.g. `report_id`/`report`,
  `case_id`/`case`) using `TYPE_CHECKING` guards for cast target types.
- Added `test/core/models/events/test_event_property_aliases.py` with 41
  parametrized boundary tests covering every alias on every event class,
  including all multi-alias classes verified on a single instance.

### Outcome

All 2615 unit tests pass. Black, flake8, mypy, and pyright all clean.

PR: [#704](https://github.com/CERTCC/Vultron/pull/704)
