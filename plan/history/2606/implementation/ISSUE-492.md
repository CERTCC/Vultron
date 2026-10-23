---
source: ISSUE-492
timestamp: '2026-06-22T17:19:42.583617+00:00'
title: Consolidate trigger-router fixtures into routers conftest.py
type: implementation
---

## Issue #492 — P1: Consolidate duplicated trigger-router fixtures into conftest.py

Consolidated the identical `actor_and_dl`, `actor`, and `dl` fixtures
that were copy-pasted across `test_trigger_embargo.py`,
`test_trigger_report.py`, and `test_trigger_case.py` into the shared
`test/adapters/driving/fastapi/routers/conftest.py`.

The old `dl(datalayer)` alias was replaced with `dl(actor_and_dl)`. The
`client_actors`, `client_datalayer`, and `created_actors` fixtures were
updated to use `datalayer` directly to avoid DataLayer instance mismatch.
Tests in `test_actors.py` (3) and `test_datalayer.py` (8) that paired `dl`
with the affected client fixtures were updated to use `datalayer` instead.

All 3449 unit tests pass. All linters clean.

PR: [#1094](https://github.com/CERTCC/Vultron/pull/1094)
