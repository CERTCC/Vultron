---
source: PCR
timestamp: '2026-05-13T20:28:03.610044+00:00'
title: 'PCR: Announce trust guard, actor-scoped deferral, report-to-case link'
type: learning
---

## 2026-05-06 PCR — Replica seeding and deferred inbox replay

- First-time `Announce(VulnerabilityCase)` seeding cannot require a locally
  stored CaseActor yet; only reject the sender when a CaseActor for that case
  is already known and does not match.
- Unknown case-context activities need actor-scoped persisted deferral so the
  inbox can replay them after a later `Announce(VulnerabilityCase)` seeds the
  missing replica.
- Reporter-side report-to-case tracking benefits from a dedicated persisted
  link object so later announce handling can attach a received case replica to
  an earlier submitted report without scanning unrelated state.

**Promoted**: 2026-05-13 — trust guard for Announce seeding documented in
notes/participant-case-replica.md and captured as PCR-03-004 in
specs/participant-case-replica.yaml; actor-scoped deferral requirement added
as PCR-06-004; report-to-case link already captured in PCR-05-001/PCR-05-002.
