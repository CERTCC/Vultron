---
title: "INLINE-OBJ-B \u2014 Accept/Reject inline typed objects (Priority 330)"
type: implementation
timestamp: '2026-04-17T00:00:00+00:00'
source: INLINE-OBJ-B
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6463
legacy_heading: "INLINE-OBJ-B \u2014 Accept/Reject inline typed objects (Priority\
  \ 330)"
date_source: git-blame
---

## INLINE-OBJ-B — Accept/Reject inline typed objects (Priority 330)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6463`
**Canonical date**: 2026-04-17 (git blame)
**Legacy heading**

```text
INLINE-OBJ-B — Accept/Reject inline typed objects (Priority 330)
```

- Changed `object_` type on all 12 `AcceptXxx` / `RejectXxx` /
  `TentativeRejectXxx` activity classes from `XxxRef`
  (`XxxActivity | as_Link | str | None`) to `XxxActivity | None`,
  preventing bare string IDs from passing Pydantic validation at
  construction time. Files: `actor.py`, `case.py`, `embargo.py`,
  `report.py`, `sync.py` in `vultron/wire/as2/vocab/activities/`.
- Updated `vultron/core/use_cases/triggers/report.py`:
  `_resolve_offer_and_report` now coerces the stored offer to
  `RmSubmitReportActivity` via `model_validate`; 3 callers updated to
  pass the full object to `object_`.
- Updated `vultron/core/use_cases/triggers/embargo.py`: added
  dehydration-aware coercion of stored `as_Invite` to
  `EmProposeEmbargoActivity` (strips dehydrated `object_` string from
  the serialized dict before validation; preserves the embargo event ID
  for the subsequent `dl.read` lookup); caller updated to pass the
  typed proposal as `object_`.
- Updated `vultron/core/use_cases/received/sync.py`: `_send_rejection`
  now constructs a `CaseLogEntry` via `CaseLogEntry.from_core(entry)`
  before passing it as `object_` to `RejectLogEntryActivity`.
- Updated `vultron/demo/utils.py`: `get_offer_from_datalayer` now
  coerces the retrieved `as_Offer` to `RmSubmitReportActivity`; all
  calling demo files benefit automatically.
- Fixed remaining `.id_` string IDs in `receive_report_demo.py` (7
  occurrences), `three_actor_demo.py` (2), `multi_vendor_demo.py` (1),
  and `status_updates_demo.py` (1).
- Updated `specs/response-format.yaml` RF-02-003/04, RF-03-003/04,
  RF-04-003/04 to require inline typed objects.
- Reversed "Accept/Reject object field" pitfall in `AGENTS.md` from
  "use ID string" to "use inline typed object"; also updated the
  Protocol Activity Model section.
- Added regression tests:
  `test/wire/as2/vocab/test_actvitities/test_inline_object_required.py`
  — 12 string-rejected tests + 12 typed-accepted tests.
- Lesson: the storage layer (`_dehydrate_data` in `db_record.py`)
  collapses `object_` of transitive activities to an ID string. Coercion
  back to a typed class must strip the dehydrated string and separately
  retrieve the nested object from `dl.read`.
