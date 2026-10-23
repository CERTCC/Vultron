---
source: ISSUE-1513
timestamp: '2026-07-20T19:41:00.621124+00:00'
title: Extract has_case_statuses predicate; wire into action_rules.py
type: implementation
---

## Issue #1513 — Wire HasCaseStatusesNode into action_rules.py (AC-5 remaining site)

Extracted `has_case_statuses(case)` into `vultron/core/models/_helpers.py` as the shared predicate for the "case has at least one CaseStatus entry" check (LST-05 / AC-5, Option B — DRY over inline guards).

Wired the predicate into both call sites:

- `HasCaseStatusesNode.update()` in `vultron/core/behaviors/embargo/nodes/conditions.py`
- `GetActionRulesUseCase.execute()` in `vultron/core/use_cases/query/action_rules.py`

Added three unit tests covering non-empty → True, explicit-empty → False, and default-construction → False.

PR: <https://github.com/CERTCC/Vultron/pull/1544>
