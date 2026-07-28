---
source: ISSUE-1503
timestamp: '2026-07-17T22:11:51.926363+00:00'
title: DataLayer read path returns core objects via CORE_VOCABULARY
type: implementation
---

## Issue #1503 — DataLayer read path returns core objects (CORE_VOCABULARY)

Implemented `_from_row` core-vocabulary lookup as the first reconstruction step in `SqliteDataLayer`. `dl.read()` and `dl.list_objects()` now return core domain objects for all 8 registered types (DL-05-001, DL-05-002). Added `_to_wire` helper in trigger adapters using `wire_cls.from_core()`. Updated 19 test files to assert core types. Added 16 round-trip tests. All 5067 tests pass, linters clean.

PR: <https://github.com/CERTCC/Vultron/pull/1512>
