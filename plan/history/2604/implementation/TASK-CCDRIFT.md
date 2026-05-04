---
title: TASK-CCDRIFT — Fix cc Addressing Warning + PersistCase Upsert
type: implementation
timestamp: '2026-04-28T22:54:41+00:00'

source: TASK-CCDRIFT
---

## TASK-CCDRIFT — Fix cc Addressing Warning + PersistCase Upsert

Both subtasks implemented and tested.

**CCDRIFT.1** — cc guard in `SubmitReportReceivedUseCase`:

- When receiving actor is in `cc` (not `to`), handler logs WARNING and
  discards the activity without creating a case.
- Both `to` (case created) and `cc` (warning, no case) paths are tested
  in `test/core/use_cases/received/test_report.py`.

**CCDRIFT.2** — PersistCase BT node: silent upsert on duplicate:

- `PersistCase.update()` calls `dl.save()`, which uses upsert semantics:
  updates the existing record if the ID already exists, inserts otherwise.
- No WARNING is logged for pre-existing cases.
- Duplicate-case scenario tested in
  `test/core/behaviors/case/test_receive_report_case_tree.py`.
