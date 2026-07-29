---
title: "RejectInviteActorToCase ledger commit is unreachable: Reject(Invite) uses inner_target not target"
type: learning
timestamp: 2026-07-27T00:00:00Z
source: ISSUE-1689
signal: concern
---

`RejectInviteActorToCaseReceivedUseCase.execute()` reads `request.target_id`
(from `request.target`) to resolve the case_id. But `Reject(Invite(actor,
case))` carries the case reference in the nested Invite's `target` field, not
at the top-level `target` of the Reject activity. `extract_event` populates
`inner_target` but not `target`, so `request.target_id` is always `None`.

The use case early-returns with a warning log and never reaches the BT that
would commit the canonical ledger entry. The fix is to read
`request.inner_target_id or request.target_id` instead of `request.target_id`
alone.

This is a pre-existing gap (introduced in #1293), not introduced by #1689.
Documented in `test_reject_invite_skips_ledger_when_target_id_absent`.

Needs a GitHub Concern issue so it does not get lost.

**Promoted**: 2026-07-28 — already in notes/case-ledger-authority.md; bug tracked as ISSUE-1747.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1790>0>0>0>0>0>0>.
