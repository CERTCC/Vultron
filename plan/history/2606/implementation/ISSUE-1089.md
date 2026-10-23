---
source: ISSUE-1089
timestamp: '2026-06-22T18:05:53.737990+00:00'
title: Split test_embargo.py (received) by use-case type
type: implementation
---

## Issue #1089 — Split test_embargo.py (received) by use-case type

Split the 1197-line `test/core/use_cases/received/test_embargo.py` (4
classes, 24 tests) into four focused files grouped by use-case concern:

- `test_embargo_propose_accept_reject.py` (9 tests): create/invite, accept,
  and reject lifecycle
- `test_embargo_term_revise.py` (5 tests): add/remove embargo and
  unusual-state transitions
- `test_embargo_misc.py` (4 tests): Announce no-op receiver + #609
  consent-reset regression tests (two smaller classes consolidated)
- `test_embargo_ledger_cascade.py` (6 tests): CaseLedgerEntry cascade for
  all embargo received-side handlers

Pure reorganization — no logic changes. All 24 tests pass unchanged.
Full suite: 3469 passed, 37 skipped, 2 xfailed. Black, flake8, mypy,
pyright clean.

PR: [#1102](https://github.com/CERTCC/Vultron/pull/1102)
