---
title: Per-actor stores block cross-actor access but not cross-actor expectation
type: learning
timestamp: 2026-08-25
source: ISSUE-2548
signal: spec-gap
---

ADR-0073 gave every actor its own store, and the invariant it states is about
**writes**: "one actor's writes must never affect what another actor could read."
That closed the access hole. It left the *expectation* hole wide open, and
nothing in the storage layout hints at it — the read simply comes back empty.

Issue #2548 is that hole. A single container hosts the report receiver and the
CaseActor it self-hosts. Under ADR-0041 the receiver does not create the case; it
proposes one, and the CaseActor creates it in **its own** store and replicates it
back as `Create(VulnerabilityCase)`. `validate-report` ran before the replica
landed, `find_case_by_report_id` correctly returned `None`, and the tree advanced
anyway. Every line of that was reachable *only* because the two actors shared a
host and the code had been written as though sharing a host meant sharing
knowledge.

The gap was real: no requirement said co-location grants no visibility. Two now
do — `PCR-01-003` (actors exchange information only by protocol message; an actor
that asked a CaseActor for a case MUST treat it as absent until the replica
arrives) and `ID-04-005` (a guard record is written last, never first). ADR-0073
carries the matching "Leak 3" section. **These are already in `specs/`; `learn`
does not need to promote them again.**

**How to apply.**

- The question to ask of any new cross-actor step is not "can this actor reach
  the other's store" — isolation already answers no. It is "does this code assume
  it already knows something only a message can tell it?" Isolation makes that
  assumption *fail*, not *impossible*.
- Absence of a replica is a routine transient state under per-actor storage, not
  an exceptional one. Treat "not here yet" as FAILURE-and-retry, never as
  SUCCESS-by-skip (ARCH-15-001).
- Watch for the pairing that made this permanent: a two-half transition where one
  half is also the evidence a guard reads. Order matters more than it looks —
  see [[latch-written-first-is-a-permanent-lie]].
- Related: [[one-actor-id-is-one-database]] and
  [[role-holder-receiver-store-must-agree]] are the same ADR's earlier lessons,
  both about layout. This one is about doctrine.
