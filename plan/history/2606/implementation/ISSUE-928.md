---
source: ISSUE-928
timestamp: '2026-06-15T13:47:02.045331+00:00'
title: RM terminal-state guard for CLOSED participants
type: implementation
---

## Issue #928 — Add RM terminal-state guard: block further RM transitions on a participant once CLOSED

Implemented an RM terminal-state guard in the AddParticipantStatus receive BT path so participants already at RM.CLOSED reject further RM updates, including CLOSED→CLOSED rewrites. Added regression coverage proving terminal rewrites do not append participant statuses and do not commit CaseLedgerEntry cascades, and promoted invariant 7 in the CI case-ledger invariant harness by removing xfail.

PR: <https://github.com/CERTCC/Vultron/pull/947>
