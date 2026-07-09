---
source: CONCERN-1287
timestamp: '2026-07-09T14:23:47.846098+00:00'
title: invite_actor_to_case trigger never commits a CaseLedgerEntry (trigger-side
  BT gap)
type: learning
---

## Problem

`invite_actor_to_case_trigger_bt` in `vultron/core/behaviors/case/actor_trigger_trees.py`
emits an `Invite(VulnerabilityCase)` addressed only to `invitee_id` (`to=[invitee_id]`).
The CaseActor never receives its own Invite activity in its inbox, so
`InviteActorToCaseReceivedUseCase` never fires for the CaseActor and the canonical
case ledger has no `invite_actor_to_case` entry. The FVV demo log jumps from
`validate_report` directly to `accept_invite_actor_to_case` with no Invite entry in
between — violating `notes/case-ledger-authority.md` which explicitly lists
`Invite(VulnerabilityCase)` as a required canonical entry type.

## Root Cause

CLP-10-001 (ADR-0021) requires every protocol-significant trigger tree to emit at
least one outbound activity addressed to `case_manager_id`. This requirement was
interpreted as applying only to participant-originated triggers, not to
CaseActor-originated triggers. Since the CaseActor IS a participant with extra
duties, it is not exempt — but no code enforced this for CaseActor-originated
activities. The `offer_case_manager_role` trigger works correctly (it uses a
self-addressed Offer), but `invite_actor_to_case` was never fixed.

## Fix Approach

1. `EmitInviteActorToCaseNode` adds `case_actor_id` to the Invite's `cc:` field
2. `InviteActorToCaseReceivedUseCase` upgraded to BTBridge + new
   `create_invite_actor_to_case_received_tree` with `GuardedCommitCaseLedgerEntryBT`
3. OX-08-004 WARNING suppressed for purposeful CaseActor self-copy (cc: = own ID)
4. `invite_actor_to_case` added to `EXPECTED_EVENT_TYPES`

## Why cc: not to: for the self-copy

The invitee is the primary recipient; the CaseActor's copy is archival.
Using `to:` for both would misrepresent the CaseActor as a co-primary recipient of
its own outbound message. `cc:` preserves the correct semantic. OX-08-004 was
narrowed to exclude this purposeful self-copy pattern (the only valid `cc:` use
in the protocol).

**Resolved**: 2026-07-09 — implementation tracked in #1293.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1291>.
Spec: `specs/case-ledger-processing.yaml` (CLP-10-001).
Spec: `specs/outbox.yaml` (OX-08-004).
ADR: `docs/adr/0021-caseactor-inbox-routing-canonical-ledger.md`.
