---
source: ISSUE-1942
timestamp: '2026-08-05T17:18:49.158164+00:00'
title: EMB-15 inbound embargo-response decision seam
type: implementation
---

## Issue #1942 — Implement inbound embargo-response decision seam (EMB-15)

Implemented `create_embargo_response_decision_tree` in
`vultron/core/behaviors/embargo/response_decision_tree.py`.

Tree structure:

- ResponseDecisionSelector (Selector, memory=False)
  - AcceptArm (Sequence): AuthorizeSelector (CheckIsCaseOwnerNode gospel bypass + CaseOwnerApprovesEmbargoResponse call-out) → EvaluateEmbargoProposal → accept_bt
  - CounterArm (Sequence, Flow A only, when counter_bt supplied): WillingToCounterEmbargoProposal → counter_bt
  - reject_bt (always last fallback)

Key fix from code review: parameter was renamed from `sender_actor_id` to `deciding_actor_id` — the gospel bypass checks whether the LOCAL deciding actor is CASE_OWNER, not whether the remote proposer is.

Also added `case_owner_approves_embargo_response_factory` to `EmbargoCallOutBundle` (default AlwaysSucceed) and `CaseOwnerApprovesEmbargoResponse` fuzzer class in demo layer.

36 structural unit tests added. Integration tests (runtime DataLayer tick) deferred to #1982.

PR: <https://github.com/CERTCC/Vultron/pull/1983>
