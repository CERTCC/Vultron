---
source: ISSUE-1324
timestamp: '2026-07-15T16:38:48.956187+00:00'
title: Enforce effects-before-persist invariant in AnnounceLogEntryReceivedBT
type: implementation
---

## Issue #1324 — Spec + impl: effects-before-persist ordering in Announce(CaseLedgerEntry) receive tree

Restructured `create_announce_log_entry_tree()` so domain effects (embargo teardown, participant-status, note attachment, invite-accept) run BEFORE `PersistReceivedLogEntry`. Replaced `Success('...Skipped')` fallbacks with `Inverter(IsX)` so `Apply*` FAILURE propagates and blocks persist. Added SYNC-12 spec group. All 20 announce-tree tests pass (3 new). PR: <https://github.com/CERTCC/Vultron/pull/1447>
