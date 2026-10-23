---
source: IDEA-689
timestamp: '2026-06-05T20:04:47.554897+00:00'
title: 'Case actor spawning architecture: vendor container should not own case actor'
type: idea
---

## Summary

The two-actor demo creates the case actor as a sub-actor inside the vendor
container's DataLayer rather than routing to the dedicated case-actor Docker
service. This conflates two distinct actor identities into one container and
violates the intended MPCVD architecture.

## Motivation

The current code in `CreateCaseActorNode` creates the case actor using the
vendor container's `server_base_url`, giving it an actor ID rooted at
`http://vendor:8000/actors/case-actor-{slug}` and storing the actor object in
the vendor container's shared SQLite DataLayer. A dedicated `case-actor` Docker
service already exists (seed config at `docker/seed-configs/seed-case-actor.yaml`)
but is explicitly verified unused in the demo phase `D5-2`. This means:

- The vendor container is the de facto case manager, violating
  **DEMAMA-01-001** (each actor MUST run in its own container).
- The canonical case log lives in the vendor container, not in a dedicated
  service, making the log's actor attribution ambiguous.
- Replication of log entries to other participants is therefore incomplete
  (see #679 for the observable symptoms).

The long-term goal is dynamic case-actor spawning (e.g., provisioning a new
service/process in a cloud environment when a case is created). In the
short term, the demo should route case creation to the pre-started dedicated
case-actor service.

**Processed**: 2026-06-05 — planned into four implementation issues:

- #810: Demo fix: route case actor creation to dedicated case-actor service
- #811: Spec + ADR: CaseActor dynamic spawning protocol
- #812: Implement CaseActor dynamic spawning protocol
- #813: Actor discovery after CaseActor spawning: ID communication to participants
