---
source: ISSUE-5047-rerun-from-holding
timestamp: '2026-11-06T22:31:21.691476+00:00'
title: Every handling tree tolerates a re-run from holding
type: implementation
---

## Issue #5047 — Every handling tree tolerates a re-run from holding; stages read only the record and the store (ADR-0154)

Delivered in three PRs: part 1 (#6004) added the `HANDLED` received stage, had the
once-only stages read it, and finished an interrupted run on restart (AC-2, AC-3);
part 2 (#6050) added the registry-derived sweep that drives every routed semantic
twice from holding, pinning 57 drained scenarios that sent again; part 3
(https://github.com/CERTCC/Vultron/pull/6081) closes AC-1 as reworded by the
maintainer on 2026-11-06.

Part 3:

- The drained comparison allows a same-id re-send with byte-identical sealed bytes
  and fails a new id, a same id with other bytes, or a new ledger entry.
- The ledger-position answer skips an activity the CASE_MANAGER already judged in
  order (read from the sender's order record and the ledger), so a replay whose
  record was released does not replay entries again under minted ids.
- `FanOutLogEntryNode` announces only an entry its commit newly recorded, and the
  commit tree's mint is one `ActTransaction`, so a recorded entry always has its
  announcements queued.
- `Announce(CaseLedgerEntry)` ids stay minted: a receiver that refused a copy (gap,
  unseeded case) must accept the replayed copy, which a derived id would block.
- `drained_failures.py` is empty and asserted empty.
