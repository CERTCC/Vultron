---
source: ISSUE-656
timestamp: '2026-06-11T18:03:46.787156+00:00'
title: Regression tests for DataLayer scope (get_canonical_actor_dl and inbox dual-DL
  path)
type: implementation
---

## Issue \#656 — Add regression tests for DataLayer scope: get\_canonical\_actor\_dl and inbox\_handler dual-DL path

Added dedicated unit tests covering all five acceptance criteria for issue
\#656, preventing regression of BUG-2026040901-class bugs where outbound
activities are silently dropped due to a queue-key mismatch between a short
UUID and the actor's canonical URI.

**New file** `test/adapters/driving/fastapi/test_deps.py` (5 tests):

- AC-1a: `get_canonical_actor_dl()` actor found via `dl.read()` → DL scoped
  to canonical URI
- AC-1b: actor found via `dl.find_actor_by_short_id()` fallback → canonical
  URI (not short ID)
- AC-1c: actor not found → falls back to raw path param
- AC-3a: documents the BUG-2026040901 failure mode — short-ID-scoped DL
  cannot read entries written by `record_outbox_item` with canonical URI
- AC-3b: regression test confirming `get_canonical_actor_dl()` prevents the
  bug

**Modified** `test/adapters/driving/fastapi/test_inbox_handler.py` (1 new test):

- AC-2: `inbox_handler` with `actor_dl ≠ dl` — queue pop uses `actor_dl`;
  rehydration and dispatch use shared `dl`

All 3153 unit tests pass (6 new). Black, flake8, mypy, pyright clean.

PR: [https://github.com/CERTCC/Vultron/pull/898](https://github.com/CERTCC/Vultron/pull/898)
