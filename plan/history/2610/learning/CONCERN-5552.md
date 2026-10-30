---
source: CONCERN-5552
timestamp: '2026-10-30T18:37:37.356321+00:00'
title: A participant rejects every held early ledger entry, so the CASE_MANAGER replays
  the whole ledger once per entry
type: learning
---

Theme: theme:shared-case-history — All participants see the same events in the same order; ledger is trustworthy and tamper-evident.

## Summary

With #5521 fixed (PR #5527, via #5538), a participant that gets ledger entries
before the case now holds them and replays them as soon as the case arrives
(SYNC-15-005). But SYNC-15-001 still makes it send a
`Reject(CaseLedgerEntry)` with `last_accepted_hash=""` for **every** early
entry it can't place. Each Reject makes the CASE_MANAGER send
`Announce(VulnerabilityCase)` (SYNC-15-015) and replay the whole ledger from
the start, rate-bounded per SYNC-15-003. Since the held entries already
converge the replica, those replays are all duplicates. On a busy server they
back up the participant's inbox for many seconds.

## Evidence

- While validating #5538 against a live single server, one
  `vultron-demo acknowledge` run failed because its message waited about 20 s
  behind duplicate replays in the reporter's inbox (the run overlapped a
  5-minute docs build on the same machine).
- With the fix, the held-entry drain starts at 0.00 s after the case arrives
  in all 24 measured cases, so the replay Rejects buy nothing in that path.

## Open question

Which rule should change, if any?

- **Send at most one replay Reject per case while entries are held:** a
  participant that already holds entries for an unknown case doesn't Reject
  again (SYNC-15-001).
- **Hold first, Reject only on timeout:** the participant holds the entries
  and Rejects only if the case hasn't arrived within a bound
  (SYNC-15-001, a new timing rule).
- **Coalesce on the CASE_MANAGER side:** collapse Rejects from one peer into
  a single replay while one is in flight (SYNC-15-003, SYNC-15-015).

The Reject exists so a participant that never gets the case still recovers.
Whatever changes must keep that guarantee.

Where: `vultron/core/behaviors/sync/`; specs SYNC-15-001, SYNC-15-003,
SYNC-15-015.

Where: vultron/core/behaviors/sync/

**Resolved**: 2026-10-30 — implementation tracked in #5555, #5556.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5554>.
Spec: `specs/sync-ledger-replication.yaml`.
Notes: `notes/sync-ledger-replication.md`.
ADR: ADR-0168 (proposed).
