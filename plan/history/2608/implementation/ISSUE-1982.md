---
source: ISSUE-1982
timestamp: '2026-08-05T18:46:06.084310+00:00'
title: EMB-15 BTBridge integration tests
type: implementation
---

## Issue #1982 — EMB-15 integration tests: tick decision tree with real DataLayer and CaseParticipant

Added `TestBTBridgeIntegration` (9 tests) to `test/core/behaviors/embargo/test_response_decision_tree.py`.

Covers all four issue requirements:

- CASE_OWNER gospel bypass (CheckIsCaseOwnerNode → SUCCESS skips CaseOwnerApproves call-out)
- Non-owner routes through CaseOwnerApproves seam
- Unknown actor falls through to reject_bt
- Flow A: accept, counter (WillingToCounter SUCCESS), reject fallback
- Flow B: accept, reject fallback

Pre-PR review found 2 IMPROVE items (dead `evaluate_embargo_proposal_factory` stubs and misleading comments describing failure path); both fixed before PR opened.

PR: <https://github.com/CERTCC/Vultron/pull/2001>
