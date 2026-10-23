---
source: ISSUE-1475
timestamp: '2026-07-20T20:27:01.792853+00:00'
title: Migrate vultron/demo/ EM guards to named predicates
type: implementation
---

## Issue #1475 — Migrate vultron/demo/ guards to staged VulnerabilityCase types and predicates

Migrated all inline EM enum comparisons (`!= EM.ACTIVE`, `== EM.EXITED`) and `active_embargo is None/not None` field checks in `vultron/demo/` to named predicates from `vultron.core.states`. Added missing `is_em_exited()` predicate. Fixed 2 test files that accessed `demo.EM.ACTIVE` after EM was removed from scenario module exports.

PR: <https://github.com/CERTCC/Vultron/pull/1551>
