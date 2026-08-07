---
source: ISSUE-2047
timestamp: '2026-08-07T19:25:46.682243+00:00'
title: 'feat(fcv-reject): reject-case-invite trigger stack and demo scenario'
type: implementation
---

## Issue #2047 — Implement fcv-reject demo scenario (RM invitation rejection variation)

Implemented the full `reject-case-invite` trigger stack (10 layers from BT node to FastAPI endpoint) and `fcv_reject_demo.py` demo scenario where Vendor rejects the case invitation and is never added as a participant.

Key additions:

- `invite_response.py` — extracted EmitAcceptCaseInviteNode + EmitRejectCaseInviteNode (BTND-07-004 compliance)
- `reject_case_invite_trigger_bt`, `SvcRejectCaseInviteUseCase`, `RejectCaseInviteRequest`, endpoint at `/{actor_id}/trigger/reject-case-invite`
- `fcv_reject_demo.py` + CLI `fcv-reject` command
- `test_fcv_reject_invariants.py` (20 tests) + 3 SvcRejectCaseInviteUseCase unit tests
- CI matrix: fcv-reject added with `full_suite_only: false` (minimum PR set now 4 scenarios)

PR: <https://github.com/CERTCC/Vultron/pull/2084>
