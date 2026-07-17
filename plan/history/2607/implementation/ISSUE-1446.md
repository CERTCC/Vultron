---
source: ISSUE-1446
timestamp: '2026-07-17T13:59:26.983098+00:00'
title: Document pre-SYNC-13 upgrade path (migration guard accept)
type: implementation
---

## Issue #1446 — Migration guard: detect already-persisted entries with unapplied effects (SYNC-12)

Decided Accept (no repair path) — the stale {entry: stored, effects: not-applied} state arose from a pre-production bug in the ingress adapter (pre-SYNC-13 code), with no extant deployed nodes or cases. SYNC-13 (PR #1447) closes the gap going forward.

Added "Pre-SYNC-13 Upgrade Path" section to notes/sync-ledger-replication.md: nodes in stale state must wipe their local DataLayer and re-sync from the CaseActor. Also updated notes/README.md to surface the SYNC-12/SYNC-13 write-ownership and upgrade-path content in the file's index entry.

PR: <https://github.com/CERTCC/Vultron/pull/1478>
