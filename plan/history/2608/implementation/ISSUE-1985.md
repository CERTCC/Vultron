---
source: ISSUE-1985
timestamp: '2026-08-05T18:50:01.586693+00:00'
title: create_deploy_tree combinator factory (BT-20-005)
type: implementation
---

## Issue #1985 — create_deploy_tree combinator factory (BT-20-005 SHOULD)

Added `create_deploy_tree(case_id, actor_id, fix_call_out, mitigation_call_out)` in `vultron/core/behaviors/report/deploy_tree.py`. Composes `create_deploy_fix_tree` (preferred fix arm) and `create_deploy_mitigation_tree` (mitigation fallback) into a `DeployOrMitigateBT` Selector, satisfying spec requirement BT-20-005 SHOULD.

14 unit tests added in `test/core/behaviors/report/test_deploy_tree.py` covering tree structure (AC-1), factory delegation (AC-2), bundle forwarding, and deterministic defaults (AC-3).

Follow-up issue #2002 created for tick-level Fallback ordering integration tests (DataLayer fixture required).

PR: <https://github.com/CERTCC/Vultron/pull/2003>
