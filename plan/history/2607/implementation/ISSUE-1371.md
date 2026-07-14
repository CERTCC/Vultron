---
source: ISSUE-1371
timestamp: '2026-07-14T16:24:51.158157+00:00'
title: 'Fix: replace None defaults with empty collections'
type: implementation
---

## Issue #1371 — Fix: replace None defaults with empty collections for collection-typed parameters

Replaced all five `param: T | None = None` with `or` guards with `param: T = empty_collection` per CS-21-001. Fixed a mutable-default aliasing hazard in `CreateLogEntryNode.__init__` (the removed `or {}` guard was accidentally protective since `{}` is falsy). Added per-site AC-4 tests. PR #1410 closes the issue.
