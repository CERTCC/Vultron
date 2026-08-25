---
source: ISSUE-1689
timestamp: '2026-07-27T21:32:18.150167+00:00'
title: 'Ledger: full suggest-actor chain entries'
type: implementation
---

## Issue #1689 — Ledger: write full suggest-actor chain entries

Implemented canonical CaseLedgerEntry commits for the complete suggest-actor-to-case protocol flow.

**New ledger entries committed:** offer_actor_to_case, accept_offer_case_participant, reject_offer_case_participant, invite_actor_to_case, add_case_participant.

**Key design decisions:**

- New `_snapshot.py` helper module with `_drop_bare_inline_refs` / `_snapshot_with_context` — strips bare-string inline-object fields that `_validate_canonical_entry` rejects. Factory methods return `target=case_id` as a bare URI; this helper strips those before validation passes.
- `EmitAddCaseParticipantNode` added to `AcceptInviteActorToCaseBT` after `PersistInviteeParticipantNode`.
- Pre-existing design gap found: `RejectInviteActorToCase` ledger commit is unreachable because `Reject(Invite)` has `inner_target` not `target` for the case_id. Documented in test; not introduced by this PR.
- Code review IMPROVE-1 caught: `_build_snapshot` needed to call `_snapshot_with_context` on stored `as_Add` to strip bare target; fixed and regression test added.

PR: <https://github.com/CERTCC/Vultron/pull/1746>
