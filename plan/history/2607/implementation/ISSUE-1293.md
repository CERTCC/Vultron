---
source: ISSUE-1293
timestamp: '2026-07-09T19:35:49.923460+00:00'
title: fix invite_actor_to_case trigger commits CaseLedgerEntry
type: implementation
---

## Issue #1293 — fix: invite_actor_to_case trigger never commits a CaseLedgerEntry

Fixed all five acceptance criteria. The CaseActor's own URI is now added to `cc:` of the outbound Invite so ASGI self-delivery routes a copy to the CaseActor's inbox. A new `create_invite_actor_to_case_received_tree()` factory handles the received-side BT; `InviteActorToCaseReceivedUseCase` upgraded to use BTBridge on the CaseActor path. OX-08-004 warning suppressed for purposeful self-copies. CI ledger invariants test updated.

PR: <https://github.com/CERTCC/Vultron/pull/1305>
