---
source: ISSUE-696
timestamp: '2026-06-09T14:07:04.766574+00:00'
title: Refactor embargo trigger orchestration
type: implementation
---

## Issue #696 — Post-#538: Audit and clean up triggers/embargo.py after EmbargoLifecycle lands

Refactored embargo trigger use cases to delegate EM/PEC transitions to EmbargoLifecycle, kept sender-side activity construction intact, and added a regression test proving invalid embargo proposals do not persist orphaned embargo records.

PR: <https://github.com/CERTCC/Vultron/pull/838>
