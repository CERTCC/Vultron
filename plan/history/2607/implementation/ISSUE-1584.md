---
source: ISSUE-1584
timestamp: '2026-07-22T18:46:39.371463+00:00'
title: Rename two-actor demo to FV demo
type: implementation
---

## Issue #1584 — feat(#1557): rename two-actor demo to FV demo

Implemented full rename of "two-actor demo" → "FV demo" across 41 files:
Python source rename (two_actor_demo.py → fv_demo.py), CLI subcommand (two-actor → fv),
Docker Compose DEMO default, CI workflow artifact name, devlogs path, docs, notes, specs, test file.
All 11 acceptance criteria satisfied. 5354 tests pass, all linters clean.

PR: <https://github.com/CERTCC/Vultron/pull/1616>
