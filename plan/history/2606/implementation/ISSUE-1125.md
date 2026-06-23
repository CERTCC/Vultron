---
source: ISSUE-1125
timestamp: '2026-06-23T13:28:32.082140+00:00'
title: 'Fix demo scenario phase execution order: M2 before M3'
type: implementation
---

## Issue #1125 — Fix demo scenario phase execution order: M2 (sync verification) must run before M3 (notes exchange)

The two-actor demo in `vultron/demo/scenario/two_actor_demo.py` was executing
phases in the wrong order: `_phase_notes_exchange` (M3) ran before
`_phase_sync_verification` (M2). Per the CVD lifecycle and DEMOMA-06-002, the
Finder must have the case replica (M2) before the notes exchange occurs (M3).

**Fix**: Swapped `_phase_sync_verification` and `_phase_notes_exchange` call
order in `run_two_actor_demo()`. Also updated a stale comment in
`_phase_sync_verification` that referenced "After _phase_notes_exchange" — no
longer accurate once sync verification runs before notes exchange.

**Verification**: 4691 unit + integration tests pass; Black, flake8, mypy,
pyright all clean.

PR: [#1130](https://github.com/CERTCC/Vultron/pull/1130)
