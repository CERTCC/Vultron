---
source: ISSUE-1067
timestamp: '2026-06-26T16:02:46.703609+00:00'
title: Add EmitRejectCaseManagerRoleNode as explicit Reject fallback
type: implementation
---

## Issue #1067 — feat: add explicit Reject path for OfferCaseManagerRole when actor cannot accept

Added `EmitRejectCaseManagerRoleNode` as a Selector fallback after
`AutoAcceptCaseManagerRoleNode` in the `offer_case_manager_role` received BT
tree. When the Case Actor cannot auto-accept a case manager role offer, it now
sends an explicit `Reject` activity back to the offering vendor instead of
staying silent.

### Implementation

- `TriggerActivityPort`: added `reject_case_manager_role` protocol method
- `TriggerActivityAdapter/_ActorsMixin`: implemented `reject_case_manager_role`
  (mirrors `accept_case_manager_role`)
- `nodes/delegation.py` (new): split delegation nodes from `communication.py`
  to comply with BTND-07-004 500-line limit; contains
  `ResolveCaseManagerOfferContextNode`, `CreateOfferCaseManagerActivityNode`,
  `AutoAcceptCaseManagerRoleNode`, `EmitRejectCaseManagerRoleNode`
- `nodes/communication.py`: trimmed to `CollectCaseAddresseesNode` +
  `CreateAndPersistCaseActivityNode` (~190 lines)
- `offer_case_manager_role_received_tree.py`: `AcceptOrReject` Selector wraps
  AutoAccept + EmitReject as the final effect node
- Tests: 7 unit tests for `EmitRejectCaseManagerRoleNode` + 2 received
  use-case tests for the reject-fallback path

PR: [#1194](https://github.com/CERTCC/Vultron/pull/1194)
