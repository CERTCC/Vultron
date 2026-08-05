---
source: CONCERN-1755
timestamp: '2026-08-05T21:25:05.200985+00:00'
title: Ownership transfer notification to non-involved participants is underspecified
type: learning
---

## Summary

When case ownership transfers from one actor to another, participants not
directly involved in the transfer (e.g., Finder, Vendor2) receive no explicit
notification of the change. The protocol did not specify who announces the
transfer, to whom, from where, or in what order.

**Surface:** In the FVCV-handoff demo, Finder is not notified that Vendor1
has transferred ownership to Coordinator. From Finder's perspective, the case
owner silently changed.

**Deeper problem:** Both `Offer(VulnerabilityCase)` and
`Accept(Offer(VulnerabilityCase))` (ownership-transfer variant) were sent
actor-to-actor, bypassing the CaseActor. No `CaseLedgerEntry` was committed,
so the `Announce(CaseLedgerEntry)` broadcast never fired.

**Resolved**: 2026-08-05 — implementation tracked in #2015, #2016.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2013>.
Spec: `specs/case-management.yaml` CM-21-005, CM-21-006, CM-21-007.
Notes: `notes/ownership-transfer.md`.
