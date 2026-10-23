---
source: ISSUE-1348
timestamp: '2026-07-10T20:25:37.753453+00:00'
title: 'fix: namespace suggested_roles blackboard key by recommendation_id'
type: implementation
---

## Issue #1348 — fix: namespace suggested_roles blackboard key by recommendation_id

EvaluateDefaultRolesNode previously wrote to a flat `suggested_roles` blackboard key.
Fixed by namespacing it as `suggested_roles_{recommendation_id_segment}` per BTND-03-004,
eliminating the concurrent-tree collision risk.

PR: <https://github.com/CERTCC/Vultron/pull/1352>
