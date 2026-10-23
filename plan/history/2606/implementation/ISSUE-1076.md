---
source: ISSUE-1076
timestamp: '2026-06-22T16:46:35.591510+00:00'
title: 'AST ratchet: detect direct DataLayer mutations in execute()'
type: implementation
---

## Issue #1076 — Add AST-based ratchet: detect direct DataLayer mutations in execute() methods

Implemented `test/architecture/test_no_dl_mutations_in_execute.py`, an
AST-based architecture ratchet that detects `self._dl.save/create/update/delete`
calls made directly inside `execute()` methods across all files under
`vultron/core/use_cases/`.

The detector uses `_walk_own_scope()` to scan only the execute() method's own
scope, correctly excluding mutations inside nested `FunctionDef`,
`AsyncFunctionDef`, and `Lambda` scopes (the last being a fix surfaced by the
pre-PR code review).

`KNOWN_VIOLATIONS` ratchet tracks 6 pre-existing files awaiting migration
(2 more than the 4 listed in the issue — `received/case/lifecycle.py` and
`received/note.py` acquired mutations post-issue-creation). Includes 8 tests:
the ratchet assertion plus 7 synthetic detector-validation tests.

PR: [#1088](https://github.com/CERTCC/Vultron/pull/1088)
