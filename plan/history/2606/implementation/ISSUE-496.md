---
source: ISSUE-496
timestamp: '2026-06-22T17:42:34.464905+00:00'
title: Split test_vocab_examples.py into 5 focused test files
type: implementation
---

## Issue #496 — P5: Split test_vocab_examples.py by domain area

Split the 913-line monolithic `test_vocab_examples.py` (one `TestVocabExamples`
class with 57 tests) into 5 focused files grouped by domain area. Each new file
is ≤350 lines with a clear single responsibility.

**New files:**

- `test_vocab_utils.py` (2 tests, 50 lines): json2md/obj_to_file utilities
- `test_vocab_actor_report_examples.py` (10 tests, 154 lines): actor + report examples
- `test_vocab_participant_examples.py` (14 tests, 254 lines): participants, status, invites, actor recommendations
- `test_vocab_case_examples.py` (22 tests, 344 lines): case lifecycle, notes, ownership, case status — 6 inner test classes
- `test_vocab_embargo_examples.py` (9 tests, 188 lines): embargo lifecycle

The inline `_RecommendActorActivity` import was promoted to module-level.
All 57 tests pass. Black, flake8, mypy, pyright clean.
3469 passed, 37 skipped, 2 xfailed in 75s.

PR: [#1100](https://github.com/CERTCC/Vultron/pull/1100)
