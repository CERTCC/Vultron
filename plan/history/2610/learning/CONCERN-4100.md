---
source: CONCERN-4100
timestamp: '2026-10-05T18:00:41.071821+00:00'
title: 'RM.CLOSED and case content: closed participants receive nothing after their
  own closure entry'
type: learning
---

## Original concern

Two rules disagreed about whether a participant at RM `CLOSED` still receives case content. ADR-0114 and CM-23-004 said it receives nothing further; the code (the `case_fully_closed` fan-out) and every demo's M7 check ("all participants RM.CLOSED on both replicas") relied on closed replicas still receiving ledger entries. A departing participant learns its own `CLOSED` only from the CASE_MANAGER's ledger entry, because the `Leave(VulnerabilityCase)` sender side does not write it. Options: (1) strict CM-23-004 plus a departure exception; (2) amend to read-only closed replicas; (3) a final `Announce(VulnerabilityCase)` snapshot.

## Resolution

Decision (Allen D. Householder): closed means the participant has stopped paying attention, so it receives no further case content, period. The ledger entry recording its own closure is the last thing it receives. Participants never write their own `CLOSED`: a leaver waits for the CASE_MANAGER's entry, then exits. "All participants closed" is verified in the CASE_MANAGER's store, not on every replica. One combined implementation issue, because the strict rule turns the demo checks red on its own.

**Resolved**: 2026-10-05 — implementation tracked in #4212.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4211>.
Spec: `specs/case-management.yaml`.
Notes: `notes/case-joining.md`.
