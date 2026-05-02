---
title: "AF.12 — Mark internal activity subclasses as private"
type: implementation
date: 2026-05-01
source: TASK-AF
---

## AF.12 — Mark internal activity subclasses as private in vocab/activities/

Added `_` prefix to all 40 internal Vultron activity classes across
`vultron/wire/as2/vocab/activities/` to signal that they are private
implementation details of the factory layer (spec AF-05-003).

**Files modified (19 total):**

- `vocab/activities/report.py`, `case.py`, `embargo.py`, `actor.py`,
  `case_participant.py`, `sync.py` — class definitions + internal cross-refs
  (object_ field type annotations between classes)
- `factories/report.py`, `case.py`, `embargo.py`, `actor.py`,
  `case_participant.py`, `sync.py` — import names + `isinstance()` checks
- `vultron/semantic_registry.py` — import names and `wire_activity_class` refs
- `test/wire/as2/vocab/test_actvitities/test_object_types.py`,
  `test_inline_object_required.py`, `test_activities.py` — import names
- `test/adapters/driven/test_sqlite_backend.py` — `__name__` assertions
  updated to match new `_`-prefixed class names

All 2187 unit tests pass.
