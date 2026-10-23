---
source: ISSUE-1108
timestamp: '2026-07-08T15:13:53.594193+00:00'
title: Remove shadowing fixture definitions from test_trigger_actor.py
type: implementation
---

## Issue #1108 — Chore: Remove shadowing fixture definitions from test_trigger_actor.py

Removed duplicate `actor_and_dl`, `actor`, and `dl` fixture definitions from
`test/adapters/driving/fastapi/routers/test_trigger_actor.py`. These three
fixtures were identical to the ones consolidated into the shared routers
`conftest.py` in PR #492. The test file was inheriting them via shadowing
rather than from conftest. After removal, all 21 tests pass unchanged.

PR: <https://github.com/CERTCC/Vultron/pull/1259>
