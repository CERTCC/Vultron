---
source: ISSUE-2015
timestamp: '2026-08-06T18:23:35.154192+00:00'
title: Fix ownership-transfer routing via CaseActor (CM-21-005/006/007)
type: implementation
---

Implemented ADR-0053: corrected two routing gaps in the ownership-transfer
protocol so both `Offer(VulnerabilityCase)` and `Accept(Offer(VulnerabilityCase))`
are addressed to the CaseActor instead of directly to the transferee/offerer.

## Changes

- `EmitOfferCaseOwnershipTransferNode._emit()` resolves `case_actor_id` via
  `_resolve_case_manager_id()` and passes `to=[case_actor_id]` (CM-21-005).
- `EmitAcceptCaseOwnershipTransferNode` gains `case_id` constructor param;
  `_emit()` resolves `case_actor_id` and passes `to=[case_actor_id]` (CM-21-006).
- `create_accept_ownership_transfer_tree()` rewritten using
  `create_receive_activity_tree()` to add guarded-commit (CaseLedgerEntry +
  Announce broadcast) after `AcceptCaseOwnershipTransferNode` (CM-21-007).
- `AcceptCaseOwnershipTransferReceivedUseCase` now passes `receiving_actor_id`
  (not `new_owner_id`) to `BTBridge` so `CheckIsCaseManagerNode` gates correctly.
- `OfferCaseOwnershipTransferReceivedUseCase` extended to commit CaseLedgerEntry
  and forward Offer to transferee's inbox.
- `OFFER_CASE_OWNERSHIP_TRANSFER` and `ACCEPT_CASE_OWNERSHIP_TRANSFER` added
  to `_SYNC_AND_TRIGGER_PORT_SEMANTICS` in `inbox_port_factories.py`.
- Demo `post_to_inbox_and_wait` self-delivery workaround removed.
- 6429 tests pass (1 updated); black, flake8, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/2044>
Closes: #2015
