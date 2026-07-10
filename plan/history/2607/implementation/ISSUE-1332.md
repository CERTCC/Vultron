---
source: ISSUE-1332
timestamp: '2026-07-10T18:31:10.083611+00:00'
title: ProtocolPair round-trip
type: implementation
---

## Issue #1332 — ProtocolPair — model Offer(CaseParticipant) round-trip in ledger

Implemented all 5 acceptance criteria:

- AC-1: Complete Offer(CaseParticipant) round-trip — new MessageSemantics, extractor patterns, semantic registry entries, received use cases with ledger commits
- AC-2: ProtocolPair dataclass (done in prior session)
- AC-3: PendingAssertionStore refactored to use ProtocolPair as key type
- AC-4: find_protocol_pair() added to CasePersistence port, DataLayer port, and SQLite adapter
- AC-5: CLP-11 specs (4 rules) for canonical request/reply state detection

PR: <https://github.com/CERTCC/Vultron/pull/1345>

Key design decisions:

- Removed ACCEPT/REJECT_ACTOR_RECOMMENDATION from MessageSemantics entirely (superseded); registry test prevents equal-pattern entries
- ProtocolPair serves as shared value type for both find_protocol_pair() (durable ledger query) and PendingAssertionStore (ephemeral suppression)
- Rebase failed in git worktree context due to hook interference; resolved with soft-reset to origin/main + manual merge of inbox_port_factories.py and suggest_actor_tree.py
