---
source: ISSUE-1303
timestamp: '2026-07-10T13:52:36.753850+00:00'
title: 'Refactor log_entry_event_effects: positive-precondition Sequence composites'
type: implementation
---

## Issue #1303 — Refactor log_entry_event_effects: replace IsNot*/Selector with positive-precondition Sequence composites

Replaced four backwards `IsNot*/Selector` composites in `log_entry_event_effects` (`announce_tree.py`) with positive-precondition `Selector(Sequence(IsFoo, Apply), AlwaysSuccess("FooSkipped"))` composites per BTND-08-001, BTND-08-002. Deleted the old `IsNot*` condition node classes and added parametrized unit tests for the four new positive nodes.

PR: <https://github.com/CERTCC/Vultron/pull/1317>
