---
source: ISSUE-961
timestamp: '2026-06-15T19:41:47.876443+00:00'
title: Late-joiner canonical case-ledger backfill
type: implementation
---

## Issue #961 — Late-joiner canonical case-ledger backfill at participant join time

Implemented join-time canonical `CaseLedgerEntry` backfill for late-joining participants, with resumable progress markers persisted in `VultronReplicationState` (`join_backfill_target_index`, `join_backfill_last_sent_index`, `join_backfill_complete`). Accept-invite processing now replays canonical entries in strict order, resumes interrupted runs without duplicates, and requires `sync_port` so backfill state cannot be skipped. Inbox/dispatcher wiring was updated so `ACCEPT_INVITE_ACTOR_TO_CASE` gets both trigger + sync ports, and dispatch now enforces catch-up gating for selected participant-originated semantics with semantic-safe case-id resolution.

PR: <https://github.com/CERTCC/Vultron/pull/976>
