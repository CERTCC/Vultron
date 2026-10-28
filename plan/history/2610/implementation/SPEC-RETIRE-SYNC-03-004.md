---
source: SPEC-RETIRE-SYNC-03-004
timestamp: '2026-10-27T17:06:32.674292+00:00'
title: Retired requirement SYNC-03-004
type: implementation
---

Retired SYNC-03-004 from `specs/sync-ledger-replication.yaml` (#5109).

Why: ADR-0156 moves the sender's position off `context` onto the `ledgerPosition` every case activity carries, from every sender, as a MUST; `context` returns to its AS2 meaning.

Replacement: SYNC-18-001

Final text: `plan/retired-specs/SYNC-03-004.md`.
