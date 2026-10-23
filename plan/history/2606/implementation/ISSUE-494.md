---
source: ISSUE-494
timestamp: '2026-06-22T17:20:38.847576+00:00'
title: Split test_sqlite_backend.py by backend concern
type: implementation
---

## Issue #494 — P3: Split test_sqlite_backend.py by backend concern

Split the 1222-line `test_sqlite_backend.py` into 6 focused files grouped
by backend concern, with shared fixtures consolidated in conftest.py.

**New files created:**

- `test_sqlite_crud.py` (273 lines, 27 tests): init, create/read/update/delete/save, all/count/clear, exists/ping
- `test_sqlite_inbox_outbox.py` (175 lines, 17 tests): inbox/outbox queues, enqueue_callback, file-backed integration test
- `test_sqlite_rehydration.py` (273 lines, 13 tests): nested-object dehydration, rehydration, hydrate()
- `test_sqlite_coercion.py` (241 lines, 7 tests): TestRehydrateFields, TestCoerceToSemanticClass
- `test_sqlite_list.py` (112 lines, 5 tests): TestListMethod / list_objects()
- `test_sqlite_find_case.py` (205 lines, 9 tests): find_case_by_short_id, find_case_by_report_id

**conftest.py**: migrated `dl` (now in-memory), `tmp_db_url`, `file_dl`,
`scoped_dl`, `record_factory`, `created_record` fixtures from the original file.

All 3449 unit tests pass. All 6 new files are ≤300 lines.

PR: [#1095](https://github.com/CERTCC/Vultron/pull/1095)
