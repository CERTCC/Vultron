---
source: CONCERN-4521
timestamp: '2026-10-12T18:13:30.077992+00:00'
title: '22 ADRs kept the #4196 rollout status_override, hiding them from the drift
  report'
type: learning
---

## Problem

The #4196 rollout gave 22 ADRs the same `status_override:`: "Set by the epoch lint rollout (#4196); the status predates the check and awaits a human's review against its epoch." An override holds a status off its epoch, so the hourly drift report (MS-14-007) never lists these ADRs. The human review that the override text promises has no trigger and no tracker.

Concrete case: ADR-0107 is `proposed` and has tested dependents (CP-01-008, VM-08-002). Without the override it would be reported as behind epoch 2.

Since #4519 (ADR-0120 revision 2), an override already on the base no longer exempts an ADR from a new promotion or from the first-dependent flip. Only the drift report still trusts these placeholder overrides.

## Why it matters

A placeholder override reads as a human's reason when none was given. The status is the confidence signal agents read (MS-14), so 22 ADRs carry a status that nobody has checked against the epoch.

## Options

1. A human reviews each of the 22 ADRs and either replaces the override with a real reason or drops it, so the drift report takes over. One docs-only PR. Recommended, because it is finite and the override text already asks for this.
2. Have the drift report ignore this exact placeholder text. That puts a magic string into tooling.

List: `grep -l "Set by the epoch lint rollout" docs/adr/*.md`

Where: docs/adr/

**Resolved**: 2026-10-12 — fixed directly in the docs PR; no implementation
issues. All 22 placeholder overrides dropped; ADR-0020, 0046, 0052 and 0069
moved to `accepted`; ADR-0105 and 0107 moved to `accepted-provisional`; the
other 16 were at or ahead of their epoch and keep their status (MS-14-012).

Docs PR: <https://github.com/CERTCC/Vultron/pull/4533>.

Notes: `notes/specs-vs-adrs.md`.
