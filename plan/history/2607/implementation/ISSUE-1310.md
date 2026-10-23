---
source: ISSUE-1310
timestamp: '2026-07-22T13:40:29.944491+00:00'
title: FUZZ-08b publication-intent per-artifact arms
type: implementation
---

## Issue #1310 — FUZZ-08b: Implement publication-intent per-artifact arms (Production Collapse 2)

Implemented Production Collapse 2 (ADR-0028 / BT-20-002): collapsed the twelve
simulator publication nodes into a single `PrioritizePublicationIntents`
Evaluator that writes a structured `PublicationIntentDecision` record. The
record's booleans gate three named per-artifact arms (exploit, fix, report),
each shaped as `Selector(Sequence(ShouldPublishX, PrepareX, Publish),
Inverter(ShouldPublishX))` so a not-intended arm is a graceful SUCCESS no-op
while a genuine Prepare/Publish failure still fails the tree.

Eliminated the `PublicationIntentsSet` flag check, the `NoPublish*` bypass
leaves, and the `ReprioritizeX` Evaluators. Added positively-named
`ShouldPublish*` gate nodes (BTND-08-001). Finalized ADR-0028 (proposed →
accepted, lean Option 1) before coding, and removed the PROVISIONAL marker from
spec BT-20-002 (BT-21-002). Directly modeled on the merged Production Collapse
1 (issue #1309 / PR #1566).

PR: <https://github.com/CERTCC/Vultron/pull/1580>
