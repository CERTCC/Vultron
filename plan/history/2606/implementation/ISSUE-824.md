---
source: ISSUE-824
timestamp: '2026-06-22T18:15:24.171265+00:00'
title: participant lookup regression tests and consistent fixture setup
type: implementation
---

## Issue #824 — Update participant lookup tests for canonical case surfaces

Added 7 regression tests for `resolve_case_participant_id_for_actor` in
`test/core/use_cases/test_helpers.py` covering all divergence-detection
scenarios: happy path, cache miss, inline participant object, actor not
found, stale index, index divergence, and duplicate actor in canonical
list. Tests use the `is_case_model()` + DL round-trip pattern matching
production call sites.

Fixed `_make_two_actor_case()` in `test/core/use_cases/triggers/test_trignotify.py`
to populate both `case_participants` and `actor_participant_index` consistently
via `add_participant()` and store participant objects in the DataLayer. The
old fixture left `case_participants` empty.

All 3476 unit tests pass (7 new). Black, flake8, mypy, pyright clean.

PR: [#1104](https://github.com/CERTCC/Vultron/pull/1104)
