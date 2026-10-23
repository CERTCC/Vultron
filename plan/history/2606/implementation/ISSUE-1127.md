---
source: ISSUE-1127
timestamp: '2026-06-25T18:20:00.172456+00:00'
title: Add SvcOfferCaseManagerRoleUseCase trigger
type: implementation
---

## Issue #1127 — Add trigger-side use case for CASE_MANAGER role delegation

Implemented the trigger-side use case for the CASE_MANAGER role delegation
protocol as part of Epic #1129.

### Deliverables

- `OfferCaseManagerRoleTriggerRequest` added to `requests.py`
- `offer_case_manager_role_trigger_bt()` BT factory added to
  `actor_trigger_trees.py`; threads `captured` dict to leaf node to avoid
  post-lock global blackboard read race condition
- `SvcOfferCaseManagerRoleUseCase` (BT-15-001 compliant): `_prepare()` sets
  `self._actor_id = case_actor_id` (PCR-08-007 pattern); `_build_tree()`
  passes `captured=self._captured`; no racy post-lock blackboard access
- `SvcAcceptCaseManagerRoleUseCase` stub (raises `NotImplementedError`,
  per OX-10-004)
- `TriggerService.offer_case_manager_role()` and
  `TriggerServicePort.offer_case_manager_role()` added
- `OfferCaseManagerRoleRequest` HTTP body model and
  `POST /{actor_id}/trigger/offer-case-manager-role` endpoint
- 4 unit tests: happy path, missing case actor, missing case, captured activity
- `CreateOfferCaseManagerActivityNode` updated to populate `captured["activity"]`
  under the BT global lock (concurrent-safe)

### Verification

4343 unit tests passed. All four linters (black, flake8, mypy, pyright) clean.

**PR**: [#1183](https://github.com/CERTCC/Vultron/pull/1183)
