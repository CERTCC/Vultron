---
source: ISSUE-493
timestamp: '2026-06-22T17:39:02.797069+00:00'
title: Split test_trigger_embargo.py into per-operation files
type: implementation
---

## Issue #493 — P2: Split test_trigger_embargo.py into per-operation files

Replaced the 1028-line `test_trigger_embargo.py` (57 tests across 5 embargo
endpoints) with five focused files — one per embargo trigger operation:

- `test_trigger_propose_embargo.py` (15 tests)
- `test_trigger_propose_embargo_revision.py` (8 tests)
- `test_trigger_accept_embargo.py` (13 tests)
- `test_trigger_reject_embargo.py` (8 tests)
- `test_trigger_terminate_embargo.py` (13 tests)

Shared fixtures (`client_triggers`, `case_without_participant`,
`case_with_embargo`, `case_with_proposal`, `_add_case_manager`) promoted to
`routers/conftest.py`. The `_no_outbox_delivery` autouse fixture kept per-file
to avoid patching unrelated tests in the same directory. The three
`TestTriggerEmbargoOutboxScheduling` tests absorbed into their respective
operation files as standalone functions.

All 57 tests pass with zero regressions (3469 unit tests clean).

PR: [#1098](https://github.com/CERTCC/Vultron/pull/1098)
