---
source: CONCERN-3364
timestamp: '2026-10-22T15:00:25.223521+00:00'
title: How strong do ledger fanout ordering guarantees need to be?
type: learning
---

## Summary

Ledger fanout is not instantaneous: the CASE_MANAGER relays a Case Ledger Entry to Participants across several instances, so for a short window those Participants can observe activities in different orders. The working position is that eventual consistency suffices. That position has not been tested against any coordination decision that might need more.

## Surface Symptom vs. Underlying Problem

**Surface reading**: "out-of-order delivery is a bug to fix with ordered transport." It is not — the existing design is right on this point and should be left alone: no part of the protocol depends on arrival order, `logIndex` carries the authoritative sequence, and gap detection plus ledger reconciliation (SYNC-00-007/008, ADR-0037) repairs a hole without ordered transport.

**Underlying problem**: "no part of the protocol uses arrival order" is an assertion nobody has audited. If some decision — an embargo termination race, a simultaneous state change by two Participants — turns out to need a stronger guarantee, the place to discover that is not production.

## Category

Protocol correctness — ledger replication.

## Severity

Low-to-medium. Wrong only if a real ordering dependency exists, in which case it is silently wrong.

## Evidence

Documented at `docs/topics/future_work/_oq-fanout-ordering.md`. What is already settled: `logIndex` holds the sequence (ADR-0079); a Participant that receives 1, 2, 3, 5 buffers 5 and lets ledger reconciliation deliver 4; gap detection replaces delivery ordering.

What is not: no audit exists showing that no coordination decision needs more than eventual consistency.

## Impact if Ignored

An ordering dependency, if one exists, surfaces as a rare non-reproducible divergence between Participant replicas — the hardest class of bug to diagnose after the fact.

## Suggested Action

Audit the protocol's decision points for arrival-order dependence. If the audit is clean, record eventual consistency as a decided property with the audit as evidence rather than leaving it as a working assumption.

## Reference

Docs: `docs/topics/future_work/_oq-fanout-ordering.md`
Specs: SYNC-00-007, SYNC-00-008
ADR: ADR-0037 (receiver-side buffering), ADR-0079 (`logIndex` sequence)
Source: #3286

**Resolved**: 2026-10-22 — implementation tracked in #5102.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5103>.
