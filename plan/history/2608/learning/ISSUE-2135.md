---
title: Protocol gap — no buffering for Announce(CaseLedgerEntry) when case not yet seeded
type: learning
timestamp: 2026-08-10T00:00:00Z
source: ISSUE-2135
signal: concern
---

During Bug #2135 (fcv demo CLP-08-005 race), the root cause analysis revealed
a deeper protocol gap: the implementation has no recovery path for
`Announce(CaseLedgerEntry)` arriving before the actor's `VulnerabilityCase`
genesis seed (i.e. `dl.read(case_id)` returns `None`).

ADR-0037 (`LedgerGapBuffer`) handles out-of-order entries among entries for a
known case, but it does not address the pre-genesis window where the case
object itself is absent.  The current behavior is fail-closed (CLP-08-005 /
`VultronValidationError`), which is correct but lossy: the entry is dropped
and the Finder must rely on a `Reject → replay` loop to recover.

In the demo, this is fixed with a `wait_for_case_on_container` ordering guard.
In production, however, the race window is a real protocol gap: a participant
who receives `Announce(CaseLedgerEntry)` before their `Create(VulnerabilityCase)`
(e.g. due to delivery reordering) silently drops the entry and may diverge.

**Suggested approach**: extend `LedgerGapBuffer` (or add a parallel
"pre-genesis buffer") to hold `Announce(CaseLedgerEntry)` activities when
`dl.read(case_id)` returns `None`, and drain them once the
`Create(VulnerabilityCase)` handler seeds the case.  This would close the
race completely without relying on demo-level polling guards.

A GitHub Bug/Concern issue should be filed to track this.

**Promoted**: 2026-08-17 — captured in GitHub #2186 (closed — protocol hardening gap fixed).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
