---
source: ISSUE-1686
timestamp: '2026-07-24T19:24:35.524743+00:00'
title: 'BT: emit Accept(CaseManagerRole) to ledger after role accepted'
type: implementation
---

## Issue #1686 — BT: emit Accept(CaseManagerRole) after case-manager role accepted

Root cause: `AutoAcceptCaseManagerRoleNode.update()` called `_call_factory()` then `_enqueue_accept()` with no ledger commit between them.

Fix:

- `accept_case_manager_role` adapter method changed to return `(id, dict)` — inline snapshot captured before DL storage
- New `_commit_accept_to_ledger(accept_id, payload_snapshot)` runs `create_commit_log_entry_tree` via BTBridge with `disposition="recorded"` before `_enqueue_accept`
- Added `("Accept", "Offer")` to `_CASE_AUTHORED_SIGNATURES` in `chain.py`
- Port contract updated: `TriggerActivityPort.accept_case_manager_role` → `tuple[str, dict[str, Any]]`
- 5 new tests in `TestAutoAcceptCaseManagerRoleNode`; 3 existing tests updated

Branch: task/1686-emit-accept-case-manager-role (pushed, PR creation blocked by GitHub API server error)
Validation: 5381 passed, 0 failed
